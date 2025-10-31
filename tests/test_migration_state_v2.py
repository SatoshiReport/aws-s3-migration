"""Comprehensive unit tests for migration_state_v2.py with 80%+ coverage."""

import json
import sqlite3
from pathlib import Path

import pytest

from migration_state_v2 import BucketStatus, DatabaseConnection, MigrationStateV2, Phase


class TestPhaseEnum:
    """Test Phase enum values and functionality."""

    def test_phase_scanning_value(self):
        """Phase.SCANNING has correct value."""
        assert Phase.SCANNING.value == "scanning"

    def test_phase_glacier_restore_value(self):
        """Phase.GLACIER_RESTORE has correct value."""
        assert Phase.GLACIER_RESTORE.value == "glacier_restore"

    def test_phase_glacier_wait_value(self):
        """Phase.GLACIER_WAIT has correct value."""
        assert Phase.GLACIER_WAIT.value == "glacier_wait"

    def test_phase_syncing_value(self):
        """Phase.SYNCING has correct value."""
        assert Phase.SYNCING.value == "syncing"

    def test_phase_verifying_value(self):
        """Phase.VERIFYING has correct value."""
        assert Phase.VERIFYING.value == "verifying"

    def test_phase_deleting_value(self):
        """Phase.DELETING has correct value."""
        assert Phase.DELETING.value == "deleting"

    def test_phase_complete_value(self):
        """Phase.COMPLETE has correct value."""
        assert Phase.COMPLETE.value == "complete"

    def test_phase_enum_from_string(self):
        """Can construct Phase from string value."""
        phase = Phase("scanning")
        assert phase == Phase.SCANNING

    def test_all_phases_exist(self):
        """All expected phases are defined."""
        expected_phases = {
            "SCANNING",
            "GLACIER_RESTORE",
            "GLACIER_WAIT",
            "SYNCING",
            "VERIFYING",
            "DELETING",
            "COMPLETE",
        }
        actual_phases = {member.name for member in Phase}
        assert expected_phases == actual_phases


class TestBucketStatus:
    """Test BucketStatus initialization and data handling."""

    def test_bucket_status_initialization_basic(self):
        """BucketStatus initializes with basic fields."""
        row = {
            "bucket": "test-bucket",
            "file_count": 100,
            "total_size": 5000,
            "storage_class_counts": '{"STANDARD": 80, "GLACIER": 20}',
            "scan_complete": 1,
            "sync_complete": 0,
            "verify_complete": 0,
            "delete_complete": 0,
        }
        status = BucketStatus(row)

        assert status.bucket == "test-bucket"
        assert status.file_count == 100
        assert status.total_size == 5000
        assert status.scan_complete is True
        assert status.sync_complete is False
        assert status.verify_complete is False
        assert status.delete_complete is False

    def test_bucket_status_storage_classes_parsing(self):
        """BucketStatus correctly parses storage class JSON."""
        row = {
            "bucket": "test-bucket",
            "file_count": 50,
            "total_size": 2000,
            "storage_class_counts": '{"STANDARD": 30, "GLACIER": 15, "DEEP_ARCHIVE": 5}',
            "scan_complete": 0,
            "sync_complete": 0,
            "verify_complete": 0,
            "delete_complete": 0,
        }
        status = BucketStatus(row)

        assert status.storage_classes == {
            "STANDARD": 30,
            "GLACIER": 15,
            "DEEP_ARCHIVE": 5,
        }

    def test_bucket_status_empty_storage_classes(self):
        """BucketStatus handles empty storage_class_counts."""
        row = {
            "bucket": "empty-bucket",
            "file_count": 0,
            "total_size": 0,
            "storage_class_counts": None,
            "scan_complete": 0,
            "sync_complete": 0,
            "verify_complete": 0,
            "delete_complete": 0,
        }
        status = BucketStatus(row)

        assert status.storage_classes == {}

    def test_bucket_status_boolean_conversion(self):
        """BucketStatus converts integer flags to booleans."""
        row = {
            "bucket": "test-bucket",
            "file_count": 10,
            "total_size": 100,
            "storage_class_counts": "{}",
            "scan_complete": 1,
            "sync_complete": 1,
            "verify_complete": 1,
            "delete_complete": 1,
        }
        status = BucketStatus(row)

        assert isinstance(status.scan_complete, bool)
        assert isinstance(status.sync_complete, bool)
        assert isinstance(status.verify_complete, bool)
        assert isinstance(status.delete_complete, bool)
        assert all(
            [
                status.scan_complete,
                status.sync_complete,
                status.verify_complete,
                status.delete_complete,
            ]
        )


class TestDatabaseConnection:
    """Test DatabaseConnection initialization and operations."""

    def test_database_connection_initialization(self, tmp_path: Path):
        """DatabaseConnection initializes with database path."""
        db_path = tmp_path / "test.db"
        db_conn = DatabaseConnection(str(db_path))

        assert db_conn.db_path == str(db_path)
        assert db_path.exists()

    def test_database_connection_context_manager(self, tmp_path: Path):
        """DatabaseConnection.get_connection works as context manager."""
        db_path = tmp_path / "test.db"
        db_conn = DatabaseConnection(str(db_path))

        with db_conn.get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)
            assert conn.row_factory == sqlite3.Row

    def test_database_connection_closes_properly(self, tmp_path: Path):
        """DatabaseConnection properly closes connections."""
        db_path = tmp_path / "test.db"
        db_conn = DatabaseConnection(str(db_path))

        with db_conn.get_connection() as conn:
            pass

        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_schema_files_table_created(self, tmp_path: Path):
        """DatabaseConnection creates files table."""
        db_path = tmp_path / "test.db"
        db_conn = DatabaseConnection(str(db_path))

        with db_conn.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
            )
            assert cursor.fetchone() is not None

    def test_schema_bucket_status_table_created(self, tmp_path: Path):
        """DatabaseConnection creates bucket_status table."""
        db_path = tmp_path / "test.db"
        db_conn = DatabaseConnection(str(db_path))

        with db_conn.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='bucket_status'"
            )
            assert cursor.fetchone() is not None

    def test_schema_migration_metadata_table_created(self, tmp_path: Path):
        """DatabaseConnection creates migration_metadata table."""
        db_path = tmp_path / "test.db"
        db_conn = DatabaseConnection(str(db_path))

        with db_conn.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='migration_metadata'"
            )
            assert cursor.fetchone() is not None

    def test_schema_indices_created(self, tmp_path: Path):
        """DatabaseConnection creates required indices."""
        db_path = tmp_path / "test.db"
        db_conn = DatabaseConnection(str(db_path))

        with db_conn.get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indices = {row[0] for row in cursor.fetchall()}

            assert "idx_files_state" in indices
            assert "idx_files_storage_class" in indices
            assert "idx_files_bucket" in indices

    def test_database_schema_migration_idempotent(self, tmp_path: Path):
        """DatabaseConnection schema migration is idempotent."""
        db_path = tmp_path / "test.db"

        _db_conn1 = DatabaseConnection(str(db_path))
        db_conn2 = DatabaseConnection(str(db_path))

        with db_conn2.get_connection() as conn:
            cursor = conn.execute("PRAGMA table_info(bucket_status)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "verified_file_count" in columns

    def test_files_table_columns(self, tmp_path: Path):
        """Files table has all expected columns."""
        db_path = tmp_path / "test.db"
        db_conn = DatabaseConnection(str(db_path))

        with db_conn.get_connection() as conn:
            cursor = conn.execute("PRAGMA table_info(files)")
            columns = {row[1] for row in cursor.fetchall()}

            expected_columns = {
                "bucket",
                "key",
                "size",
                "etag",
                "storage_class",
                "last_modified",
                "local_path",
                "local_checksum",
                "state",
                "error_message",
                "glacier_restore_requested_at",
                "glacier_restored_at",
                "created_at",
                "updated_at",
            }
            assert expected_columns.issubset(columns)

    def test_bucket_status_table_columns(self, tmp_path: Path):
        """Bucket_status table has all expected columns."""
        db_path = tmp_path / "test.db"
        db_conn = DatabaseConnection(str(db_path))

        with db_conn.get_connection() as conn:
            cursor = conn.execute("PRAGMA table_info(bucket_status)")
            columns = {row[1] for row in cursor.fetchall()}

            expected_columns = {
                "bucket",
                "file_count",
                "total_size",
                "storage_class_counts",
                "scan_complete",
                "sync_complete",
                "verify_complete",
                "delete_complete",
                "local_file_count",
                "local_total_size",
                "verified_file_count",
                "size_verified_count",
                "checksum_verified_count",
                "total_bytes_verified",
                "created_at",
                "updated_at",
            }
            assert expected_columns.issubset(columns)

    def test_migration_metadata_table_columns(self, tmp_path: Path):
        """Migration_metadata table has expected columns."""
        db_path = tmp_path / "test.db"
        db_conn = DatabaseConnection(str(db_path))

        with db_conn.get_connection() as conn:
            cursor = conn.execute("PRAGMA table_info(migration_metadata)")
            columns = {row[1] for row in cursor.fetchall()}

            expected_columns = {"key", "value", "updated_at"}
            assert expected_columns.issubset(columns)


class TestMigrationStateV2:
    """Test MigrationStateV2 delegation and integration."""

    def test_migration_state_v2_initialization(self, tmp_path: Path):
        """MigrationStateV2 initializes with database and managers."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        assert isinstance(state.db_conn, DatabaseConnection)
        assert hasattr(state, "files")
        assert hasattr(state, "buckets")
        assert hasattr(state, "phases")

    def test_migration_state_v2_add_file(self, tmp_path: Path):
        """MigrationStateV2.add_file delegates to FileStateManager."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.add_file(
            bucket="test-bucket",
            key="test-key.txt",
            size=1024,
            etag="abc123",
            storage_class="STANDARD",
            last_modified="2025-10-31T00:00:00Z",
        )

        with state.db_conn.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM files WHERE bucket = ? AND key = ?", ("test-bucket", "test-key.txt")
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["size"] == 1024
            assert row["storage_class"] == "STANDARD"

    def test_migration_state_v2_add_file_idempotent(self, tmp_path: Path):
        """MigrationStateV2.add_file is idempotent."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.add_file(
            bucket="bucket1",
            key="key1",
            size=100,
            etag="e1",
            storage_class="STANDARD",
            last_modified="2025-10-31T00:00:00Z",
        )

        state.add_file(
            bucket="bucket1",
            key="key1",
            size=100,
            etag="e1",
            storage_class="STANDARD",
            last_modified="2025-10-31T00:00:00Z",
        )

        with state.db_conn.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM files")
            count = cursor.fetchone()[0]
            assert count == 1

    def test_migration_state_v2_mark_glacier_restore_requested(self, tmp_path: Path):
        """MigrationStateV2.mark_glacier_restore_requested updates file state."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.add_file(
            bucket="bucket1",
            key="glacier-key",
            size=1000,
            etag="e1",
            storage_class="GLACIER",
            last_modified="2025-10-31T00:00:00Z",
        )

        state.mark_glacier_restore_requested("bucket1", "glacier-key")

        with state.db_conn.get_connection() as conn:
            cursor = conn.execute(
                "SELECT glacier_restore_requested_at FROM files WHERE bucket = ? AND key = ?",
                ("bucket1", "glacier-key"),
            )
            row = cursor.fetchone()
            assert row["glacier_restore_requested_at"] is not None

    def test_migration_state_v2_mark_glacier_restored(self, tmp_path: Path):
        """MigrationStateV2.mark_glacier_restored updates file state."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.add_file(
            bucket="bucket1",
            key="glacier-key",
            size=1000,
            etag="e1",
            storage_class="GLACIER",
            last_modified="2025-10-31T00:00:00Z",
        )

        state.mark_glacier_restore_requested("bucket1", "glacier-key")
        state.mark_glacier_restored("bucket1", "glacier-key")

        with state.db_conn.get_connection() as conn:
            cursor = conn.execute(
                "SELECT glacier_restored_at FROM files WHERE bucket = ? AND key = ?",
                ("bucket1", "glacier-key"),
            )
            row = cursor.fetchone()
            assert row["glacier_restored_at"] is not None

    def test_migration_state_v2_get_glacier_files_needing_restore(self, tmp_path: Path):
        """MigrationStateV2.get_glacier_files_needing_restore returns GLACIER files."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.add_file(
            bucket="b1",
            key="glacier1",
            size=100,
            etag="e1",
            storage_class="GLACIER",
            last_modified="2025-10-31T00:00:00Z",
        )
        state.add_file(
            bucket="b1",
            key="standard1",
            size=100,
            etag="e2",
            storage_class="STANDARD",
            last_modified="2025-10-31T00:00:00Z",
        )

        files = state.get_glacier_files_needing_restore()

        assert len(files) == 1
        assert files[0]["key"] == "glacier1"
        assert files[0]["storage_class"] == "GLACIER"

    def test_migration_state_v2_get_files_restoring(self, tmp_path: Path):
        """MigrationStateV2.get_files_restoring returns in-progress restores."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.add_file(
            bucket="b1",
            key="glacier1",
            size=100,
            etag="e1",
            storage_class="GLACIER",
            last_modified="2025-10-31T00:00:00Z",
        )
        state.mark_glacier_restore_requested("b1", "glacier1")

        files = state.get_files_restoring()

        assert len(files) == 1
        assert files[0]["key"] == "glacier1"

    def test_migration_state_v2_save_bucket_status(self, tmp_path: Path):
        """MigrationStateV2.save_bucket_status persists bucket info."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.save_bucket_status(
            bucket="test-bucket",
            file_count=50,
            total_size=5000,
            storage_classes={"STANDARD": 40, "GLACIER": 10},
            scan_complete=True,
        )

        with state.db_conn.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM bucket_status WHERE bucket = ?", ("test-bucket",))
            row = cursor.fetchone()
            assert row is not None
            assert row["file_count"] == 50
            assert row["total_size"] == 5000
            assert row["scan_complete"] == 1

    def test_migration_state_v2_mark_bucket_sync_complete(self, tmp_path: Path):
        """MigrationStateV2.mark_bucket_sync_complete updates bucket status."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.save_bucket_status("bucket1", 10, 100, {})
        state.mark_bucket_sync_complete("bucket1")

        with state.db_conn.get_connection() as conn:
            cursor = conn.execute(
                "SELECT sync_complete FROM bucket_status WHERE bucket = ?", ("bucket1",)
            )
            row = cursor.fetchone()
            assert row["sync_complete"] == 1

    def test_migration_state_v2_mark_bucket_verify_complete_with_metrics(self, tmp_path: Path):
        """MigrationStateV2.mark_bucket_verify_complete stores verification metrics."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.save_bucket_status("bucket1", 10, 100, {})
        state.mark_bucket_verify_complete(
            bucket="bucket1",
            verified_file_count=10,
            size_verified_count=10,
            checksum_verified_count=5,
            total_bytes_verified=100,
            local_file_count=10,
        )

        with state.db_conn.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM bucket_status WHERE bucket = ?", ("bucket1",))
            row = cursor.fetchone()
            assert row["verify_complete"] == 1
            assert row["verified_file_count"] == 10
            assert row["checksum_verified_count"] == 5

    def test_migration_state_v2_mark_bucket_delete_complete(self, tmp_path: Path):
        """MigrationStateV2.mark_bucket_delete_complete updates bucket status."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.save_bucket_status("bucket1", 10, 100, {})
        state.mark_bucket_delete_complete("bucket1")

        with state.db_conn.get_connection() as conn:
            cursor = conn.execute(
                "SELECT delete_complete FROM bucket_status WHERE bucket = ?", ("bucket1",)
            )
            row = cursor.fetchone()
            assert row["delete_complete"] == 1

    def test_migration_state_v2_get_all_buckets(self, tmp_path: Path):
        """MigrationStateV2.get_all_buckets returns all bucket names."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.save_bucket_status("bucket1", 10, 100, {})
        state.save_bucket_status("bucket2", 20, 200, {})
        state.save_bucket_status("bucket3", 30, 300, {})

        buckets = state.get_all_buckets()

        assert set(buckets) == {"bucket1", "bucket2", "bucket3"}
        assert buckets == sorted(buckets)

    def test_migration_state_v2_get_completed_buckets_for_phase(self, tmp_path: Path):
        """MigrationStateV2.get_completed_buckets_for_phase filters by phase flag."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.save_bucket_status("bucket1", 10, 100, {})
        state.save_bucket_status("bucket2", 20, 200, {})
        state.save_bucket_status("bucket3", 30, 300, {})

        state.mark_bucket_sync_complete("bucket1")
        state.mark_bucket_sync_complete("bucket2")

        completed = state.get_completed_buckets_for_phase("sync_complete")

        assert set(completed) == {"bucket1", "bucket2"}

    def test_migration_state_v2_get_bucket_info(self, tmp_path: Path):
        """MigrationStateV2.get_bucket_info returns bucket details."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.save_bucket_status(
            "test-bucket", 25, 2500, {"STANDARD": 20, "GLACIER": 5}, scan_complete=True
        )

        info = state.get_bucket_info("test-bucket")

        assert info["bucket"] == "test-bucket"
        assert info["file_count"] == 25
        assert info["total_size"] == 2500
        assert info["scan_complete"] == 1
        storage_classes = json.loads(info["storage_class_counts"])
        assert storage_classes == {"STANDARD": 20, "GLACIER": 5}

    def test_migration_state_v2_get_bucket_info_nonexistent(self, tmp_path: Path):
        """MigrationStateV2.get_bucket_info returns empty dict for missing bucket."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        info = state.get_bucket_info("nonexistent-bucket")

        assert info == {}

    def test_migration_state_v2_get_scan_summary(self, tmp_path: Path):
        """MigrationStateV2.get_scan_summary aggregates scan data."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        # Add files for scan
        state.add_file("b1", "k1", 100, "e1", "STANDARD", "2025-10-31T00:00:00Z")
        state.add_file("b1", "k2", 100, "e2", "GLACIER", "2025-10-31T00:00:00Z")
        state.add_file("b2", "k3", 100, "e3", "STANDARD", "2025-10-31T00:00:00Z")

        state.save_bucket_status("b1", 2, 200, {"STANDARD": 1, "GLACIER": 1}, scan_complete=True)
        state.save_bucket_status("b2", 1, 100, {"STANDARD": 1}, scan_complete=True)
        state.save_bucket_status("b3", 5, 50, {"STANDARD": 5}, scan_complete=False)

        summary = state.get_scan_summary()

        assert summary["bucket_count"] == 2
        assert summary["total_files"] == 3
        assert summary["total_size"] == 300
        assert summary["storage_classes"]["STANDARD"] == 2
        assert summary["storage_classes"]["GLACIER"] == 1

    def test_migration_state_v2_get_current_phase_default(self, tmp_path: Path):
        """MigrationStateV2.get_current_phase returns SCANNING by default."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        phase = state.get_current_phase()

        assert phase == Phase.SCANNING

    def test_migration_state_v2_set_current_phase(self, tmp_path: Path):
        """MigrationStateV2.set_current_phase updates phase."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.set_current_phase(Phase.GLACIER_RESTORE)
        phase = state.get_current_phase()

        assert phase == Phase.GLACIER_RESTORE

    def test_migration_state_v2_set_current_phase_persists(self, tmp_path: Path):
        """MigrationStateV2 phase change persists across instances."""
        db_path = tmp_path / "test.db"

        state1 = MigrationStateV2(str(db_path))
        state1.set_current_phase(Phase.GLACIER_WAIT)

        state2 = MigrationStateV2(str(db_path))
        phase = state2.get_current_phase()

        assert phase == Phase.GLACIER_WAIT

    def test_migration_state_v2_phase_transition_sequence(self, tmp_path: Path):
        """MigrationStateV2 supports full phase transition sequence."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        phases = [
            Phase.SCANNING,
            Phase.GLACIER_RESTORE,
            Phase.GLACIER_WAIT,
            Phase.SYNCING,
            Phase.VERIFYING,
            Phase.DELETING,
            Phase.COMPLETE,
        ]

        for expected_phase in phases:
            state.set_current_phase(expected_phase)
            assert state.get_current_phase() == expected_phase


class TestMigrationStateV2Integration:
    """Integration tests combining multiple operations."""

    def test_full_bucket_migration_workflow(self, tmp_path: Path):
        """Test complete workflow through all phases."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.set_current_phase(Phase.SCANNING)
        assert state.get_current_phase() == Phase.SCANNING

        state.add_file("bucket1", "key1", 100, "e1", "GLACIER", "2025-10-31T00:00:00Z")
        state.add_file("bucket1", "key2", 200, "e2", "STANDARD", "2025-10-31T00:00:00Z")

        state.save_bucket_status("bucket1", 2, 300, {"GLACIER": 1, "STANDARD": 1}, True)

        state.set_current_phase(Phase.GLACIER_RESTORE)
        glacier_files = state.get_glacier_files_needing_restore()
        assert len(glacier_files) == 1

        state.mark_glacier_restore_requested("bucket1", "key1")
        state.set_current_phase(Phase.GLACIER_WAIT)

        state.mark_glacier_restored("bucket1", "key1")
        state.set_current_phase(Phase.SYNCING)

        state.mark_bucket_sync_complete("bucket1")
        state.set_current_phase(Phase.VERIFYING)

        state.mark_bucket_verify_complete("bucket1", 2, 2, 1, 300, 2)
        state.set_current_phase(Phase.DELETING)

        state.mark_bucket_delete_complete("bucket1")
        state.set_current_phase(Phase.COMPLETE)

        summary = state.get_scan_summary()
        assert summary["bucket_count"] == 1
        assert summary["total_files"] == 2
        assert summary["total_size"] == 300

    def test_multiple_buckets_independent_status(self, tmp_path: Path):
        """Test multiple buckets can have independent status."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.save_bucket_status("bucket1", 10, 100, {})
        state.save_bucket_status("bucket2", 20, 200, {})

        state.mark_bucket_sync_complete("bucket1")
        state.mark_bucket_verify_complete("bucket1")

        completed_sync = state.get_completed_buckets_for_phase("sync_complete")
        completed_verify = state.get_completed_buckets_for_phase("verify_complete")

        assert "bucket1" in completed_sync
        assert "bucket2" not in completed_sync
        assert "bucket1" in completed_verify
        assert "bucket2" not in completed_verify

    def test_storage_classes_aggregation(self, tmp_path: Path):
        """Test storage classes are properly aggregated in scan summary."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.add_file("b1", "k1", 100, "e1", "STANDARD", "2025-10-31T00:00:00Z")
        state.add_file("b1", "k2", 200, "e2", "GLACIER", "2025-10-31T00:00:00Z")
        state.add_file("b1", "k3", 300, "e3", "DEEP_ARCHIVE", "2025-10-31T00:00:00Z")
        state.add_file("b2", "k4", 400, "e4", "GLACIER_IR", "2025-10-31T00:00:00Z")
        state.add_file("b2", "k5", 100, "e5", "GLACIER", "2025-10-31T00:00:00Z")

        state.save_bucket_status("b1", 3, 600, {}, True)
        state.save_bucket_status("b2", 2, 500, {}, True)

        summary = state.get_scan_summary()

        assert summary["storage_classes"]["STANDARD"] == 1
        assert summary["storage_classes"]["GLACIER"] == 2
        assert summary["storage_classes"]["DEEP_ARCHIVE"] == 1
        assert summary["storage_classes"]["GLACIER_IR"] == 1

    def test_glacier_restore_workflow(self, tmp_path: Path):
        """Test complete Glacier restore workflow."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.add_file("b1", "glacier1", 100, "e1", "GLACIER", "2025-10-31T00:00:00Z")
        state.add_file("b1", "glacier2", 200, "e2", "DEEP_ARCHIVE", "2025-10-31T00:00:00Z")

        needing_restore = state.get_glacier_files_needing_restore()
        assert len(needing_restore) == 2

        state.mark_glacier_restore_requested("b1", "glacier1")
        state.mark_glacier_restore_requested("b1", "glacier2")

        restoring = state.get_files_restoring()
        assert len(restoring) == 2

        state.mark_glacier_restored("b1", "glacier1")

        restoring = state.get_files_restoring()
        assert len(restoring) == 1
        assert restoring[0]["key"] == "glacier2"

        needing_restore = state.get_glacier_files_needing_restore()
        assert len(needing_restore) == 0
