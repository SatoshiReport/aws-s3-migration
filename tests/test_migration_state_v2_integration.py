"""Integration tests for MigrationStateV2 combining multiple operations."""

from pathlib import Path

import pytest

from migration_state_v2 import MigrationStateV2, Phase


class TestFullBucketMigration:
    """Test complete bucket migration workflow"""

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
        assert summary["total_files"] == 2  # noqa: PLR2004
        assert summary["total_size"] == 300  # noqa: PLR2004


class TestMultipleBucketStatus:
    """Test multiple buckets with independent status"""

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


class TestStorageClassAggregation:
    """Test storage class aggregation"""

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
        assert summary["storage_classes"]["GLACIER"] == 2  # noqa: PLR2004
        assert summary["storage_classes"]["DEEP_ARCHIVE"] == 1
        assert summary["storage_classes"]["GLACIER_IR"] == 1


class TestGlacierRestoreIntegration:
    """Test complete Glacier restore workflow"""

    def test_glacier_restore_workflow(self, tmp_path: Path):
        """Test complete Glacier restore workflow."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.add_file("b1", "glacier1", 100, "e1", "GLACIER", "2025-10-31T00:00:00Z")
        state.add_file("b1", "glacier2", 200, "e2", "DEEP_ARCHIVE", "2025-10-31T00:00:00Z")

        needing_restore = state.get_glacier_files_needing_restore()
        assert len(needing_restore) == 2  # noqa: PLR2004

        state.mark_glacier_restore_requested("b1", "glacier1")
        state.mark_glacier_restore_requested("b1", "glacier2")

        restoring = state.get_files_restoring()
        assert len(restoring) == 2  # noqa: PLR2004

        state.mark_glacier_restored("b1", "glacier1")

        restoring = state.get_files_restoring()
        assert len(restoring) == 1
        assert restoring[0]["key"] == "glacier2"

        needing_restore = state.get_glacier_files_needing_restore()
        assert len(needing_restore) == 0
