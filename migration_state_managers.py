"""State manager classes for file, bucket, and phase operations"""

import sqlite3
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from migration_state_v2 import DatabaseConnection, Phase


class FileStateManager:
    """Manages file-level state operations"""

    def __init__(self, db_conn: "DatabaseConnection"):
        self.db_conn = db_conn

    def add_file(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, bucket: str, key: str, size: int, etag: str, storage_class: str, last_modified: str
    ):
        """Add a discovered file to tracking database (idempotent)"""
        now = datetime.now(timezone.utc).isoformat()
        with self.db_conn.get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO files
                    (bucket, key, size, etag, storage_class, last_modified,
                     state, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'discovered', ?, ?)
                """,
                    (bucket, key, size, etag, storage_class, last_modified, now, now),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # File already exists

    def mark_glacier_restore_requested(self, bucket: str, key: str):
        """Mark that Glacier restore has been requested"""
        now = datetime.now(timezone.utc).isoformat()
        with self.db_conn.get_connection() as conn:
            conn.execute(
                """UPDATE files SET glacier_restore_requested_at = ?,
                updated_at = ? WHERE bucket = ? AND key = ?""",
                (now, now, bucket, key),
            )
            conn.commit()

    def mark_glacier_restored(self, bucket: str, key: str):
        """Mark that Glacier restore is complete"""
        now = datetime.now(timezone.utc).isoformat()
        with self.db_conn.get_connection() as conn:
            conn.execute(
                """UPDATE files SET glacier_restored_at = ?,
                updated_at = ? WHERE bucket = ? AND key = ?""",
                (now, now, bucket, key),
            )
            conn.commit()

    def get_glacier_files_needing_restore(self) -> List[Dict]:
        """Get Glacier files that need restore requests"""
        with self.db_conn.get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM files WHERE storage_class IN ('GLACIER', 'DEEP_ARCHIVE')
                AND glacier_restore_requested_at IS NULL"""
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_files_restoring(self) -> List[Dict]:
        """Get files currently being restored"""
        with self.db_conn.get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM files WHERE storage_class IN ('GLACIER', 'DEEP_ARCHIVE')
                AND glacier_restore_requested_at IS NOT NULL
                AND glacier_restored_at IS NULL"""
            )
            return [dict(row) for row in cursor.fetchall()]


class BucketStateManager:
    """Manages bucket-level state operations"""

    def __init__(self, db_conn: "DatabaseConnection"):
        self.db_conn = db_conn

    def save_bucket_status(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        bucket: str,
        file_count: int,
        total_size: int,
        storage_classes: Dict[str, int],
        scan_complete: bool = False,
    ):
        """Save or update bucket status"""
        import json  # pylint: disable=import-outside-toplevel

        now = datetime.now(timezone.utc).isoformat()
        storage_json = json.dumps(storage_classes)
        with self.db_conn.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO bucket_status
                (bucket, file_count, total_size, storage_class_counts,
                scan_complete, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?,
                COALESCE((SELECT created_at FROM bucket_status WHERE bucket = ?), ?), ?)""",
                (bucket, file_count, total_size, storage_json, scan_complete, bucket, now, now),
            )
            conn.commit()

    def mark_bucket_sync_complete(self, bucket: str):
        """Mark bucket as synced"""
        self._update_bucket_flag(bucket, "sync_complete")

    def mark_bucket_verify_complete(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        bucket: str,
        verified_file_count: int = None,
        size_verified_count: int = None,
        checksum_verified_count: int = None,
        total_bytes_verified: int = None,
        local_file_count: int = None,
    ):
        """Mark bucket as verified and store verification results"""
        now = datetime.now(timezone.utc).isoformat()
        with self.db_conn.get_connection() as conn:
            conn.execute(
                """UPDATE bucket_status SET verify_complete = 1, verified_file_count = ?,
                size_verified_count = ?, checksum_verified_count = ?, total_bytes_verified = ?,
                local_file_count = ?, updated_at = ? WHERE bucket = ?""",
                (
                    verified_file_count,
                    size_verified_count,
                    checksum_verified_count,
                    total_bytes_verified,
                    local_file_count,
                    now,
                    bucket,
                ),
            )
            conn.commit()

    def mark_bucket_delete_complete(self, bucket: str):
        """Mark bucket as deleted from S3"""
        self._update_bucket_flag(bucket, "delete_complete")

    def _update_bucket_flag(self, bucket: str, flag_name: str):
        """Helper to update a boolean flag"""
        now = datetime.now(timezone.utc).isoformat()
        with self.db_conn.get_connection() as conn:
            conn.execute(
                f"UPDATE bucket_status SET {flag_name} = 1, updated_at = ? WHERE bucket = ?",
                (now, bucket),
            )
            conn.commit()

    def get_all_buckets(self) -> List[str]:
        """Get list of all buckets"""
        with self.db_conn.get_connection() as conn:
            return [
                r["bucket"]
                for r in conn.execute("SELECT bucket FROM bucket_status ORDER BY bucket")
            ]

    def get_completed_buckets_for_phase(self, phase_field: str) -> List[str]:
        """Get buckets that completed a specific phase"""
        with self.db_conn.get_connection() as conn:
            return [
                r["bucket"]
                for r in conn.execute(
                    f"SELECT bucket FROM bucket_status WHERE {phase_field} = 1 ORDER BY bucket"
                )
            ]

    def get_bucket_info(self, bucket: str) -> Dict:
        """Get bucket information"""
        with self.db_conn.get_connection() as conn:
            row = conn.execute("SELECT * FROM bucket_status WHERE bucket = ?", (bucket,)).fetchone()
            return dict(row) if row else {}

    def get_scan_summary(self) -> Dict:
        """Get summary of scanned buckets"""
        with self.db_conn.get_connection() as conn:
            cursor = conn.execute(
                """SELECT COUNT(*) as bucket_count,
                COALESCE(SUM(file_count), 0) as total_files,
                COALESCE(SUM(total_size), 0) as total_size
                FROM bucket_status WHERE scan_complete = 1"""
            )
            row = cursor.fetchone()
            cursor = conn.execute(
                "SELECT storage_class, COUNT(*) as count FROM files GROUP BY storage_class"
            )
            storage_classes = {r["storage_class"]: r["count"] for r in cursor.fetchall()}
            return {
                "bucket_count": row["bucket_count"],
                "total_files": row["total_files"],
                "total_size": row["total_size"],
                "storage_classes": storage_classes,
            }


class PhaseManager:
    """Manages migration phase tracking"""

    def __init__(self, db_conn: "DatabaseConnection"):
        self.db_conn = db_conn
        self._init_phase()

    def _init_phase(self):
        """Initialize phase if not set"""
        from migration_state_v2 import Phase  # pylint: disable=import-outside-toplevel

        with self.db_conn.get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM migration_metadata WHERE key = 'current_phase'"
            )
            if not cursor.fetchone():
                self.set_phase(Phase.SCANNING)

    def get_phase(self) -> "Phase":
        """Get current migration phase"""
        from migration_state_v2 import Phase  # pylint: disable=import-outside-toplevel

        with self.db_conn.get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM migration_metadata WHERE key = 'current_phase'"
            )
            row = cursor.fetchone()
            return Phase(row["value"]) if row else Phase.SCANNING

    def set_phase(self, phase: "Phase"):
        """Set current migration phase"""
        now = datetime.now(timezone.utc).isoformat()
        with self.db_conn.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO migration_metadata
                (key, value, updated_at) VALUES ('current_phase', ?, ?)""",
                (phase.value, now),
            )
            conn.commit()
