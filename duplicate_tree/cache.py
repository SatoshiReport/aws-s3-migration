"""Cache management for duplicate tree analysis results."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Sequence, TypedDict, cast

from duplicate_tree.analysis import (
    MIN_REPORT_BYTES,
    MIN_REPORT_FILES,
    ClusterRow,
    ScanFingerprint,
    cache_key,
    clusters_to_rows,
)
from duplicate_tree.core import DuplicateCluster

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


class CachedReportBase(TypedDict):
    """Common metadata for cached duplicate analysis reports."""

    generated_at: str
    total_files: str


class CachedRowsReport(CachedReportBase):
    """Cached report containing parsed cluster rows."""

    rows: list[ClusterRow]


class CachedRawReport(CachedReportBase):
    """Cached report containing the raw JSON payload."""

    rows: list[ClusterRow]
    report: str


CachedReport = CachedRowsReport | CachedRawReport


def ensure_cache_table(conn: sqlite3.Connection):
    """Create cache table if it doesn't exist."""
    conn.execute(CACHE_TABLE_SQL)
    conn.commit()


def load_cached_report(
    db_path: str,
    fingerprint: ScanFingerprint,
    base_path: str,
    min_files: int = MIN_REPORT_FILES,
    min_bytes: int = MIN_REPORT_BYTES,
) -> Optional[CachedReport]:
    """Return cached report metadata if it matches the current snapshot."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_cache_table(conn)
        key = cache_key(fingerprint, min_files, min_bytes)
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
            rows = cast(list[ClusterRow], json.loads(payload))
            return {
                "generated_at": row["generated_at"],
                "rows": rows,
                "total_files": str(row["total_files"]),
            }
        except json.JSONDecodeError:
            print(
                f"⚠️  Cached report has corrupted JSON payload. Generated at: {row['generated_at']}"
            )
            return {
                "generated_at": row["generated_at"],
                "rows": [],
                "total_files": str(row["total_files"]),
                "report": payload,
            }
    finally:
        conn.close()


def store_cached_report(  # pylint: disable=too-many-positional-arguments  # cache key requires all params
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
        ensure_cache_table(conn)
        key = cache_key(fingerprint, min_files, min_bytes)
        payload = json.dumps(clusters_to_rows(clusters))
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
