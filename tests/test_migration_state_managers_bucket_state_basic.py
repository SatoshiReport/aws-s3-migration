"""Unit tests for BucketStateManager basic operations from migration_state_managers.py"""

import json

import pytest

from migration_state_managers import BucketStateManager

DEFAULT_BUCKET = "test-bucket"
DEFAULT_FILE_COUNT = 100
DEFAULT_TOTAL_SIZE = 5_000_000
UPDATED_FILE_COUNT = 150
UPDATED_TOTAL_SIZE = 7_000_000
DOUBLE_TOTAL_SIZE = 10_000_000
STANDARD_STORAGE_COUNTS = {"STANDARD": 80}
MIXED_STORAGE_COUNTS = {"STANDARD": 80, "GLACIER": 20}
FULL_STANDARD_STORAGE = {"STANDARD": DEFAULT_FILE_COUNT}
CHECKSUM_VERIFIED_COUNT = 95


class TestBucketStateManagerFixtures:
    """Shared fixtures for BucketStateManager tests"""

    @pytest.fixture
    def bucket_manager(self, db_conn):
        """Create BucketStateManager instance"""
        return BucketStateManager(db_conn)


class TestBucketStatusSave(TestBucketStateManagerFixtures):
    """Test save_bucket_status operations"""

    def test_save_bucket_status_inserts_record(self, bucket_manager, db_conn):
        """Test saving bucket status"""
        bucket_manager.save_bucket_status(
            bucket=DEFAULT_BUCKET,
            file_count=DEFAULT_FILE_COUNT,
            total_size=DEFAULT_TOTAL_SIZE,
            storage_classes=MIXED_STORAGE_COUNTS,
            scan_complete=True,
        )

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM bucket_status WHERE bucket = ?", (DEFAULT_BUCKET,)
            ).fetchone()

        assert row is not None
        assert row["bucket"] == DEFAULT_BUCKET
        assert row["file_count"] == DEFAULT_FILE_COUNT
        assert row["total_size"] == DEFAULT_TOTAL_SIZE
        assert row["scan_complete"] == 1
        storage_classes = json.loads(row["storage_class_counts"])
        assert storage_classes == MIXED_STORAGE_COUNTS


class TestBucketStatusUpdate(TestBucketStateManagerFixtures):
    """Test bucket status update operations"""

    def test_save_bucket_status_updates_existing(self, bucket_manager, db_conn):
        """Test that saving bucket status updates existing record"""
        bucket_manager.save_bucket_status(
            bucket=DEFAULT_BUCKET,
            file_count=DEFAULT_FILE_COUNT,
            total_size=DEFAULT_TOTAL_SIZE,
            storage_classes=STANDARD_STORAGE_COUNTS,
            scan_complete=False,
        )

        bucket_manager.save_bucket_status(
            bucket=DEFAULT_BUCKET,
            file_count=UPDATED_FILE_COUNT,
            total_size=UPDATED_TOTAL_SIZE,
            storage_classes={"STANDARD": UPDATED_FILE_COUNT},
            scan_complete=True,
        )

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM bucket_status WHERE bucket = ?", (DEFAULT_BUCKET,)
            ).fetchone()

        assert row["file_count"] == UPDATED_FILE_COUNT
        assert row["total_size"] == UPDATED_TOTAL_SIZE
        assert row["scan_complete"] == 1


class TestBucketStatusTimestamps(TestBucketStateManagerFixtures):
    """Test bucket status timestamp preservation"""

    def test_save_bucket_status_preserves_created_at(self, bucket_manager, db_conn):
        """Test that created_at timestamp is preserved on update"""
        bucket_manager.save_bucket_status(
            bucket=DEFAULT_BUCKET,
            file_count=DEFAULT_FILE_COUNT,
            total_size=DEFAULT_TOTAL_SIZE,
            storage_classes=STANDARD_STORAGE_COUNTS,
        )

        with db_conn.get_connection() as conn:
            original = conn.execute(
                "SELECT created_at FROM bucket_status WHERE bucket = ?",
                (DEFAULT_BUCKET,),
            ).fetchone()
            original_time = original["created_at"]

        bucket_manager.save_bucket_status(
            bucket=DEFAULT_BUCKET,
            file_count=2 * DEFAULT_FILE_COUNT,
            total_size=DOUBLE_TOTAL_SIZE,
            storage_classes={"STANDARD": 2 * DEFAULT_FILE_COUNT},
        )

        with db_conn.get_connection() as conn:
            updated = conn.execute(
                "SELECT created_at FROM bucket_status WHERE bucket = ?",
                (DEFAULT_BUCKET,),
            ).fetchone()

        assert updated["created_at"] == original_time


class TestBucketSyncCompletion(TestBucketStateManagerFixtures):
    """Test bucket sync completion marking"""

    def test_mark_bucket_sync_complete(self, bucket_manager, db_conn):
        """Test marking bucket as synced"""
        bucket_manager.save_bucket_status(
            bucket=DEFAULT_BUCKET,
            file_count=DEFAULT_FILE_COUNT,
            total_size=DEFAULT_TOTAL_SIZE,
            storage_classes=FULL_STANDARD_STORAGE,
        )

        bucket_manager.mark_bucket_sync_complete(DEFAULT_BUCKET)

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT sync_complete FROM bucket_status WHERE bucket = ?",
                (DEFAULT_BUCKET,),
            ).fetchone()

        assert row["sync_complete"] == 1


class TestBucketVerifyCompletion(TestBucketStateManagerFixtures):
    """Test bucket verification completion marking"""

    def test_mark_bucket_verify_complete(self, bucket_manager, db_conn):
        """Test marking bucket as verified"""
        bucket_manager.save_bucket_status(
            bucket=DEFAULT_BUCKET,
            file_count=DEFAULT_FILE_COUNT,
            total_size=DEFAULT_TOTAL_SIZE,
            storage_classes=FULL_STANDARD_STORAGE,
        )

        bucket_manager.mark_bucket_verify_complete(
            bucket=DEFAULT_BUCKET,
            verified_file_count=DEFAULT_FILE_COUNT,
            size_verified_count=DEFAULT_FILE_COUNT,
            checksum_verified_count=CHECKSUM_VERIFIED_COUNT,
            total_bytes_verified=DEFAULT_TOTAL_SIZE,
            local_file_count=DEFAULT_FILE_COUNT,
        )

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM bucket_status WHERE bucket = ?", (DEFAULT_BUCKET,)
            ).fetchone()

        assert row["verify_complete"] == 1
        assert row["verified_file_count"] == DEFAULT_FILE_COUNT
        assert row["size_verified_count"] == DEFAULT_FILE_COUNT
        assert row["checksum_verified_count"] == CHECKSUM_VERIFIED_COUNT
        assert row["total_bytes_verified"] == DEFAULT_TOTAL_SIZE
        assert row["local_file_count"] == DEFAULT_FILE_COUNT


class TestBucketVerifyPartial(TestBucketStateManagerFixtures):
    """Test bucket verification with partial data"""

    def test_mark_bucket_verify_complete_with_partial_data(self, bucket_manager, db_conn):
        """Test marking bucket verified with only some verification fields"""
        bucket_manager.save_bucket_status(
            bucket=DEFAULT_BUCKET,
            file_count=DEFAULT_FILE_COUNT,
            total_size=DEFAULT_TOTAL_SIZE,
            storage_classes=FULL_STANDARD_STORAGE,
        )

        bucket_manager.mark_bucket_verify_complete(
            bucket=DEFAULT_BUCKET,
            verified_file_count=DEFAULT_FILE_COUNT,
            size_verified_count=DEFAULT_FILE_COUNT,
        )

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM bucket_status WHERE bucket = ?", (DEFAULT_BUCKET,)
            ).fetchone()

        assert row["verify_complete"] == 1
        assert row["verified_file_count"] == DEFAULT_FILE_COUNT
        assert row["size_verified_count"] == DEFAULT_FILE_COUNT
        assert row["checksum_verified_count"] is None


class TestBucketDeleteCompletion(TestBucketStateManagerFixtures):
    """Test bucket deletion completion marking"""

    def test_mark_bucket_delete_complete(self, bucket_manager, db_conn):
        """Test marking bucket as deleted from S3"""
        bucket_manager.save_bucket_status(
            bucket=DEFAULT_BUCKET,
            file_count=DEFAULT_FILE_COUNT,
            total_size=DEFAULT_TOTAL_SIZE,
            storage_classes=FULL_STANDARD_STORAGE,
        )

        bucket_manager.mark_bucket_delete_complete(DEFAULT_BUCKET)

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT delete_complete FROM bucket_status WHERE bucket = ?",
                (DEFAULT_BUCKET,),
            ).fetchone()

        assert row["delete_complete"] == 1
