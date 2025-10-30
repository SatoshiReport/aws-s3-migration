"""
State management for S3 migration V2 using SQLite.
Enhanced with bucket-level tracking and phase management.
"""
import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional, Dict, List
from contextlib import contextmanager
from enum import Enum


class Phase(Enum):
    """Migration phases"""
    SCANNING = "scanning"
    GLACIER_RESTORE = "glacier_restore"
    GLACIER_WAIT = "glacier_wait"
    SYNCING = "syncing"
    VERIFYING = "verifying"
    DELETING = "deleting"
    COMPLETE = "complete"


class BucketStatus:
    """Bucket processing status"""
    def __init__(self, row: Dict):
        self.bucket = row['bucket']
        self.file_count = row['file_count']
        self.total_size = row['total_size']
        self.storage_classes = json.loads(row['storage_class_counts']) if row['storage_class_counts'] else {}
        self.scan_complete = bool(row['scan_complete'])
        self.sync_complete = bool(row['sync_complete'])
        self.verify_complete = bool(row['verify_complete'])
        self.delete_complete = bool(row['delete_complete'])


class MigrationStateV2:
    """
    Enhanced migration state management with bucket-level tracking.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            # Files table (same as before with additions)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    bucket TEXT NOT NULL,
                    key TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    etag TEXT,
                    storage_class TEXT,
                    last_modified TEXT,
                    local_path TEXT,
                    local_checksum TEXT,
                    state TEXT NOT NULL,
                    error_message TEXT,
                    glacier_restore_requested_at TEXT,
                    glacier_restored_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (bucket, key)
                )
            """)

            # Bucket status table (NEW)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bucket_status (
                    bucket TEXT PRIMARY KEY,
                    file_count INTEGER NOT NULL,
                    total_size INTEGER NOT NULL,
                    storage_class_counts TEXT,
                    scan_complete BOOLEAN DEFAULT 0,
                    sync_complete BOOLEAN DEFAULT 0,
                    verify_complete BOOLEAN DEFAULT 0,
                    delete_complete BOOLEAN DEFAULT 0,
                    local_file_count INTEGER,
                    local_total_size INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Migration metadata table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS migration_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Create indices
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_files_state
                ON files(state)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_files_storage_class
                ON files(storage_class)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_files_bucket
                ON files(bucket)
            """)

            conn.commit()

            # Initialize current phase if not set
            cursor = conn.execute(
                "SELECT value FROM migration_metadata WHERE key = 'current_phase'"
            )
            if not cursor.fetchone():
                self.set_current_phase(Phase.SCANNING)

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def add_file(self, bucket: str, key: str, size: int, etag: str,
                 storage_class: str, last_modified: str):
        """Add a discovered file to tracking database (idempotent)"""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            try:
                conn.execute("""
                    INSERT INTO files
                    (bucket, key, size, etag, storage_class, last_modified,
                     state, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'discovered', ?, ?)
                """, (bucket, key, size, etag, storage_class, last_modified, now, now))
                conn.commit()
            except sqlite3.IntegrityError:
                # File already exists, skip
                pass

    def save_bucket_status(self, bucket: str, file_count: int, total_size: int,
                          storage_classes: Dict[str, int], scan_complete: bool = False):
        """Save or update bucket status"""
        now = datetime.now(timezone.utc).isoformat()
        storage_json = json.dumps(storage_classes)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO bucket_status
                (bucket, file_count, total_size, storage_class_counts, scan_complete,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, COALESCE(
                    (SELECT created_at FROM bucket_status WHERE bucket = ?), ?
                ), ?)
            """, (bucket, file_count, total_size, storage_json, scan_complete, bucket, now, now))
            conn.commit()

    def mark_bucket_sync_complete(self, bucket: str):
        """Mark bucket as synced"""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE bucket_status
                SET sync_complete = 1, updated_at = ?
                WHERE bucket = ?
            """, (now, bucket))
            conn.commit()

    def mark_bucket_verify_complete(self, bucket: str):
        """Mark bucket as verified"""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE bucket_status
                SET verify_complete = 1, updated_at = ?
                WHERE bucket = ?
            """, (now, bucket))
            conn.commit()

    def mark_bucket_delete_complete(self, bucket: str):
        """Mark bucket as deleted from S3"""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE bucket_status
                SET delete_complete = 1, updated_at = ?
                WHERE bucket = ?
            """, (now, bucket))
            conn.commit()

    def mark_glacier_restore_requested(self, bucket: str, key: str):
        """Mark that Glacier restore has been requested"""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE files
                SET glacier_restore_requested_at = ?, updated_at = ?
                WHERE bucket = ? AND key = ?
            """, (now, now, bucket, key))
            conn.commit()

    def mark_glacier_restored(self, bucket: str, key: str):
        """Mark that Glacier restore is complete"""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE files
                SET glacier_restored_at = ?, updated_at = ?
                WHERE bucket = ? AND key = ?
            """, (now, now, bucket, key))
            conn.commit()

    def get_current_phase(self) -> Phase:
        """Get current migration phase"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM migration_metadata WHERE key = 'current_phase'"
            )
            row = cursor.fetchone()
            if row:
                return Phase(row['value'])
            return Phase.SCANNING

    def set_current_phase(self, phase: Phase):
        """Set current migration phase"""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO migration_metadata
                (key, value, updated_at)
                VALUES ('current_phase', ?, ?)
            """, (phase.value, now))
            conn.commit()

    def get_all_buckets(self) -> List[str]:
        """Get list of all buckets"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT bucket FROM bucket_status
                ORDER BY bucket
            """)
            return [row['bucket'] for row in cursor.fetchall()]

    def get_completed_buckets_for_phase(self, phase_field: str) -> List[str]:
        """Get buckets that completed a specific phase"""
        with self._get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT bucket FROM bucket_status
                WHERE {phase_field} = 1
                ORDER BY bucket
            """)
            return [row['bucket'] for row in cursor.fetchall()]

    def get_bucket_info(self, bucket: str) -> Dict:
        """Get bucket information"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM bucket_status WHERE bucket = ?
            """, (bucket,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {}

    def get_glacier_files_needing_restore(self) -> List[Dict]:
        """Get Glacier files that need restore requests"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM files
                WHERE storage_class IN ('GLACIER', 'DEEP_ARCHIVE')
                AND glacier_restore_requested_at IS NULL
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_files_restoring(self) -> List[Dict]:
        """Get files currently being restored"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM files
                WHERE storage_class IN ('GLACIER', 'DEEP_ARCHIVE')
                AND glacier_restore_requested_at IS NOT NULL
                AND glacier_restored_at IS NULL
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_scan_summary(self) -> Dict:
        """Get summary of scanned buckets"""
        with self._get_connection() as conn:
            # Get bucket count and totals
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as bucket_count,
                    SUM(file_count) as total_files,
                    SUM(total_size) as total_size
                FROM bucket_status
                WHERE scan_complete = 1
            """)
            row = cursor.fetchone()

            # Get storage class breakdown
            cursor = conn.execute("""
                SELECT storage_class, COUNT(*) as count
                FROM files
                GROUP BY storage_class
            """)
            storage_classes = {row['storage_class']: row['count'] for row in cursor.fetchall()}

            return {
                'bucket_count': row['bucket_count'] or 0,
                'total_files': row['total_files'] or 0,
                'total_size': row['total_size'] or 0,
                'storage_classes': storage_classes
            }
