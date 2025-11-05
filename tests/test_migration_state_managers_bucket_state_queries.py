"""Unit tests for BucketStateManager query operations from migration_state_managers.py"""

import pytest

from migration_state_managers import BucketStateManager, FileStateManager


class TestBucketStateManagerQueriesFixtures:
    """Shared fixtures for BucketStateManager query tests"""

    @pytest.fixture
    def bucket_manager(self, db_conn):
        """Create BucketStateManager instance"""
        return BucketStateManager(db_conn)


class TestGetAllBuckets(TestBucketStateManagerQueriesFixtures):
    """Test get_all_buckets operations"""

    def test_get_all_buckets(self, bucket_manager, db_conn):
        """Test retrieving all buckets"""
        bucket_manager.save_bucket_status(
            bucket="bucket-a",
            file_count=100,
            total_size=1000000,
            storage_classes={"STANDARD": 100},
        )
        bucket_manager.save_bucket_status(
            bucket="bucket-b",
            file_count=200,
            total_size=2000000,
            storage_classes={"STANDARD": 200},
        )
        bucket_manager.save_bucket_status(
            bucket="bucket-c",
            file_count=300,
            total_size=3000000,
            storage_classes={"STANDARD": 300},
        )

        buckets = bucket_manager.get_all_buckets()

        assert buckets == ["bucket-a", "bucket-b", "bucket-c"]

    def test_get_all_buckets_empty(self, bucket_manager):
        """Test getting all buckets when none exist"""
        buckets = bucket_manager.get_all_buckets()

        assert buckets == []


class TestGetCompletedBuckets(TestBucketStateManagerQueriesFixtures):
    """Test get_completed_buckets_for_phase operations"""

    def test_get_completed_buckets_for_phase(self, bucket_manager, db_conn):
        """Test retrieving buckets completed for a specific phase"""
        bucket_manager.save_bucket_status(
            bucket="bucket-a",
            file_count=100,
            total_size=1000000,
            storage_classes={"STANDARD": 100},
        )
        bucket_manager.save_bucket_status(
            bucket="bucket-b",
            file_count=200,
            total_size=2000000,
            storage_classes={"STANDARD": 200},
        )
        bucket_manager.save_bucket_status(
            bucket="bucket-c",
            file_count=300,
            total_size=3000000,
            storage_classes={"STANDARD": 300},
        )

        bucket_manager.mark_bucket_sync_complete("bucket-a")
        bucket_manager.mark_bucket_sync_complete("bucket-b")

        buckets = bucket_manager.get_completed_buckets_for_phase("sync_complete")

        assert sorted(buckets) == ["bucket-a", "bucket-b"]


class TestGetBucketInfo(TestBucketStateManagerQueriesFixtures):
    """Test get_bucket_info operations"""

    def test_get_bucket_info(self, bucket_manager, db_conn):
        """Test retrieving bucket information"""
        bucket_manager.save_bucket_status(
            bucket="test-bucket",
            file_count=100,
            total_size=5000000,
            storage_classes={"STANDARD": 80, "GLACIER": 20},
            scan_complete=True,
        )

        info = bucket_manager.get_bucket_info("test-bucket")

        assert info["bucket"] == "test-bucket"
        assert info["file_count"] == 100
        assert info["total_size"] == 5000000
        assert info["scan_complete"] == 1

    def test_get_bucket_info_nonexistent(self, bucket_manager):
        """Test retrieving info for nonexistent bucket"""
        info = bucket_manager.get_bucket_info("nonexistent-bucket")

        assert info == {}


class TestGetScanSummary(TestBucketStateManagerQueriesFixtures):
    """Test get_scan_summary operations"""

    def test_get_scan_summary(self, bucket_manager, db_conn):
        """Test getting scan summary"""
        file_manager = FileStateManager(db_conn)
        file_manager.add_file(
            bucket="bucket-a",
            key="file1.txt",
            size=1000,
            etag="abc1",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )
        file_manager.add_file(
            bucket="bucket-a",
            key="file2.txt",
            size=2000,
            etag="abc2",
            storage_class="GLACIER",
            last_modified="2024-01-01T00:00:00Z",
        )
        file_manager.add_file(
            bucket="bucket-b",
            key="file3.txt",
            size=3000,
            etag="def1",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )

        bucket_manager.save_bucket_status(
            bucket="bucket-a",
            file_count=2,
            total_size=3000,
            storage_classes={"STANDARD": 1, "GLACIER": 1},
            scan_complete=True,
        )
        bucket_manager.save_bucket_status(
            bucket="bucket-b",
            file_count=1,
            total_size=3000,
            storage_classes={"STANDARD": 1},
            scan_complete=True,
        )

        summary = bucket_manager.get_scan_summary()

        assert summary["bucket_count"] == 2
        assert summary["total_files"] == 3
        assert summary["total_size"] == 6000
        assert summary["storage_classes"]["STANDARD"] == 2
        assert summary["storage_classes"]["GLACIER"] == 1


class TestScanSummaryFiltering(TestBucketStateManagerQueriesFixtures):
    """Test scan summary filtering logic"""

    def test_get_scan_summary_excludes_incomplete_scans(self, bucket_manager, db_conn):
        """Test that scan summary only includes complete scans"""
        bucket_manager.save_bucket_status(
            bucket="incomplete-bucket",
            file_count=10,
            total_size=100000,
            storage_classes={"STANDARD": 10},
            scan_complete=False,
        )

        bucket_manager.save_bucket_status(
            bucket="complete-bucket",
            file_count=5,
            total_size=50000,
            storage_classes={"STANDARD": 5},
            scan_complete=True,
        )

        summary = bucket_manager.get_scan_summary()

        assert summary["bucket_count"] == 1
        assert summary["total_files"] == 5
        assert summary["total_size"] == 50000
