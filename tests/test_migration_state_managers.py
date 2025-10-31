"""Comprehensive unit tests for migration_state_managers.py"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from migration_state_managers import BucketStateManager, FileStateManager, PhaseManager
from migration_state_v2 import DatabaseConnection, MigrationStateV2, Phase


class TestFileStateManager:
    """Test FileStateManager class"""

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
    def file_manager(self, db_conn):
        """Create FileStateManager instance"""
        return FileStateManager(db_conn)

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
        assert row["size"] == 1024
        assert row["etag"] == "abc123"
        assert row["storage_class"] == "STANDARD"
        assert row["state"] == "discovered"

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

        # Add the same file again - should not raise an error
        file_manager.add_file(
            bucket="test-bucket",
            key="path/to/file.txt",
            size=1024,
            etag="abc123",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )

        # Verify only one record exists
        with db_conn.get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM files WHERE bucket = ? AND key = ?",
                ("test-bucket", "path/to/file.txt"),
            ).fetchone()

        assert count["cnt"] == 1

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
        # Timestamps should be between before and after
        assert before_time <= row["created_at"] <= after_time

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

    def test_get_glacier_files_needing_restore(self, file_manager, db_conn):
        """Test retrieving Glacier files that need restore"""
        # Add standard file
        file_manager.add_file(
            bucket="test-bucket",
            key="standard.txt",
            size=100,
            etag="std123",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )

        # Add glacier file without restore request
        file_manager.add_file(
            bucket="test-bucket",
            key="glacier1.txt",
            size=1000,
            etag="glac1",
            storage_class="GLACIER",
            last_modified="2024-01-01T00:00:00Z",
        )

        # Add deep archive file without restore request
        file_manager.add_file(
            bucket="test-bucket",
            key="archive1.txt",
            size=2000,
            etag="arch1",
            storage_class="DEEP_ARCHIVE",
            last_modified="2024-01-01T00:00:00Z",
        )

        # Add glacier file with restore request (should not appear)
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
        assert len(files) == 2

    def test_get_files_restoring(self, file_manager, db_conn):
        """Test retrieving files currently being restored"""
        # Add standard file
        file_manager.add_file(
            bucket="test-bucket",
            key="standard.txt",
            size=100,
            etag="std123",
            storage_class="STANDARD",
            last_modified="2024-01-01T00:00:00Z",
        )

        # Add glacier file without restore request
        file_manager.add_file(
            bucket="test-bucket",
            key="glacier1.txt",
            size=1000,
            etag="glac1",
            storage_class="GLACIER",
            last_modified="2024-01-01T00:00:00Z",
        )

        # Add glacier file with restore request (currently restoring)
        file_manager.add_file(
            bucket="test-bucket",
            key="glacier2.txt",
            size=1500,
            etag="glac2",
            storage_class="GLACIER",
            last_modified="2024-01-01T00:00:00Z",
        )
        file_manager.mark_glacier_restore_requested("test-bucket", "glacier2.txt")

        # Add glacier file that is already restored
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
        assert len(files) == 1

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
                "SELECT size FROM files WHERE bucket = ? AND key = ?", ("bucket-a", "file.txt")
            ).fetchone()
            row_b = conn.execute(
                "SELECT size FROM files WHERE bucket = ? AND key = ?", ("bucket-b", "file.txt")
            ).fetchone()

        assert row_a["size"] == 100
        assert row_b["size"] == 200


class TestBucketStateManager:
    """Test BucketStateManager class"""

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
        assert row["file_count"] == 100
        assert row["total_size"] == 5000000
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

        assert row["file_count"] == 150
        assert row["total_size"] == 7000000
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
        assert row["verified_file_count"] == 100
        assert row["size_verified_count"] == 100
        assert row["checksum_verified_count"] == 95
        assert row["total_bytes_verified"] == 5000000
        assert row["local_file_count"] == 100

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
        assert row["verified_file_count"] == 100
        assert row["size_verified_count"] == 100
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

    def test_get_completed_buckets_for_phase(self, bucket_manager, db_conn):
        """Test retrieving buckets completed for a specific phase"""
        # Create three buckets
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

        # Mark some as sync_complete
        bucket_manager.mark_bucket_sync_complete("bucket-a")
        bucket_manager.mark_bucket_sync_complete("bucket-b")

        buckets = bucket_manager.get_completed_buckets_for_phase("sync_complete")

        assert sorted(buckets) == ["bucket-a", "bucket-b"]

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

    def test_get_scan_summary(self, bucket_manager, db_conn):
        """Test getting scan summary"""
        # Add files for testing
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

        # Save bucket statuses
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

    def test_get_scan_summary_excludes_incomplete_scans(self, bucket_manager, db_conn):
        """Test that scan summary only includes complete scans"""
        # Add bucket with scan_complete=False
        bucket_manager.save_bucket_status(
            bucket="incomplete-bucket",
            file_count=10,
            total_size=100000,
            storage_classes={"STANDARD": 10},
            scan_complete=False,
        )

        # Add bucket with scan_complete=True
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


class TestPhaseManager:
    """Test PhaseManager class"""

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
    def phase_manager(self, db_conn):
        """Create PhaseManager instance"""
        return PhaseManager(db_conn)

    def test_phase_manager_initialization_sets_scanning(self, db_conn):
        """Test that new PhaseManager initializes to SCANNING phase"""
        phase_manager = PhaseManager(db_conn)
        phase = phase_manager.get_phase()

        assert phase == Phase.SCANNING

    def test_set_phase_and_get_phase(self, phase_manager):
        """Test setting and getting phases"""
        phase_manager.set_phase(Phase.GLACIER_RESTORE)
        assert phase_manager.get_phase() == Phase.GLACIER_RESTORE

        phase_manager.set_phase(Phase.GLACIER_WAIT)
        assert phase_manager.get_phase() == Phase.GLACIER_WAIT

        phase_manager.set_phase(Phase.SYNCING)
        assert phase_manager.get_phase() == Phase.SYNCING

        phase_manager.set_phase(Phase.VERIFYING)
        assert phase_manager.get_phase() == Phase.VERIFYING

        phase_manager.set_phase(Phase.DELETING)
        assert phase_manager.get_phase() == Phase.DELETING

        phase_manager.set_phase(Phase.COMPLETE)
        assert phase_manager.get_phase() == Phase.COMPLETE

    def test_phase_persistence_across_instances(self, db_conn):
        """Test that phase is persisted and can be retrieved by new instance"""
        phase_manager1 = PhaseManager(db_conn)
        phase_manager1.set_phase(Phase.GLACIER_RESTORE)

        # Create new instance
        phase_manager2 = PhaseManager(db_conn)
        assert phase_manager2.get_phase() == Phase.GLACIER_RESTORE

    def test_phase_updates_are_persisted(self, phase_manager, db_conn):
        """Test that phase updates are stored in database"""
        phase_manager.set_phase(Phase.SYNCING)

        with db_conn.get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM migration_metadata WHERE key = 'current_phase'"
            ).fetchone()

        assert row["value"] == Phase.SYNCING.value

    def test_get_phase_returns_phase_enum(self, phase_manager):
        """Test that get_phase returns Phase enum type"""
        phase = phase_manager.get_phase()

        assert isinstance(phase, Phase)
        assert phase in Phase

    def test_phase_manager_multiple_set_operations(self, phase_manager):
        """Test multiple consecutive set operations"""
        phases = [
            Phase.SCANNING,
            Phase.GLACIER_RESTORE,
            Phase.GLACIER_WAIT,
            Phase.SYNCING,
            Phase.VERIFYING,
            Phase.DELETING,
            Phase.COMPLETE,
        ]

        for phase in phases:
            phase_manager.set_phase(phase)
            assert phase_manager.get_phase() == phase


class TestIntegration:
    """Integration tests for all state managers working together"""

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
    def state(self, temp_db):
        """Create MigrationStateV2 instance"""
        return MigrationStateV2(temp_db)

    def test_full_migration_workflow(self, state):
        """Test a complete migration workflow"""
        # Add files
        state.add_file(
            "test-bucket",
            "file1.txt",
            1000,
            "abc1",
            "STANDARD",
            "2024-01-01T00:00:00Z",
        )
        state.add_file(
            "test-bucket",
            "file2.txt",
            2000,
            "abc2",
            "GLACIER",
            "2024-01-01T00:00:00Z",
        )

        # Save bucket status
        state.save_bucket_status(
            "test-bucket", 2, 3000, {"STANDARD": 1, "GLACIER": 1}, scan_complete=True
        )

        # Verify scanning phase
        assert state.get_current_phase() == Phase.SCANNING

        # Progress to glacier restore
        state.set_current_phase(Phase.GLACIER_RESTORE)
        glacier_files = state.get_glacier_files_needing_restore()
        assert len(glacier_files) == 1

        # Mark glacier restore requested
        state.mark_glacier_restore_requested("test-bucket", "file2.txt")
        glacier_files = state.get_glacier_files_needing_restore()
        assert len(glacier_files) == 0

        # Check files restoring
        restoring_files = state.get_files_restoring()
        assert len(restoring_files) == 1

        # Mark glacier restore complete
        state.mark_glacier_restored("test-bucket", "file2.txt")
        restoring_files = state.get_files_restoring()
        assert len(restoring_files) == 0

        # Progress through phases
        state.set_current_phase(Phase.GLACIER_WAIT)
        assert state.get_current_phase() == Phase.GLACIER_WAIT

        state.set_current_phase(Phase.SYNCING)
        state.mark_bucket_sync_complete("test-bucket")
        assert "test-bucket" in state.get_completed_buckets_for_phase("sync_complete")

        state.set_current_phase(Phase.VERIFYING)
        state.mark_bucket_verify_complete(
            "test-bucket",
            verified_file_count=2,
            size_verified_count=2,
            checksum_verified_count=2,
            total_bytes_verified=3000,
            local_file_count=2,
        )

        state.set_current_phase(Phase.DELETING)
        state.mark_bucket_delete_complete("test-bucket")
        assert "test-bucket" in state.get_completed_buckets_for_phase("delete_complete")

        state.set_current_phase(Phase.COMPLETE)
        assert state.get_current_phase() == Phase.COMPLETE

    def test_multiple_buckets_independent_states(self, state):
        """Test that multiple buckets maintain independent states"""
        # Add files to bucket A
        state.add_file("bucket-a", "file1.txt", 1000, "abc1", "STANDARD", "2024-01-01T00:00:00Z")

        # Add files to bucket B
        state.add_file("bucket-b", "file2.txt", 2000, "def1", "STANDARD", "2024-01-01T00:00:00Z")

        # Save bucket statuses
        state.save_bucket_status("bucket-a", 1, 1000, {"STANDARD": 1}, scan_complete=True)
        state.save_bucket_status("bucket-b", 1, 2000, {"STANDARD": 1}, scan_complete=True)

        # Mark only bucket-a as synced
        state.mark_bucket_sync_complete("bucket-a")

        synced_buckets = state.get_completed_buckets_for_phase("sync_complete")
        assert "bucket-a" in synced_buckets
        assert "bucket-b" not in synced_buckets

    def test_get_scan_summary_integration(self, state):
        """Test getting scan summary through integrated managers"""
        state.add_file("bucket-a", "file1.txt", 1000, "abc1", "STANDARD", "2024-01-01T00:00:00Z")
        state.add_file("bucket-a", "file2.txt", 2000, "abc2", "GLACIER", "2024-01-01T00:00:00Z")
        state.add_file("bucket-b", "file3.txt", 3000, "def1", "STANDARD", "2024-01-01T00:00:00Z")

        state.save_bucket_status("bucket-a", 2, 3000, {"STANDARD": 1, "GLACIER": 1}, True)
        state.save_bucket_status("bucket-b", 1, 3000, {"STANDARD": 1}, True)

        summary = state.get_scan_summary()

        assert summary["bucket_count"] == 2
        assert summary["total_files"] == 3
        assert summary["total_size"] == 6000
        assert summary["storage_classes"]["STANDARD"] == 2
        assert summary["storage_classes"]["GLACIER"] == 1
