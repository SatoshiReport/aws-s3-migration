"""CLI workflow for duplicate tree analysis."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Sequence

try:  # Prefer package-relative imports when packaged
    from . import config as config_module  # type: ignore
    from .duplicate_tree_core import (
        DirectoryIndex,
        DuplicateCluster,
        NearDuplicateReport,
        find_exact_duplicates,
        find_near_duplicates,
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
        NearDuplicateReport,
        find_exact_duplicates,
        find_near_duplicates,
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
    tolerance: float,
    base_path: str,
) -> Optional[Dict[str, str]]:
    """Return cached report metadata if it matches the current snapshot."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_cache_table(conn)
        row = conn.execute(
            """
            SELECT total_files, generated_at, report
            FROM duplicate_tree_cache
            WHERE fingerprint = ? AND tolerance = ? AND base_path = ?
            """,
            (fingerprint.checksum, tolerance, base_path),
        ).fetchone()
        if row is None:
            return None
        if row["total_files"] != fingerprint.total_files:
            return None
        return {
            "generated_at": row["generated_at"],
            "report": row["report"],
            "total_files": str(row["total_files"]),
        }
    finally:
        conn.close()


def store_cached_report(
    db_path: str,
    fingerprint: ScanFingerprint,
    tolerance: float,
    base_path: str,
    report_text: str,
):
    """Persist the latest duplicate analysis snapshot."""
    conn = sqlite3.connect(db_path)
    try:
        _ensure_cache_table(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO duplicate_tree_cache (
                fingerprint, tolerance, base_path, total_files, generated_at, report
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                fingerprint.checksum,
                tolerance,
                base_path,
                fingerprint.total_files,
                datetime.now(timezone.utc).isoformat(),
                report_text,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _path_on_disk(base_path: Path, node_path: PathTuple) -> Path:
    return base_path.joinpath(*node_path)


def _render_reports(
    clusters: Sequence[DuplicateCluster],
    near_duplicates: Sequence[NearDuplicateReport],
    base_path: Path,
) -> str:
    """Produce the textual report for caching/printing."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        _print_duplicate_clusters(clusters, base_path)
        _print_near_duplicates(near_duplicates, base_path)
    return buffer.getvalue()


def _print_duplicate_clusters(clusters: Sequence[DuplicateCluster], base_path: Path) -> None:
    if not clusters:
        print("No exact duplicate directories found.")
        return
    print()
    print("=" * 70)
    print("EXACT DUPLICATE TREES")
    print("=" * 70)
    for idx, cluster in enumerate(clusters, start=1):
        representative = cluster.nodes[0]
        print(f"[{idx}] {representative.total_files:,} files, {representative.total_size:,} bytes")
        for node in cluster.nodes:
            print(f"  - {_path_on_disk(base_path, node.path)}")
        print()


def _print_near_duplicates(reports: Sequence[NearDuplicateReport], base_path: Path) -> None:
    if not reports:
        print("No near-duplicate directories within tolerance.")
        return
    print("=" * 70)
    print("NEAR DUPLICATES WITH MINOR DELTAS")
    print("=" * 70)
    for idx, report in enumerate(reports, start=1):
        print(
            f"[{idx}] Similarity: {report.similarity*100:.2f}% | "
            f"Δ files: {report.file_delta:,}, Δ bytes: {report.size_delta:,}"
        )
        print(f"  A: {_path_on_disk(base_path, report.primary.path)}")
        print(f"  B: {_path_on_disk(base_path, report.secondary.path)}")
        for label, paths in report.differences.items():
            print(f"    {label.capitalize()}: {', '.join(paths)}")
        print()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments controlling database path, base path, and tolerance."""
    parser = argparse.ArgumentParser(
        description=(
            "Detect duplicate or near-duplicate directory trees on the external drive "
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
        "--tolerance",
        type=float,
        default=0.99,
        help="Minimum similarity ratio (0-1) to report near duplicates (default: 0.99).",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore cached duplicate analysis and recompute from scratch.",
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
    print(f"Using database: {db_path}")
    print(f"Assumed drive root: {base_path}")
    index, fingerprint = build_directory_index_from_db(str(db_path))
    base_path_str = str(base_path)
    cached_report = None
    if not args.refresh_cache:
        cached_report = load_cached_report(str(db_path), fingerprint, args.tolerance, base_path_str)
    if cached_report:
        print(
            "Using cached duplicate analysis from "
            f"{cached_report['generated_at']} "
            f"({int(cached_report['total_files']):,} files)."
        )
        report_text = cached_report["report"]
    else:
        clusters = find_exact_duplicates(index)
        near_duplicates = find_near_duplicates(index, tolerance=args.tolerance)
        report_text = _render_reports(clusters, near_duplicates, base_path)
        store_cached_report(
            str(db_path),
            fingerprint,
            args.tolerance,
            base_path_str,
            report_text,
        )
    if report_text:
        print(report_text, end="" if report_text.endswith("\n") else "\n")
    print("Done.")
    return 0


__all__ = [
    "build_directory_index_from_db",
    "load_cached_report",
    "main",
    "parse_args",
    "store_cached_report",
]


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except KeyboardInterrupt as exc:
        print("\n✗ Duplicate tree analysis interrupted by user.", file=sys.stderr)
        raise SystemExit(130) from exc
