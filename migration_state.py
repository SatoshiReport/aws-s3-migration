"""
State management for S3 migration using SQLite.
Tracks every file through its lifecycle: discovery, download, verification, deletion.
"""
import sqlite3
import json
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple
from contextlib import contextmanager


class FileState:
    """File processing states"""
    DISCOVERED = "discovered"
    GLACIER_RESTORE_REQUESTED = "glacier_restore_requested"
    GLACIER_RESTORING = "glacier_restoring"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    VERIFIED = "verified"
    DELETED = "deleted"
    ERROR = "error"


class MigrationState:
    """
    Manages migration state in SQLite database.
    Provides resilient state tracking for S3 to local migration.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()  # Thread safety for concurrent operations
        self._batch_updates = []  # Queue for batched database updates
        self._init_database()

    def _init_database(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    bucket TEXT NOT NULL,
                    key TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    etag TEXT,
                    storage_class TEXT,
                    last_modified TEXT,
                    local_path TEXT,
                    state TEXT NOT NULL,
                    error_message TEXT,
                    checksum TEXT,
                    glacier_restore_requested_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (bucket, key)
                )
            """)

            # Track bucket scan completion
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scanned_buckets (
                    bucket TEXT PRIMARY KEY,
                    file_count INTEGER NOT NULL,
                    total_size INTEGER NOT NULL,
                    scanned_at TEXT NOT NULL
                )
            """)

            # Track migration metadata (start time, end time, etc.)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS migration_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Create indices for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_state
                ON files(state)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_storage_class
                ON files(storage_class)
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections with thread-safe timeout"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def add_file(self, bucket: str, key: str, size: int, etag: str,
                 storage_class: str, last_modified: str):
        """
        Add a discovered file to tracking database.
        If file exists, skip (idempotent).
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            try:
                conn.execute("""
                    INSERT INTO files
                    (bucket, key, size, etag, storage_class, last_modified,
                     state, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (bucket, key, size, etag, storage_class, last_modified,
                      FileState.DISCOVERED, now, now))
                conn.commit()
            except sqlite3.IntegrityError:
                # File already exists, skip
                pass

    def update_state(self, bucket: str, key: str, state: str,
                     error_message: Optional[str] = None,
                     local_path: Optional[str] = None,
                     checksum: Optional[str] = None,
                     batch: bool = False):
        """
        Update file state.

        Args:
            batch: If True, queue the update for batch commit. Call flush_batch_updates() to commit.
        """
        now = datetime.now(timezone.utc).isoformat()

        if batch:
            # Queue for batch commit
            with self._lock:
                self._batch_updates.append({
                    'bucket': bucket,
                    'key': key,
                    'state': state,
                    'error_message': error_message,
                    'local_path': local_path,
                    'checksum': checksum,
                    'updated_at': now
                })
            return

        # Immediate commit
        with self._lock:
            with self._get_connection() as conn:
                updates = ["state = ?", "updated_at = ?"]
                values = [state, now]

                if error_message is not None:
                    updates.append("error_message = ?")
                    values.append(error_message)

                if local_path is not None:
                    updates.append("local_path = ?")
                    values.append(local_path)

                if checksum is not None:
                    updates.append("checksum = ?")
                    values.append(checksum)

                values.extend([bucket, key])

                conn.execute(f"""
                    UPDATE files
                    SET {", ".join(updates)}
                    WHERE bucket = ? AND key = ?
                """, values)
                conn.commit()

    def flush_batch_updates(self):
        """
        Commit all queued batch updates to database.
        Thread-safe and efficient for bulk operations.
        """
        with self._lock:
            if not self._batch_updates:
                return

            updates_to_commit = self._batch_updates[:]
            self._batch_updates.clear()

        # Commit outside the lock to reduce contention
        with self._get_connection() as conn:
            for update in updates_to_commit:
                updates = ["state = ?", "updated_at = ?"]
                values = [update['state'], update['updated_at']]

                if update['error_message'] is not None:
                    updates.append("error_message = ?")
                    values.append(update['error_message'])

                if update['local_path'] is not None:
                    updates.append("local_path = ?")
                    values.append(update['local_path'])

                if update['checksum'] is not None:
                    updates.append("checksum = ?")
                    values.append(update['checksum'])

                values.extend([update['bucket'], update['key']])

                conn.execute(f"""
                    UPDATE files
                    SET {", ".join(updates)}
                    WHERE bucket = ? AND key = ?
                """, values)

            conn.commit()

    def mark_glacier_restore_requested(self, bucket: str, key: str):
        """Mark that Glacier restore has been requested"""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE files
                    SET state = ?,
                        glacier_restore_requested_at = ?,
                        updated_at = ?
                    WHERE bucket = ? AND key = ?
                """, (FileState.GLACIER_RESTORE_REQUESTED, now, now, bucket, key))
                conn.commit()

    def get_files_by_state(self, state: str, limit: Optional[int] = None) -> List[Dict]:
        """Get all files in a specific state"""
        query = "SELECT * FROM files WHERE state = ?"
        if limit:
            query += f" LIMIT {limit}"

        with self._get_connection() as conn:
            cursor = conn.execute(query, (state,))
            return [dict(row) for row in cursor.fetchall()]


    def get_files_by_states(self, states: List[str]) -> List[Dict]:
        """Get all files in any of the specified states"""
        placeholders = ",".join("?" * len(states))
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM files WHERE state IN ({placeholders})",
                states
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_glacier_files_to_check(self) -> List[Dict]:
        """Get Glacier files that need restore status check"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM files
                WHERE state IN (?, ?)
            """, (FileState.GLACIER_RESTORE_REQUESTED, FileState.GLACIER_RESTORING))
            return [dict(row) for row in cursor.fetchall()]

    def get_file(self, bucket: str, key: str) -> Optional[Dict]:
        """Get specific file information"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM files WHERE bucket = ? AND key = ?
            """, (bucket, key))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_statistics(self) -> Dict:
        """Get migration statistics"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    state,
                    COUNT(*) as count,
                    SUM(size) as total_size
                FROM files
                GROUP BY state
            """)

            stats = {}
            for row in cursor.fetchall():
                stats[row['state']] = {
                    'count': row['count'],
                    'size': row['total_size'] or 0
                }

            # Get totals
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_files,
                    SUM(size) as total_size
                FROM files
            """)
            totals = cursor.fetchone()

            stats['total'] = {
                'count': totals['total_files'],
                'size': totals['total_size'] or 0
            }

            return stats

    def get_storage_class_breakdown(self, state: str = None) -> Dict:
        """
        Get breakdown by storage class, optionally filtered by state.
        Fast query that doesn't require sampling.
        """
        with self._get_connection() as conn:
            if state:
                cursor = conn.execute("""
                    SELECT
                        storage_class,
                        COUNT(*) as count,
                        SUM(size) as total_size
                    FROM files
                    WHERE state = ?
                    GROUP BY storage_class
                """, (state,))
            else:
                cursor = conn.execute("""
                    SELECT
                        storage_class,
                        COUNT(*) as count,
                        SUM(size) as total_size
                    FROM files
                    GROUP BY storage_class
                """)

            breakdown = {}
            for row in cursor.fetchall():
                breakdown[row['storage_class']] = {
                    'count': row['count'],
                    'size': row['total_size'] or 0
                }

            return breakdown

    def get_progress(self) -> Tuple[int, int, int, int]:
        """
        Get progress information.
        Returns: (completed_files, total_files, completed_bytes, total_bytes)
        """
        with self._get_connection() as conn:
            # Total
            cursor = conn.execute("""
                SELECT COUNT(*) as count, SUM(size) as size FROM files
            """)
            row = cursor.fetchone()
            total_files = row['count']
            total_bytes = row['size'] or 0

            # Completed (deleted means successfully moved)
            cursor = conn.execute("""
                SELECT COUNT(*) as count, SUM(size) as size
                FROM files WHERE state = ?
            """, (FileState.DELETED,))
            row = cursor.fetchone()
            completed_files = row['count']
            completed_bytes = row['size'] or 0

            return completed_files, total_files, completed_bytes, total_bytes

    def has_files_to_process(self) -> bool:
        """Check if there are any files not yet deleted"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM files
                WHERE state != ?
            """, (FileState.DELETED,))
            return cursor.fetchone()['count'] > 0

    def get_buckets(self) -> List[str]:
        """Get list of all buckets in the database"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT bucket FROM files ORDER BY bucket
            """)
            return [row['bucket'] for row in cursor.fetchall()]

    def get_migration_start_time(self) -> Optional[str]:
        """Get the timestamp when migration started (earliest file added)"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT MIN(created_at) as start_time FROM files
            """)
            row = cursor.fetchone()
            return row['start_time'] if row else None

    def get_overall_stats(self) -> Dict:
        """
        Get overall migration statistics including timing.
        Returns dict with start_time, completed_count, total_count, etc.
        """
        with self._get_connection() as conn:
            # Get start time
            cursor = conn.execute("SELECT MIN(created_at) as start_time FROM files")
            start_time = cursor.fetchone()['start_time']

            # Get completion stats
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_files,
                    SUM(size) as total_bytes,
                    SUM(CASE WHEN state = ? THEN 1 ELSE 0 END) as completed_files,
                    SUM(CASE WHEN state = ? THEN size ELSE 0 END) as completed_bytes
                FROM files
            """, (FileState.DELETED, FileState.DELETED))

            row = cursor.fetchone()

            return {
                'start_time': start_time,
                'total_files': row['total_files'],
                'total_bytes': row['total_bytes'] or 0,
                'completed_files': row['completed_files'],
                'completed_bytes': row['completed_bytes'] or 0
            }

    def mark_bucket_scanned(self, bucket: str, file_count: int, total_size: int):
        """Mark a bucket as completely scanned"""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO scanned_buckets
                (bucket, file_count, total_size, scanned_at)
                VALUES (?, ?, ?, ?)
            """, (bucket, file_count, total_size, now))
            conn.commit()

    def is_bucket_scanned(self, bucket: str) -> bool:
        """Check if a bucket has been fully scanned"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT bucket FROM scanned_buckets WHERE bucket = ?
            """, (bucket,))
            return cursor.fetchone() is not None

    def get_scanned_buckets(self) -> List[Dict]:
        """Get list of all scanned buckets with their stats"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT bucket, file_count, total_size, scanned_at
                FROM scanned_buckets
                ORDER BY bucket
            """)
            return [dict(row) for row in cursor.fetchall()]

    def set_metadata(self, key: str, value: str):
        """Set a metadata value"""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO migration_metadata
                (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, now))
            conn.commit()

    def get_metadata(self, key: str) -> Optional[str]:
        """Get a metadata value"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT value FROM migration_metadata WHERE key = ?
            """, (key,))
            row = cursor.fetchone()
            return row['value'] if row else None

    def get_migration_runtime_info(self) -> Dict:
        """
        Get migration runtime information.
        Returns start time and completion stats for actual migration (not scan).
        """
        migration_start = self.get_metadata('migration_start_time')

        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_files,
                    SUM(size) as total_bytes,
                    SUM(CASE WHEN state = ? THEN 1 ELSE 0 END) as completed_files,
                    SUM(CASE WHEN state = ? THEN size ELSE 0 END) as completed_bytes
                FROM files
            """, (FileState.DELETED, FileState.DELETED))

            row = cursor.fetchone()

            return {
                'migration_start_time': migration_start,
                'total_files': row['total_files'],
                'total_bytes': row['total_bytes'] or 0,
                'completed_files': row['completed_files'],
                'completed_bytes': row['completed_bytes'] or 0
            }
