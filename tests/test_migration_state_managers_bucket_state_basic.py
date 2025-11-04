"""Unit tests for BucketStateManager basic operations from migration_state_managers.py"""

import json
import tempfile
from pathlib import Path

import pytest

from migration_state_managers import BucketStateManager
from migration_state_v2 import DatabaseConnection


class TestBucketStateManagerBasic:
    """Test BucketStateManager basic operations"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def db_conn(self, temp_db):
        """Create database connection with initialized schema"""
        return DatabaseConnection(temp_db)

    @pytest.fixture
    def bucket_manager(self, db_conn):
        """Create BucketStateManager instance"""
        return BucketStateManager(db_conn)

    def test_save_bucket_status_inserts_record(self, bucket_manager, db_conn):
        """Test saving bucket status"""
        bucket_manager.save_bucket_status(
            bucket="test-bucket",
            file_count=100,
            total_size=5000000,
            storage_classes={"STANDARD": 80, "GLACIER": 20},
            scan_complete=True,
        )

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM bucket_status WHERE bucket = ?", ("test-bucket",)
            ).fetchone()

        assert row is not None
        assert row["bucket"] == "test-bucket"
        assert row["file_count"] == 100  # noqa: PLR2004
        assert row["total_size"] == 5000000  # noqa: PLR2004
        assert row["scan_complete"] == 1
        storage_classes = json.loads(row["storage_class_counts"])
        assert storage_classes == {"STANDARD": 80, "GLACIER": 20}

    def test_save_bucket_status_updates_existing(self, bucket_manager, db_conn):
        """Test that saving bucket status updates existing record"""
        bucket_manager.save_bucket_status(
            bucket="test-bucket",
            file_count=100,
            total_size=5000000,
            storage_classes={"STANDARD": 80},
            scan_complete=False,
        )

        # Update with new values
        bucket_manager.save_bucket_status(
            bucket="test-bucket",
            file_count=150,
            total_size=7000000,
            storage_classes={"STANDARD": 150},
            scan_complete=True,
        )

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM bucket_status WHERE bucket = ?", ("test-bucket",)
            ).fetchone()

        assert row["file_count"] == 150  # noqa: PLR2004
        assert row["total_size"] == 7000000  # noqa: PLR2004
        assert row["scan_complete"] == 1

    def test_save_bucket_status_preserves_created_at(self, bucket_manager, db_conn):
        """Test that created_at timestamp is preserved on update"""
        bucket_manager.save_bucket_status(
            bucket="test-bucket",
            file_count=100,
            total_size=5000000,
            storage_classes={"STANDARD": 80},
        )

        with db_conn.get_connection() as conn:
            original = conn.execute(
                "SELECT created_at FROM bucket_status WHERE bucket = ?", ("test-bucket",)
            ).fetchone()
            original_time = original["created_at"]

        # Update the record
        bucket_manager.save_bucket_status(
            bucket="test-bucket",
            file_count=200,
            total_size=10000000,
            storage_classes={"STANDARD": 200},
        )

        with db_conn.get_connection() as conn:
            updated = conn.execute(
                "SELECT created_at FROM bucket_status WHERE bucket = ?", ("test-bucket",)
            ).fetchone()

        assert updated["created_at"] == original_time

    def test_mark_bucket_sync_complete(self, bucket_manager, db_conn):
        """Test marking bucket as synced"""
        bucket_manager.save_bucket_status(
            bucket="test-bucket",
            file_count=100,
            total_size=5000000,
            storage_classes={"STANDARD": 100},
        )

        bucket_manager.mark_bucket_sync_complete("test-bucket")

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT sync_complete FROM bucket_status WHERE bucket = ?", ("test-bucket",)
            ).fetchone()

        assert row["sync_complete"] == 1

    def test_mark_bucket_verify_complete(self, bucket_manager, db_conn):
        """Test marking bucket as verified"""
        bucket_manager.save_bucket_status(
            bucket="test-bucket",
            file_count=100,
            total_size=5000000,
            storage_classes={"STANDARD": 100},
        )

        bucket_manager.mark_bucket_verify_complete(
            bucket="test-bucket",
            verified_file_count=100,
            size_verified_count=100,
            checksum_verified_count=95,
            total_bytes_verified=5000000,
            local_file_count=100,
        )

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM bucket_status WHERE bucket = ?", ("test-bucket",)
            ).fetchone()

        assert row["verify_complete"] == 1
        assert row["verified_file_count"] == 100  # noqa: PLR2004
        assert row["size_verified_count"] == 100  # noqa: PLR2004
        assert row["checksum_verified_count"] == 95  # noqa: PLR2004
        assert row["total_bytes_verified"] == 5000000  # noqa: PLR2004
        assert row["local_file_count"] == 100  # noqa: PLR2004

    def test_mark_bucket_verify_complete_with_partial_data(self, bucket_manager, db_conn):
        """Test marking bucket verified with only some verification fields"""
        bucket_manager.save_bucket_status(
            bucket="test-bucket",
            file_count=100,
            total_size=5000000,
            storage_classes={"STANDARD": 100},
        )

        bucket_manager.mark_bucket_verify_complete(
            bucket="test-bucket",
            verified_file_count=100,
            size_verified_count=100,
        )

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM bucket_status WHERE bucket = ?", ("test-bucket",)
            ).fetchone()

        assert row["verify_complete"] == 1
        assert row["verified_file_count"] == 100  # noqa: PLR2004
        assert row["size_verified_count"] == 100  # noqa: PLR2004
        assert row["checksum_verified_count"] is None

    def test_mark_bucket_delete_complete(self, bucket_manager, db_conn):
        """Test marking bucket as deleted from S3"""
        bucket_manager.save_bucket_status(
            bucket="test-bucket",
            file_count=100,
            total_size=5000000,
            storage_classes={"STANDARD": 100},
        )

        bucket_manager.mark_bucket_delete_complete("test-bucket")

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT delete_complete FROM bucket_status WHERE bucket = ?", ("test-bucket",)
            ).fetchone()

        assert row["delete_complete"] == 1
