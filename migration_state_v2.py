"""State management for S3 migration V2 using SQLite
with bucket-level tracking and phase management."""

import json
import sqlite3
from contextlib import contextmanager
from enum import Enum
from typing import Dict, List


class Phase(Enum):
    """Migration phases"""

    SCANNING = "scanning"
    GLACIER_RESTORE = "glacier_restore"
    GLACIER_WAIT = "glacier_wait"
    SYNCING = "syncing"
    VERIFYING = "verifying"
    DELETING = "deleting"
    COMPLETE = "complete"


class BucketStatus:  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """Bucket processing status"""

    def __init__(self, row: Dict):
        self.bucket = row["bucket"]
        self.file_count = row["file_count"]
        self.total_size = row["total_size"]
        self.storage_classes = (
            json.loads(row["storage_class_counts"]) if row["storage_class_counts"] else {}
        )
        self.scan_complete = bool(row["scan_complete"])
        self.sync_complete = bool(row["sync_complete"])
        self.verify_complete = bool(row["verify_complete"])
        self.delete_complete = bool(row["delete_complete"])


class DatabaseConnection:  # pylint: disable=too-few-public-methods
    """Handles database connection and schema initialization"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            self._create_tables(conn)
            self._create_indices(conn)
            self._migrate_existing_schema(conn)
            conn.commit()

    def _create_tables(self, conn):
        """Create database tables"""
        conn.execute(
            """
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
        """
        )
        conn.execute(
            """
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
                verified_file_count INTEGER,
                size_verified_count INTEGER,
                checksum_verified_count INTEGER,
                total_bytes_verified INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS migration_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """
        )

    def _create_indices(self, conn):
        """Create database indices"""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_state ON files(state)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_storage_class ON files(storage_class)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_bucket ON files(bucket)")

    def _migrate_existing_schema(self, conn):
        """Add new columns to existing databases"""
        columns = [
            "verified_file_count INTEGER",
            "size_verified_count INTEGER",
            "checksum_verified_count INTEGER",
            "total_bytes_verified INTEGER",
        ]
        for column in columns:
            try:
                conn.execute(f"ALTER TABLE bucket_status ADD COLUMN {column}")
            except sqlite3.OperationalError:
                pass


class MigrationStateV2:
    """
    Enhanced migration state management with bucket-level tracking.
    Thin coordinator delegating to specialized managers.
    """

    def __init__(self, db_path: str):
        # pylint: disable=import-outside-toplevel
        from migration_state_managers import BucketStateManager, FileStateManager, PhaseManager

        self.db_conn = DatabaseConnection(db_path)
        self.files = FileStateManager(self.db_conn)
        self.buckets = BucketStateManager(self.db_conn)
        self.phases = PhaseManager(self.db_conn)

    # File operations
    def add_file(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, bucket: str, key: str, size: int, etag: str, storage_class: str, last_modified: str
    ):
        """Add a discovered file"""
        self.files.add_file(bucket, key, size, etag, storage_class, last_modified)

    def mark_glacier_restore_requested(self, bucket: str, key: str):
        """Mark Glacier restore requested"""
        self.files.mark_glacier_restore_requested(bucket, key)

    def mark_glacier_restored(self, bucket: str, key: str):
        """Mark Glacier restore complete"""
        self.files.mark_glacier_restored(bucket, key)

    def get_glacier_files_needing_restore(self) -> List[Dict]:
        """Get Glacier files needing restore"""
        return self.files.get_glacier_files_needing_restore()

    def get_files_restoring(self) -> List[Dict]:
        """Get files currently restoring"""
        return self.files.get_files_restoring()

    # Bucket operations
    def save_bucket_status(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        bucket: str,
        file_count: int,
        total_size: int,
        storage_classes: Dict[str, int],
        scan_complete: bool = False,
    ):
        """Save bucket status"""
        self.buckets.save_bucket_status(
            bucket, file_count, total_size, storage_classes, scan_complete
        )

    def mark_bucket_sync_complete(self, bucket: str):
        """Mark bucket synced"""
        self.buckets.mark_bucket_sync_complete(bucket)

    def mark_bucket_verify_complete(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        bucket: str,
        verified_file_count: int = None,
        size_verified_count: int = None,
        checksum_verified_count: int = None,
        total_bytes_verified: int = None,
        local_file_count: int = None,
    ):
        """Mark bucket verified"""
        self.buckets.mark_bucket_verify_complete(
            bucket,
            verified_file_count,
            size_verified_count,
            checksum_verified_count,
            total_bytes_verified,
            local_file_count,
        )

    def mark_bucket_delete_complete(self, bucket: str):
        """Mark bucket deleted"""
        self.buckets.mark_bucket_delete_complete(bucket)

    def get_all_buckets(self) -> List[str]:
        """Get all buckets"""
        return self.buckets.get_all_buckets()

    def get_completed_buckets_for_phase(self, phase_field: str) -> List[str]:
        """Get completed buckets for phase"""
        return self.buckets.get_completed_buckets_for_phase(phase_field)

    def get_bucket_info(self, bucket: str) -> Dict:
        """Get bucket info"""
        return self.buckets.get_bucket_info(bucket)

    def get_scan_summary(self) -> Dict:
        """Get scan summary"""
        return self.buckets.get_scan_summary()

    # Phase operations
    def get_current_phase(self) -> Phase:
        """Get current phase"""
        return self.phases.get_phase()

    def set_current_phase(self, phase: Phase):
        """Set current phase"""
        self.phases.set_phase(phase)
