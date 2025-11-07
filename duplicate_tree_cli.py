"""CLI workflow for duplicate tree analysis."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:  # Prefer package-relative imports when packaged
    from . import config as config_module  # type: ignore
    from .duplicate_tree_core import (
        DirectoryIndex,
        DuplicateCluster,
        find_exact_duplicates,
    )
    from .duplicate_tree_models import (
        FilesTableReadError,
        PathTuple,
        ProgressPrinter,
    )
except ImportError:  # pragma: no cover - execution as standalone script
    import config as config_module  # type: ignore
    from duplicate_tree_core import (  # type: ignore
        DirectoryIndex,
        DuplicateCluster,
        find_exact_duplicates,
    )
    from duplicate_tree_models import (  # type: ignore
        FilesTableReadError,
        PathTuple,
        ProgressPrinter,
    )


CACHE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS duplicate_tree_cache (
    fingerprint TEXT NOT NULL,
    tolerance REAL NOT NULL,
    base_path TEXT NOT NULL,
    total_files INTEGER NOT NULL,
    generated_at TEXT NOT NULL,
    report TEXT NOT NULL,
    PRIMARY KEY (fingerprint, tolerance, base_path)
)
"""

EXACT_TOLERANCE = 1.0
MIN_REPORT_FILES = 2
MIN_REPORT_BYTES = 512 * 1024 * 1024  # 0.5 GiB

ClusterRow = Dict[str, Any]
NodeRow = Dict[str, Any]


@dataclass(frozen=True)
class ScanFingerprint:
    """Uniquely identifies a DB snapshot by file count + checksum."""

    total_files: int
    checksum: str


def build_directory_index_from_db(  # pylint: disable=too-many-locals
    db_path: str, progress_label: str = "Scanning files"
) -> tuple[DirectoryIndex, ScanFingerprint]:
    """Stream the files table and construct the in-memory directory index."""
    index = DirectoryIndex()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        try:
            total_files = conn.execute(
                "SELECT COUNT(*) FROM files WHERE key NOT LIKE '%/'"
            ).fetchone()[0]
        except sqlite3.OperationalError as exc:
            raise FilesTableReadError(db_path) from exc
        progress = ProgressPrinter(total_files, progress_label)
        start_time = time.time()
        cursor = conn.execute(
            """
            SELECT bucket, key, size,
                   COALESCE(local_checksum, etag, '') AS checksum
            FROM files
            ORDER BY bucket, key
            """
        )
        processed = 0
        hasher = hashlib.sha256()
        try:
            for processed, row in enumerate(cursor, start=1):
                checksum = row["checksum"] or ""
                bucket = row["bucket"]
                key = row["key"]
                size = row["size"]
                index.add_file(bucket, key, size, checksum)
                for value in (bucket, key, str(size), checksum):
                    hasher.update(value.encode("utf-8"))
                    hasher.update(b"\0")
                progress.update(processed)
        except KeyboardInterrupt:
            print("\n\n✗ Scan interrupted by user.")
            raise
        finally:
            elapsed = time.time() - start_time
            progress.finish(
                f"{progress_label} processed {processed:,}/{total_files:,} files in {elapsed:.1f}s"
            )
    finally:
        conn.close()
    index.finalize()
    fingerprint = ScanFingerprint(total_files=total_files, checksum=hasher.hexdigest())
    return index, fingerprint


def _ensure_cache_table(conn: sqlite3.Connection):
    conn.execute(CACHE_TABLE_SQL)
    conn.commit()


def load_cached_report(
    db_path: str,
    fingerprint: ScanFingerprint,
    base_path: str,
    min_files: int = MIN_REPORT_FILES,
    min_bytes: int = MIN_REPORT_BYTES,
) -> Optional[Dict[str, str]]:
    """Return cached report metadata if it matches the current snapshot."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_cache_table(conn)
        key = _cache_key(fingerprint, min_files, min_bytes)
        row = conn.execute(
            """
            SELECT total_files, generated_at, report
            FROM duplicate_tree_cache
            WHERE fingerprint = ? AND tolerance = ? AND base_path = ?
            """,
            (key, EXACT_TOLERANCE, base_path),
        ).fetchone()
        if row is None:
            return None
        if row["total_files"] != fingerprint.total_files:
            return None
        payload = row["report"]
        try:
            rows = json.loads(payload)
            return {
                "generated_at": row["generated_at"],
                "rows": rows,
                "total_files": str(row["total_files"]),
            }
        except json.JSONDecodeError:
            return {
                "generated_at": row["generated_at"],
                "report": payload,
                "total_files": str(row["total_files"]),
            }
    finally:
        conn.close()


def store_cached_report(
    db_path: str,
    fingerprint: ScanFingerprint,
    base_path: str,
    clusters: Sequence[DuplicateCluster],
    min_files: int = MIN_REPORT_FILES,
    min_bytes: int = MIN_REPORT_BYTES,
):
    """Persist the latest duplicate analysis snapshot."""
    conn = sqlite3.connect(db_path)
    try:
        _ensure_cache_table(conn)
        key = _cache_key(fingerprint, min_files, min_bytes)
        payload = json.dumps(_clusters_to_rows(clusters))
        conn.execute(
            """
            INSERT OR REPLACE INTO duplicate_tree_cache (
                fingerprint, tolerance, base_path, total_files, generated_at, report
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                EXACT_TOLERANCE,
                base_path,
                fingerprint.total_files,
                datetime.now(timezone.utc).isoformat(),
                payload,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _path_on_disk(base_path: Path, node_path: PathTuple) -> Path:
    return base_path.joinpath(*node_path)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments controlling database path, base path, and tolerance."""
    parser = argparse.ArgumentParser(
        description=(
            "Detect exact duplicate directory trees on the external drive "
            "using migrate_v2's SQLite metadata."
        )
    )
    parser.add_argument(
        "--db-path",
        default=config_module.STATE_DB_PATH,
        help="Path to migration state SQLite DB (default: %(default)s).",
    )
    parser.add_argument(
        "--base-path",
        default=config_module.LOCAL_BASE_PATH,
        help="Root of the external drive (default: %(default)s).",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore cached duplicate analysis and recompute from scratch.",
    )
    parser.add_argument(
        "--min-files",
        type=int,
        default=MIN_REPORT_FILES,
        help="Minimum files per directory to include (default: %(default)s).",
    )
    parser.add_argument(
        "--min-size-gb",
        type=float,
        default=MIN_REPORT_BYTES / (1024**3),
        help="Minimum directory size (GiB) to include (default: %(default).2f).",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help=(
            "After reporting duplicates, delete every directory except the first entry "
            "in each cluster (requires confirmation)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the duplicate tree report workflow."""
    args = parse_args(argv)
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"State DB not found at {db_path}. Run migrate_v2 first.", file=sys.stderr)
        return 1
    base_path = Path(args.base_path)
    min_files = max(0, args.min_files)
    min_bytes = max(0, int(args.min_size_gb * (1024**3)))
    print(f"Using database: {db_path}")
    print(f"Assumed drive root: {base_path}")
    index, fingerprint = build_directory_index_from_db(str(db_path))
    base_path_str = str(base_path)
    can_cache_results = args.min_files == MIN_REPORT_FILES and min_bytes == MIN_REPORT_BYTES
    use_cache = (not args.refresh_cache) and can_cache_results
    cached_report = None
    if use_cache:
        cached_report = load_cached_report(
            str(db_path), fingerprint, base_path_str, min_files, min_bytes
        )
    clusters: Optional[Sequence[DuplicateCluster]] = None
    cluster_rows: Optional[List[ClusterRow]] = None
    if cached_report:
        print(
            "Using cached duplicate analysis from "
            f"{cached_report['generated_at']} "
            f"({int(cached_report['total_files']):,} files)."
        )
        if "rows" in cached_report:
            cluster_rows = cached_report["rows"]
            report_text = _render_report_rows(cluster_rows, base_path)
        else:
            report_text = cached_report["report"]
    else:
        clusters = find_exact_duplicates(index)
        clusters = _apply_thresholds(clusters, min_files, min_bytes)
        clusters = sorted(
            clusters, key=lambda c: c.nodes[0].total_size if c.nodes else 0, reverse=True
        )
        cluster_rows = _clusters_to_rows(clusters)
        report_text = _render_report_rows(cluster_rows, base_path)
        if can_cache_results:
            store_cached_report(
                str(db_path), fingerprint, base_path_str, clusters, min_files, min_bytes
            )
    if report_text:
        print(report_text, end="" if report_text.endswith("\n") else "\n")
    if args.delete:
        if cluster_rows is None:
            print(
                "Cached report lacks structured duplicate data. "
                "Recomputing duplicates to prepare deletion plan..."
            )
            clusters = find_exact_duplicates(index)
            clusters = _apply_thresholds(clusters, min_files, min_bytes)
            clusters = sorted(
                clusters,
                key=lambda c: c.nodes[0].total_size if c.nodes else 0,
                reverse=True,
            )
            cluster_rows = _clusters_to_rows(clusters)
        _delete_duplicate_directories(cluster_rows or [], base_path)
    print("Done.")
    return 0


def _apply_thresholds(
    clusters: Sequence[DuplicateCluster], min_files: int, min_bytes: int
) -> List[DuplicateCluster]:
    """Filter clusters down to nodes meeting file and size thresholds."""
    filtered: List[DuplicateCluster] = []
    for cluster in clusters:
        nodes = [
            node
            for node in cluster.nodes
            if node.total_files > min_files and node.total_size >= min_bytes
        ]
        if len(nodes) >= 2:
            filtered.append(DuplicateCluster(cluster.signature, nodes))
    return filtered


def _cache_key(fingerprint: ScanFingerprint, min_files: int, min_bytes: int) -> str:
    return f"{fingerprint.checksum}|files>{min_files}|bytes>={min_bytes}"


def _clusters_to_rows(clusters: Sequence[DuplicateCluster]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for cluster in clusters:
        if not cluster.nodes:
            continue
        node_rows = [
            {
                "path": list(node.path),
                "total_files": node.total_files,
                "total_size": node.total_size,
            }
            for node in cluster.nodes
        ]
        rows.append(
            {
                "total_files": node_rows[0]["total_files"],
                "total_size": node_rows[0]["total_size"],
                "nodes": node_rows,
            }
        )
    return rows


def _render_report_rows(cluster_rows: List[ClusterRow], base_path: Path) -> str:
    buffer = io.StringIO()
    if not cluster_rows:
        buffer.write("No exact duplicate directories found.\n")
        return buffer.getvalue()
    buffer.write("\n")
    buffer.write("=" * 70 + "\n")
    buffer.write("EXACT DUPLICATE TREES\n")
    buffer.write("=" * 70 + "\n")
    for idx, cluster in enumerate(cluster_rows, start=1):
        size_label = _format_bytes(cluster["total_size"])
        buffer.write(f"[{idx}] {cluster['total_files']:,} files, {size_label}\n")
        nodes = _sort_node_rows(cluster["nodes"])
        for node in nodes:
            path_tuple = tuple(node["path"])
            buffer.write(
                f"  - {_format_bytes(node['total_size']):>12}  "
                f"{_path_on_disk(base_path, path_tuple)}\n"
            )
        buffer.write("\n")
    return buffer.getvalue()


def _format_bytes(num_bytes: int) -> str:
    units = ["bytes", "KiB", "MiB", "GiB", "TiB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:0.2f} {unit}"
        value /= 1024


def _sort_node_rows(node_rows: Sequence[NodeRow]) -> List[NodeRow]:
    """Sort node rows by size (desc) then path for deterministic output."""
    return sorted(
        node_rows,
        key=lambda n: (-n["total_size"], tuple(n["path"])),
    )


def _delete_duplicate_directories(cluster_rows: Sequence[ClusterRow], base_path: Path):
    """Delete every duplicate directory except the first entry in each cluster."""
    deletion_groups = []
    total_bytes = 0
    total_dirs = 0
    for idx, cluster in enumerate(cluster_rows, start=1):
        nodes = _sort_node_rows(cluster["nodes"])
        if len(nodes) < 2:
            continue
        keep_node = nodes[0]
        delete_nodes = nodes[1:]
        deletion_groups.append((idx, keep_node, delete_nodes))
        total_bytes += sum(node["total_size"] for node in delete_nodes)
        total_dirs += len(delete_nodes)
    if not deletion_groups:
        print("No duplicate directories meet the delete criteria.")
        return
    print("\nDeletion plan (keeping the first directory shown per cluster):")
    for cluster_idx, keep_node, delete_nodes in deletion_groups:
        keep_path = _path_on_disk(base_path, tuple(keep_node["path"]))
        print(f"[{cluster_idx}] Keep {keep_path}")
        for node in delete_nodes:
            delete_path = _path_on_disk(base_path, tuple(node["path"]))
            print(f"    delete {_format_bytes(node['total_size']):>12}  {delete_path}")
        print()
    prompt = f"Delete {total_dirs} directories " f"({ _format_bytes(total_bytes) })? [y/N]: "
    try:
        response = input(prompt)
    except EOFError:
        print("\nConfirmation not received; skipping deletion.")
        return
    if response.strip().lower() not in {"y", "yes"}:
        print("Deletion cancelled.")
        return
    errors: List[tuple[Path, Exception]] = []
    for _, _, delete_nodes in deletion_groups:
        for node in delete_nodes:
            path = _path_on_disk(base_path, tuple(node["path"]))
            if not path.exists():
                print(f"Skipping missing directory: {path}")
                continue
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink()
                else:
                    shutil.rmtree(path)
                print(f"Deleted {path}")
            except Exception as exc:  # pylint: disable=broad-except
                errors.append((path, exc))
                print(f"Error deleting {path}: {exc}")
    if errors:
        print(f"Completed with {len(errors)} error(s).")
    else:
        print("Deletion complete.")


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except KeyboardInterrupt as exc:
        print("\n✗ Duplicate tree analysis interrupted by user.", file=sys.stderr)
        raise SystemExit(130) from exc
