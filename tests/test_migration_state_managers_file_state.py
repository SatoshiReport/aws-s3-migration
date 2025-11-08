"""Unit tests for FileStateManager from migration_state_managers.py"""

from datetime import datetime, timezone

import pytest

from migration_state_managers import FileStateManager
from tests.assertions import assert_equal


class TestFileStateManagerFixtures:
    """Shared fixtures for FileStateManager tests"""

    @pytest.fixture
    def file_manager(self, db_conn):
        """Create FileStateManager instance"""
        return FileStateManager(db_conn)


class TestFileAddition(TestFileStateManagerFixtures):
    """Test add_file operations"""

    def test_add_file_inserts_file_record(self, file_manager, db_conn):
        """Test adding a file to the database"""
        file_manager.add_file(
            bucket="test-bucket",
            key="path/to/file.txt",
            size=1024,
            etag="abc123",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM files WHERE bucket = ? AND key = ?",
                ("test-bucket", "path/to/file.txt"),
            ).fetchone()

        assert row is not None
        assert row["bucket"] == "test-bucket"
        assert row["key"] == "path/to/file.txt"
        assert_equal(row["size"], 1024)
        assert row["etag"] == "abc123"
        assert row["storage_class"] == "STANDARD"
        assert row["state"] == "discovered"


class TestFileIdempotency(TestFileStateManagerFixtures):
    """Test file addition idempotency"""

    def test_add_file_is_idempotent(self, file_manager, db_conn):
        """Test that adding the same file twice doesn't raise an error"""
        file_manager.add_file(
            bucket="test-bucket",
            key="path/to/file.txt",
            size=1024,
            etag="abc123",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )

        file_manager.add_file(
            bucket="test-bucket",
            key="path/to/file.txt",
            size=1024,
            etag="abc123",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )

        with db_conn.get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM files WHERE bucket = ? AND key = ?",
                ("test-bucket", "path/to/file.txt"),
            ).fetchone()

        assert_equal(count["cnt"], 1)


class TestFileTimestamps(TestFileStateManagerFixtures):
    """Test file timestamp handling"""

    def test_add_file_sets_timestamps(self, file_manager, db_conn):
        """Test that created_at and updated_at are set"""
        before_time = datetime.now(timezone.utc).isoformat()
        file_manager.add_file(
            bucket="test-bucket",
            key="file.txt",
            size=100,
            etag="def456",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )
        after_time = datetime.now(timezone.utc).isoformat()

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT created_at, updated_at FROM files WHERE bucket = ? AND key = ?",
                ("test-bucket", "file.txt"),
            ).fetchone()

        assert row["created_at"] is not None
        assert row["updated_at"] is not None
        assert before_time <= row["created_at"] <= after_time


class TestGlacierRestoreRequest(TestFileStateManagerFixtures):
    """Test glacier restore request marking"""

    def test_mark_glacier_restore_requested(self, file_manager, db_conn):
        """Test marking a file for glacier restore"""
        file_manager.add_file(
            bucket="test-bucket",
            key="glacier-file.txt",
            size=5000,
            etag="ghi789",
            storage_class="GLACIER",
            last_modified="2024-01-01T00:00:00Z",
        )

        file_manager.mark_glacier_restore_requested("test-bucket", "glacier-file.txt")

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT glacier_restore_requested_at FROM files WHERE bucket = ? AND key = ?",
                ("test-bucket", "glacier-file.txt"),
            ).fetchone()

        assert row["glacier_restore_requested_at"] is not None


class TestGlacierRestoreCompletion(TestFileStateManagerFixtures):
    """Test glacier restore completion marking"""

    def test_mark_glacier_restored(self, file_manager, db_conn):
        """Test marking a file as restored from glacier"""
        file_manager.add_file(
            bucket="test-bucket",
            key="glacier-file.txt",
            size=5000,
            etag="ghi789",
            storage_class="GLACIER",
            last_modified="2024-01-01T00:00:00Z",
        )

        file_manager.mark_glacier_restore_requested("test-bucket", "glacier-file.txt")
        file_manager.mark_glacier_restored("test-bucket", "glacier-file.txt")

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT glacier_restored_at FROM files WHERE bucket = ? AND key = ?",
                ("test-bucket", "glacier-file.txt"),
            ).fetchone()

        assert row["glacier_restored_at"] is not None


class TestGlacierFilesNeedingRestore(TestFileStateManagerFixtures):
    """Test get_glacier_files_needing_restore query"""

    def test_get_glacier_files_needing_restore(self, file_manager, db_conn):
        """Test retrieving Glacier files that need restore"""
        file_manager.add_file(
            bucket="test-bucket",
            key="standard.txt",
            size=100,
            etag="std123",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )

        file_manager.add_file(
            bucket="test-bucket",
            key="glacier1.txt",
            size=1000,
            etag="glac1",
            storage_class="GLACIER",
            last_modified="2024-01-01T00:00:00Z",
        )

        file_manager.add_file(
            bucket="test-bucket",
            key="archive1.txt",
            size=2000,
            etag="arch1",
            storage_class="DEEP_ARCHIVE",
            last_modified="2024-01-01T00:00:00Z",
        )

        file_manager.add_file(
            bucket="test-bucket",
            key="glacier2.txt",
            size=1500,
            etag="glac2",
            storage_class="GLACIER",
            last_modified="2024-01-01T00:00:00Z",
        )
        file_manager.mark_glacier_restore_requested("test-bucket", "glacier2.txt")

        files = file_manager.get_glacier_files_needing_restore()

        keys = [f["key"] for f in files]
        assert "glacier1.txt" in keys
        assert "archive1.txt" in keys
        assert "glacier2.txt" not in keys
        assert "standard.txt" not in keys
        assert_equal(len(files), 2)


class TestFilesRestoring(TestFileStateManagerFixtures):
    """Test get_files_restoring query"""

    def test_get_files_restoring(self, file_manager, db_conn):
        """Test retrieving files currently being restored"""
        file_manager.add_file(
            bucket="test-bucket",
            key="standard.txt",
            size=100,
            etag="std123",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )

        file_manager.add_file(
            bucket="test-bucket",
            key="glacier1.txt",
            size=1000,
            etag="glac1",
            storage_class="GLACIER",
            last_modified="2024-01-01T00:00:00Z",
        )

        file_manager.add_file(
            bucket="test-bucket",
            key="glacier2.txt",
            size=1500,
            etag="glac2",
            storage_class="GLACIER",
            last_modified="2024-01-01T00:00:00Z",
        )
        file_manager.mark_glacier_restore_requested("test-bucket", "glacier2.txt")

        file_manager.add_file(
            bucket="test-bucket",
            key="glacier3.txt",
            size=2000,
            etag="glac3",
            storage_class="GLACIER",
            last_modified="2024-01-01T00:00:00Z",
        )
        file_manager.mark_glacier_restore_requested("test-bucket", "glacier3.txt")
        file_manager.mark_glacier_restored("test-bucket", "glacier3.txt")

        files = file_manager.get_files_restoring()

        keys = [f["key"] for f in files]
        assert "glacier2.txt" in keys
        assert "glacier3.txt" not in keys
        assert "glacier1.txt" not in keys
        assert "standard.txt" not in keys
        assert_equal(len(files), 1)


class TestMultiBucketTracking(TestFileStateManagerFixtures):
    """Test multi-bucket file tracking"""

    def test_multiple_buckets_tracked_separately(self, file_manager, db_conn):
        """Test that files from different buckets are tracked separately"""
        file_manager.add_file(
            bucket="bucket-a",
            key="file.txt",
            size=100,
            etag="abc",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )

        file_manager.add_file(
            bucket="bucket-b",
            key="file.txt",
            size=200,
            etag="def",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )

        with db_conn.get_connection() as conn:
            row_a = conn.execute(
                "SELECT size FROM files WHERE bucket = ? AND key = ?",
                ("bucket-a", "file.txt"),
            ).fetchone()
            row_b = conn.execute(
                "SELECT size FROM files WHERE bucket = ? AND key = ?",
                ("bucket-b", "file.txt"),
            ).fetchone()

        assert_equal(row_a["size"], 100)
        assert_equal(row_b["size"], 200)
