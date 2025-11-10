"""Cache management for duplicate tree analysis results."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Optional, Sequence

try:  # Prefer package-relative imports when packaged
    from ..duplicate_tree_core import DuplicateCluster
    from .analysis import (
        MIN_REPORT_BYTES,
        MIN_REPORT_FILES,
        ScanFingerprint,
        cache_key,
        clusters_to_rows,
    )
except ImportError:  # pragma: no cover - execution as standalone script
    from analysis import (  # type: ignore
        MIN_REPORT_BYTES,
        MIN_REPORT_FILES,
        ScanFingerprint,
        cache_key,
        clusters_to_rows,
    )

    from duplicate_tree_core import DuplicateCluster  # type: ignore


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
) -> Optional[Dict[str, str]]:
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
