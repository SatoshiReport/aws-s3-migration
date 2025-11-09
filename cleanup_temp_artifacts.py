#!/usr/bin/env python3
"""
Scan backup trees for disposable cache/temp artifacts and optionally delete them.

The script focuses on developer tooling residue (Python caches, VS Code remote
downloads, language package caches, etc.) and intentionally ignores macOS system
metadata (.Spotlight-V100, .DS_Store, ...).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator, Sequence

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import config as config_module  # type: ignore
except ImportError:  # pragma: no cover - best-effort fallback
    config_module = None

try:  # Shared state DB utilities.
    from .state_db_admin import reseed_state_db_from_local_drive
except ImportError:  # pragma: no cover - direct script execution
    from state_db_admin import reseed_state_db_from_local_drive  # type: ignore

Matcher = Callable[[Path, bool], bool]


@dataclass(frozen=True)
class Category:
    name: str
    description: str
    matcher: Matcher
    prune: bool = True


@dataclass
class Candidate:
    path: Path
    category: Category
    size_bytes: int | None
    mtime: float

    @property
    def iso_mtime(self) -> str:
        return datetime.fromtimestamp(self.mtime, tz=timezone.utc).isoformat()


@dataclass
class CandidateLoadResult:
    candidates: list[Candidate]
    cache_path: Path | None
    cache_used: bool
    total_files: int
    max_rowid: int


class CandidateLoadError(RuntimeError):
    """Raised when the migration database cannot be queried."""


CACHE_VERSION = 2
PROGRESS_UPDATE_INTERVAL_SECONDS = 0.5
BYTES_PER_KIB = 1024
BYTES_PER_MIB = BYTES_PER_KIB**2
BYTES_PER_GIB = BYTES_PER_KIB**3
BYTES_PER_TIB = BYTES_PER_KIB**4


def _default_cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")).expanduser()
    return base / "cleanup_temp_artifacts"


def build_scan_params(
    categories: Sequence[Category],
    older_than: int | None,
    min_size_bytes: int | None,
) -> dict[str, object]:
    return {
        "categories": [cat.name for cat in categories],
        "older_than": older_than,
        "min_size_bytes": min_size_bytes,
    }


def build_cache_key(base_path: Path, db_path: Path, scan_params: dict[str, object]) -> str:
    payload = {
        "base_path": str(base_path),
        "db_path": str(db_path),
        "scan_params": scan_params,
    }
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_cache(
    cache_path: Path,
    scan_params: dict[str, object],
    category_map: dict[str, Category],
) -> tuple[list[Candidate], dict] | None:
    try:
        payload = json.loads(cache_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Failed to read cache %s: %s", cache_path, exc)
        return None
    if payload.get("version") != CACHE_VERSION:
        return None
    if payload.get("scan_params") != scan_params:
        return None
    metadata = {
        "generated_at": payload.get("generated_at"),
        "rowcount": payload.get("rowcount"),
        "max_rowid": payload.get("max_rowid"),
        "db_mtime_ns": payload.get("db_mtime_ns"),
    }
    items = payload.get("candidates", [])
    candidates: list[Candidate] = []
    for item in items:
        cat_name = item.get("category")
        if cat_name not in category_map:
            return None
        candidates.append(
            Candidate(
                path=Path(item["path"]),
                category=category_map[cat_name],
                size_bytes=item.get("size_bytes"),
                mtime=item.get("mtime", 0),
            )
        )
    return candidates, metadata


def write_cache(  # noqa: PLR0913 - function arguments reflect cache metadata requirements
    cache_path: Path,
    candidates: Sequence[Candidate],
    *,
    scan_params: dict[str, object],
    base_path: Path,
    db_path: Path,
    rowcount: int,
    max_rowid: int,
    db_mtime_ns: int,
) -> None:
    payload = {
        "version": CACHE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_path": str(base_path),
        "db_path": str(db_path),
        "rowcount": rowcount,
        "max_rowid": max_rowid,
        "db_mtime_ns": db_mtime_ns,
        "scan_params": scan_params,
        "candidates": [
            {
                "path": str(c.path),
                "category": c.category.name,
                "size_bytes": c.size_bytes,
                "mtime": c.mtime,
            }
            for c in candidates
        ],
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2))


def cache_is_valid(  # noqa: PLR0911 - explicit guard clauses improve readability
    metadata: dict,
    *,
    ttl_seconds: int,
    rowcount: int,
    max_rowid: int,
    db_mtime_ns: int,
) -> bool:
    if metadata.get("rowcount") != rowcount:
        return False
    if metadata.get("max_rowid") != max_rowid:
        return False
    if metadata.get("db_mtime_ns") != db_mtime_ns:
        return False
    generated_at = metadata.get("generated_at")
    if ttl_seconds > 0:
        if not generated_at:
            return False
        try:
            generated_dt = datetime.fromisoformat(generated_at)
        except ValueError:
            return False
        age = (datetime.now(timezone.utc) - generated_dt).total_seconds()
        if age > ttl_seconds:
            return False
    return True


def derive_local_path(base_path: Path, bucket: str, key: str) -> Path | None:
    """Convert a bucket/key pair into the expected local filesystem path."""
    candidate = base_path / bucket
    for part in PurePosixPath(key).parts:
        if part in ("", "."):
            continue
        if part == "..":
            return None
        candidate /= part
    try:
        candidate.relative_to(base_path)
    except ValueError:
        return None
    return candidate


def iter_relevant_dirs(file_path: Path, base_path: Path) -> Iterator[Path]:
    """Yield ancestor directories under base_path (excluding base_path itself)."""
    try:
        file_path.relative_to(base_path)
    except ValueError:
        return
    current = file_path.parent
    while True:
        try:
            current.relative_to(base_path)
        except ValueError:
            break
        if current == base_path:
            break
        yield current
        current = current.parent


class ProgressTracker:
    """Minimal progress indicator for long-running scans."""

    def __init__(self, total: int, label: str):
        self.total = total
        self.label = label
        self.start = time.time()
        self.last_print = 0.0

    def update(self, current: int):
        now = time.time()
        if current == self.total or now - self.last_print >= PROGRESS_UPDATE_INTERVAL_SECONDS:
            if self.total:
                pct = (current / self.total) * 100
                status = f"{current:,}/{self.total:,} ({pct:5.1f}%)"
            else:
                status = f"{current:,}"
            print(f"\r{self.label}: {status}", end="", flush=True)
            self.last_print = now

    def finish(self):
        print()


def _determine_default_base_path() -> Path | None:
    """Return the most likely local base path for migrated objects."""

    candidates: list[Path] = []
    if config_module and getattr(config_module, "LOCAL_BASE_PATH", None):
        candidates.append(Path(config_module.LOCAL_BASE_PATH).expanduser())
    for name in ("CLEANUP_TEMP_ROOT", "CLEANUP_ROOT"):
        if os.environ.get(name):
            candidates.append(Path(os.environ[name]).expanduser())
    candidates.extend(
        [
            Path("/Volumes/Extreme SSD/s3_backup"),
            Path("/Volumes/Extreme SSD"),
            Path.cwd(),
        ]
    )
    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def _determine_default_db_path() -> Path:
    """Return the default SQLite DB path shared with migrate_v2."""

    if config_module and getattr(config_module, "STATE_DB_PATH", None):
        candidate = Path(config_module.STATE_DB_PATH)
    else:
        candidate = Path("s3_migration_state.db")
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    return candidate


DEFAULT_BASE_PATH = _determine_default_base_path()
DEFAULT_DB_PATH = _determine_default_db_path()


def _match_python_bytecode(path: Path, is_dir: bool) -> bool:
    return is_dir and path.name == "__pycache__"


def _match_python_test_cache(path: Path, is_dir: bool) -> bool:
    return is_dir and path.name in {".pytest_cache", ".mypy_cache", ".hypothesis"}


def _match_python_tox_cache(path: Path, is_dir: bool) -> bool:
    return is_dir and path.name in {".tox", ".nox", ".ruff_cache"}


def _match_generic_dot_cache(path: Path, is_dir: bool) -> bool:
    return is_dir and path.name == ".cache"


def _match_vscode_remote(path: Path, is_dir: bool) -> bool:
    return (
        is_dir
        and ".vscode-server" in path.parts
        and path.name in {"node_modules", "extensions", "server"}
    )


def _match_go_module_cache(path: Path, is_dir: bool) -> bool:
    if not is_dir or path.name != "cache":
        return False
    parts = ("go", "pkg", "mod", "cache")
    return path.parts[-len(parts) :] == parts if len(path.parts) >= len(parts) else False


def _match_maven_cache(path: Path, is_dir: bool) -> bool:
    if not is_dir or not path.name.startswith(".cache"):
        return False
    if ".m2" not in path.parts:
        return False
    parts = (".m2", "repository", path.name)
    return path.parts[-len(parts) :] == parts if len(path.parts) >= len(parts) else False


def _match_npm_cache(path: Path, is_dir: bool) -> bool:
    if not is_dir:
        return False
    return (path.name == "_cacache" and path.parent.name == ".npm") or (
        path.name == "cache" and path.parent.name == ".yarn"
    )


def build_categories() -> dict[str, Category]:
    """Return the static set of cleanup categories."""
    categories = [
        Category(
            name="python-bytecode",
            description="Python __pycache__ directories generated by the interpreter.",
            matcher=_match_python_bytecode,
        ),
        Category(
            name="python-test-cache",
            description=".pytest_cache / .mypy_cache / .hypothesis artifacts from test runs.",
            matcher=_match_python_test_cache,
        ),
        Category(
            name="python-tox-cache",
            description="Python tooling environments such as .tox, .nox, and .ruff_cache.",
            matcher=_match_python_tox_cache,
        ),
        Category(
            name="generic-dot-cache",
            description="Generic .cache directories (pip wheels, IDE caches, etc.).",
            matcher=_match_generic_dot_cache,
        ),
        Category(
            name="vscode-remote",
            description="VS Code Remote server bundles (node_modules, extensions, server caches).",
            matcher=_match_vscode_remote,
        ),
        Category(
            name="go-module-cache",
            description="Go module download cache under go/pkg/mod/cache.",
            matcher=_match_go_module_cache,
        ),
        Category(
            name="maven-cache",
            description="Maven .m2/repository/.cache directories.",
            matcher=_match_maven_cache,
        ),
        Category(
            name="npm-cache",
            description="npm/yarn cache folders such as .npm/_cacache and .yarn/cache.",
            matcher=_match_npm_cache,
        ),
    ]
    return {c.name: c for c in categories}


def parse_size(text: str) -> int:
    """Parse human-readable size strings (e.g. 10G, 512M) into bytes."""
    text = text.strip().upper()
    multiplier = 1
    if text.endswith("K"):
        multiplier = BYTES_PER_KIB
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = BYTES_PER_MIB
        text = text[:-1]
    elif text.endswith("G"):
        multiplier = BYTES_PER_GIB
        text = text[:-1]
    elif text.endswith("T"):
        multiplier = BYTES_PER_TIB
        text = text[:-1]
    return int(float(text) * multiplier)


def format_size(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "n/a"
    suffixes = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(num_bytes)
    for suffix in suffixes:
        if value < BYTES_PER_KIB or suffix == suffixes[-1]:
            return f"{value:.1f}{suffix}"
        value /= BYTES_PER_KIB
    return f"{value:.1f}PB"


def match_category(path: Path, is_dir: bool, categories: Sequence[Category]) -> Category | None:
    for category in categories:
        try:
            if category.matcher(path, is_dir):
                return category
        except Exception as exc:  # Defensive: matcher should not break the scan.
            logging.warning("Matcher %s failed on %s: %s", category.name, path, exc)
    return None


def _process_parent_directory(
    parent: Path,
    file_size: int,
    candidates: dict[Path, Candidate],
    non_matching: set[Path],
    categories: Sequence[Category],
    cutoff_ts: float | None,
) -> None:
    """Process a single parent directory for inclusion in candidates."""
    try:
        canonical = parent.resolve()
    except OSError:
        return

    entry = candidates.get(canonical)
    if entry:
        entry.size_bytes = (entry.size_bytes or 0) + file_size
        return

    if canonical in non_matching:
        return

    category = match_category(parent, True, categories)
    if not category:
        non_matching.add(canonical)
        return

    try:
        stat = parent.stat()
    except OSError as exc:
        logging.warning("Unable to stat %s: %s", parent, exc)
        non_matching.add(canonical)
        return

    if cutoff_ts is not None and stat.st_mtime > cutoff_ts:
        non_matching.add(canonical)
        return

    candidates[canonical] = Candidate(
        path=parent,
        category=category,
        size_bytes=file_size,
        mtime=stat.st_mtime,
    )


def _filter_candidates_by_size(
    candidates: dict[Path, Candidate], min_size_bytes: int | None
) -> list[Candidate]:
    """Filter candidates by minimum size requirement."""
    results: list[Candidate] = []
    for candidate in candidates.values():
        size_bytes = candidate.size_bytes or 0
        if min_size_bytes is not None and size_bytes < min_size_bytes:
            continue
        candidate.size_bytes = size_bytes
        results.append(candidate)
    return results


def scan_candidates_from_db(
    conn: sqlite3.Connection,
    base_path: Path,
    categories: Sequence[Category],
    *,
    cutoff_ts: float | None,
    min_size_bytes: int | None,
    total_files: int,
) -> list[Candidate]:
    """Inspect the migration SQLite database and find directories worth pruning."""
    base_path = base_path.resolve()
    progress = ProgressTracker(total_files, "Scanning migration database")
    candidates: dict[Path, Candidate] = {}
    non_matching: set[Path] = set()

    if total_files == 0:
        progress.update(0)

    cursor = conn.execute("SELECT bucket, key, size FROM files")
    for idx, row in enumerate(cursor, start=1):
        progress.update(idx)
        local_file = derive_local_path(base_path, row["bucket"], row["key"])
        if local_file is None:
            continue
        file_size = row["size"] or 0
        for parent in iter_relevant_dirs(local_file, base_path):
            _process_parent_directory(
                parent, file_size, candidates, non_matching, categories, cutoff_ts
            )
    progress.finish()
    return _filter_candidates_by_size(candidates, min_size_bytes)


def summarise(candidates: Sequence[Candidate]) -> list[tuple[str, int, int]]:
    """Return per-category summary of (name, count, total_size)."""
    summary: dict[str, tuple[int, int]] = {}
    for candidate in candidates:
        count, total_size = summary.get(candidate.category.name, (0, 0))
        summary[candidate.category.name] = (count + 1, total_size + (candidate.size_bytes or 0))
    return sorted((name, cnt, size) for name, (cnt, size) in summary.items())


def write_reports(
    candidates: Sequence[Candidate],
    *,
    json_path: Path | None,
    csv_path: Path | None,
) -> None:
    rows = [
        {
            "path": str(c.path),
            "category": c.category.name,
            "size_bytes": c.size_bytes,
            "size_human": format_size(c.size_bytes),
            "mtime": c.iso_mtime,
        }
        for c in candidates
    ]
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(rows, indent=2))
    if csv_path:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["path", "category", "size_bytes", "size_human", "mtime"]
            )
            writer.writeheader()
            writer.writerows(rows)


def order_candidates(
    candidates: Sequence[Candidate],
    *,
    order: str,
) -> list[Candidate]:
    if order == "size":
        return sorted(candidates, key=lambda c: c.size_bytes or 0, reverse=True)
    return sorted(candidates, key=lambda c: str(c.path))


def delete_paths(
    candidates: Sequence[Candidate], *, root: Path
) -> list[tuple[Candidate, Exception]]:
    errors: list[tuple[Candidate, Exception]] = []
    for candidate in candidates:
        resolved = candidate.path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            errors.append((candidate, ValueError(f"{resolved} escapes root {root}")))
            continue
        try:
            if resolved.is_dir():
                shutil.rmtree(resolved)
            else:
                resolved.unlink()
        except (OSError, shutil.Error) as exc:
            logging.exception("Failed to delete %s", resolved)
            errors.append((candidate, exc))
        else:
            logging.info("Deleted %s", resolved)
    return errors


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    categories = build_categories()
    parser = argparse.ArgumentParser(description=__doc__)
    base_help = "Local base path containing migrated bucket folders."
    if DEFAULT_BASE_PATH:
        base_help += f" Default: {DEFAULT_BASE_PATH}."
    parser.add_argument(
        "--base-path",
        default=str(DEFAULT_BASE_PATH) if DEFAULT_BASE_PATH else None,
        help=base_help,
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to migration SQLite database (default: {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--reset-state-db",
        action="store_true",
        help="Delete and recreate the migrate_v2 state DB before scanning.",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=sorted(categories),
        default=sorted(categories),
        help="Categories to include (default: all).",
    )
    parser.add_argument(
        "--older-than", type=int, metavar="DAYS", help="Only include entries older than DAYS."
    )
    parser.add_argument(
        "--min-size",
        type=str,
        help="Only include entries >= SIZE (e.g. 500M).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of entries acted on (heaviest first when sorting by size).",
    )
    parser.add_argument(
        "--sort",
        choices={"path", "size"},
        default="path",
        help="Order used when reporting/deleting.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the matched entries. Default is dry-run/report only.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts for destructive actions (deletes, DB reset).",
    )
    parser.add_argument(
        "--report-json", type=Path, help="Optional path to write the full candidate list as JSON."
    )
    parser.add_argument("--report-csv", type=Path, help="Optional path to write the report as CSV.")
    parser.add_argument(
        "--list-categories", action="store_true", help="List available categories and exit."
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Directory for cached scan results (default: ~/.cache/cleanup_temp_artifacts).",
    )
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=43200,
        help="Reuse cached scans younger than TTL seconds (default: 43200). Set <=0 to disable TTL expiration.",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Force a fresh scan even if cache metadata matches the database.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache reads and writes entirely.",
    )
    args = parser.parse_args(argv)
    if args.list_categories:
        for cat in categories.values():
            print(f"{cat.name:20} {cat.description}")
        sys.exit(0)
    if not args.base_path:
        parser.error("--base-path is required when no default could be determined.")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive.")
    args.min_size_bytes = parse_size(args.min_size) if args.min_size else None
    args.categories = [categories[name] for name in args.categories]
    args.cache_dir = Path(args.cache_dir).expanduser() if args.cache_dir else _default_cache_dir()
    args.cache_enabled = not args.no_cache
    return args


def maybe_reset_state_db(
    base_path: Path,
    db_path: Path,
    *,
    reset_requested: bool,
    auto_confirm: bool,
) -> Path:
    """Handle optional migrate_v2 state DB reseeding."""
    if not reset_requested:
        return db_path
    reset_confirmed = auto_confirm
    if not reset_confirmed:
        resp = (
            input(
                f"Reset migrate_v2 state database at {db_path}? "
                "This deletes cached migration metadata. [y/N] "
            )
            .strip()
            .lower()
        )
        reset_confirmed = resp in {"y", "yes"}
        if not reset_confirmed:
            print("State database reset cancelled; continuing without reset.")
            return db_path
    new_db_path, file_count, total_bytes = reseed_state_db_from_local_drive(base_path, db_path)
    print(
        f"✓ Recreated migrate_v2 state database at {new_db_path} "
        f"({file_count:,} files, {format_size(total_bytes)}). Continuing."
    )
    return new_db_path


def load_candidates_from_db(
    *,
    args: argparse.Namespace,
    base_path: Path,
    db_path: Path,
    db_stat: os.stat_result,
    cutoff_ts: float | None,
    scan_params: dict[str, object],
) -> CandidateLoadResult:
    """Read candidate directories, honoring cache settings."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:  # pragma: no cover - connection failure
        message = f"Failed to open SQLite database {db_path}"
        raise CandidateLoadError(message) from exc  # noqa: TRY003

    category_map = {cat.name: cat for cat in args.categories}
    cache_path: Path | None = None
    cache_used = False
    candidates: list[Candidate] | None = None

    try:
        try:
            total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        except sqlite3.OperationalError as exc:
            raise CandidateLoadError(  # noqa: TRY003
                "Migration database missing expected 'files' table"
            ) from exc
        try:
            max_rowid_row = conn.execute("SELECT MAX(rowid) FROM files").fetchone()
            max_rowid = max_rowid_row[0] if max_rowid_row and max_rowid_row[0] is not None else 0
        except sqlite3.OperationalError:
            max_rowid = total_files

        if args.cache_enabled:
            cache_key = build_cache_key(base_path, db_path, scan_params)
            cache_dir = args.cache_dir
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / f"{cache_key}.json"
            if cache_path.exists() and not args.refresh_cache:
                loaded = load_cache(cache_path, scan_params, category_map)
                if loaded:
                    cached_candidates, metadata = loaded
                    if cache_is_valid(
                        metadata,
                        ttl_seconds=args.cache_ttl,
                        rowcount=total_files,
                        max_rowid=max_rowid,
                        db_mtime_ns=db_stat.st_mtime_ns,
                    ):
                        candidates = cached_candidates
                        cache_used = True
                        generated = metadata.get("generated_at", "unknown time")
                        print(
                            f"Using cached results from {generated} "
                            f"(files={total_files:,}). Use --refresh-cache to rescan.\n"
                        )

        if candidates is None:
            candidates = scan_candidates_from_db(
                conn,
                base_path,
                args.categories,
                cutoff_ts=cutoff_ts,
                min_size_bytes=args.min_size_bytes,
                total_files=total_files,
            )

        return CandidateLoadResult(
            candidates=candidates,
            cache_path=cache_path,
            cache_used=cache_used,
            total_files=total_files,
            max_rowid=max_rowid,
        )
    finally:
        conn.close()


def main(  # noqa: C901, PLR0911, PLR0912, PLR0915 - CLI orchestration benefits from linear flow
    argv: Sequence[str] | None = None,
) -> int:
    args = parse_args(argv or sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    base_path = Path(args.base_path).expanduser()
    if not base_path.exists():
        logging.error("Base path %s does not exist.", base_path)
        return 1
    base_path = base_path.resolve()

    db_path = Path(args.db_path).expanduser()
    if not db_path.is_absolute():
        db_path = (REPO_ROOT / db_path).resolve()
    else:
        db_path = db_path.resolve()

    db_path = maybe_reset_state_db(
        base_path,
        db_path,
        reset_requested=args.reset_state_db,
        auto_confirm=args.yes,
    )

    if not db_path.exists():
        logging.error("SQLite database %s does not exist.", db_path)
        return 1
    db_path = db_path.resolve()
    db_stat = db_path.stat()

    cutoff_ts: float | None = None
    if args.older_than:
        cutoff_ts = time.time() - (args.older_than * 86400)

    if not args.delete:
        print("Dry run: no directories will be deleted. Use --delete --yes to remove them.\n")

    scan_params = build_scan_params(
        args.categories,
        args.older_than,
        args.min_size_bytes,
    )
    try:
        load_result = load_candidates_from_db(
            args=args,
            base_path=base_path,
            db_path=db_path,
            db_stat=db_stat,
            cutoff_ts=cutoff_ts,
            scan_params=scan_params,
        )
    except CandidateLoadError:
        logging.exception("Failed to load candidates from database")
        return 1

    candidates = load_result.candidates
    cache_path = load_result.cache_path
    cache_used = load_result.cache_used

    if args.cache_enabled and cache_path and not cache_used:
        try:
            write_cache(
                cache_path,
                load_result.candidates,
                scan_params=scan_params,
                base_path=base_path,
                db_path=db_path,
                rowcount=load_result.total_files,
                max_rowid=load_result.max_rowid,
                db_mtime_ns=db_stat.st_mtime_ns,
            )
        except OSError as exc:
            logging.warning("Failed to write cache %s: %s", cache_path, exc)
    if not candidates:
        print("No candidates found for the selected categories.")
        return 0

    ordered = order_candidates(candidates, order=args.sort)
    acted_upon = ordered[: args.limit] if args.limit else ordered

    print(
        f"Identified {len(candidates)} candidate(s) (showing {len(acted_upon)}) under {base_path}:"
    )
    for candidate in acted_upon:
        size_str = format_size(candidate.size_bytes)
        print(
            f"- [{candidate.category.name}] {candidate.path} (mtime {candidate.iso_mtime}, size {size_str})"
        )

    summary = summarise(candidates)
    print("\nPer-category totals:")
    for name, count, size in summary:
        print(f"  {name:20} count={count:6d} size={format_size(size)}")

    write_reports(ordered, json_path=args.report_json, csv_path=args.report_csv)

    if args.delete:
        if not args.yes:
            resp = input(f"\nDelete {len(acted_upon)} entry(ies)? [y/N] ").strip().lower()
            if resp not in {"y", "yes"}:
                print("Aborted by user.")
                return 0
        errors = delete_paths(acted_upon, root=base_path.resolve())
        if errors:
            print(f"Completed with {len(errors)} error(s); see log for details.")
            return 2
        print("Deletion complete.")
    else:
        print("\nDry run only (use --delete --yes to remove the listed entries).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
