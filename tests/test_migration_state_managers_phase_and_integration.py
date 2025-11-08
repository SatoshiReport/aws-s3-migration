"""Unit tests for PhaseManager and integration tests for migration_state_managers.py"""

import pytest

from migration_state_managers import PhaseManager
from migration_state_v2 import MigrationStateV2, Phase
from tests.assertions import assert_equal


class TestPhaseManagerFixtures:
    """Shared fixtures for PhaseManager tests"""

    @pytest.fixture
    def phase_manager(self, db_conn):
        """Create PhaseManager instance"""
        return PhaseManager(db_conn)


class TestPhaseManagerInitialization(TestPhaseManagerFixtures):
    """Test PhaseManager initialization"""

    def test_phase_manager_initialization_sets_scanning(self, db_conn):
        """Test that new PhaseManager initializes to SCANNING phase"""
        phase_manager = PhaseManager(db_conn)
        phase = phase_manager.get_phase()

        assert phase == Phase.SCANNING


class TestPhaseSetAndGet(TestPhaseManagerFixtures):
    """Test setting and getting phases"""

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


class TestPhasePersistence(TestPhaseManagerFixtures):
    """Test phase persistence"""

    def test_phase_persistence_across_instances(self, db_conn):
        """Test that phase is persisted and can be retrieved by new instance"""
        phase_manager1 = PhaseManager(db_conn)
        phase_manager1.set_phase(Phase.GLACIER_RESTORE)

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


class TestPhaseEnumType(TestPhaseManagerFixtures):
    """Test phase enum type"""

    def test_get_phase_returns_phase_enum(self, phase_manager):
        """Test that get_phase returns Phase enum type"""
        phase = phase_manager.get_phase()

        assert isinstance(phase, Phase)
        assert phase in Phase


class TestPhaseMultipleOperations(TestPhaseManagerFixtures):
    """Test multiple phase operations"""

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


class TestIntegrationFixtures:
    """Shared fixtures for integration tests"""

    @pytest.fixture
    def state(self, temp_db):
        """Create MigrationStateV2 instance"""
        return MigrationStateV2(temp_db)


class TestFullMigrationWorkflow(TestIntegrationFixtures):
    """Test complete migration workflow"""

    def test_full_migration_workflow(self, state):
        """Test a complete migration workflow"""
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

        state.save_bucket_status(
            "test-bucket", 2, 3000, {"STANDARD": 1, "GLACIER": 1}, scan_complete=True
        )

        assert state.get_current_phase() == Phase.SCANNING

        state.set_current_phase(Phase.GLACIER_RESTORE)
        glacier_files = state.get_glacier_files_needing_restore()
        assert len(glacier_files) == 1


class TestGlacierRestoreWorkflow(TestIntegrationFixtures):
    """Test glacier restore workflow integration"""

    def test_glacier_restore_workflow(self, state):
        """Test complete glacier restore workflow"""
        state.add_file(
            "test-bucket",
            "file2.txt",
            2000,
            "abc2",
            "GLACIER",
            "2024-01-01T00:00:00Z",
        )

        state.mark_glacier_restore_requested("test-bucket", "file2.txt")
        glacier_files = state.get_glacier_files_needing_restore()
        assert len(glacier_files) == 0

        restoring_files = state.get_files_restoring()
        assert len(restoring_files) == 1

        state.mark_glacier_restored("test-bucket", "file2.txt")
        restoring_files = state.get_files_restoring()
        assert len(restoring_files) == 0


class TestPhaseProgression(TestIntegrationFixtures):
    """Test phase progression workflow"""

    def test_phase_progression(self, state):
        """Test progressing through migration phases"""
        state.save_bucket_status(
            "test-bucket", 2, 3000, {"STANDARD": 1, "GLACIER": 1}, scan_complete=True
        )

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


class TestMultipleBucketsIndependence(TestIntegrationFixtures):
    """Test multiple buckets with independent states"""

    def test_multiple_buckets_independent_states(self, state):
        """Test that multiple buckets maintain independent states"""
        state.add_file("bucket-a", "file1.txt", 1000, "abc1", "STANDARD", "2024-01-01T00:00:00Z")

        state.add_file("bucket-b", "file2.txt", 2000, "def1", "STANDARD", "2024-01-01T00:00:00Z")

        state.save_bucket_status("bucket-a", 1, 1000, {"STANDARD": 1}, scan_complete=True)
        state.save_bucket_status("bucket-b", 1, 2000, {"STANDARD": 1}, scan_complete=True)

        state.mark_bucket_sync_complete("bucket-a")

        synced_buckets = state.get_completed_buckets_for_phase("sync_complete")
        assert "bucket-a" in synced_buckets
        assert "bucket-b" not in synced_buckets


class TestScanSummaryIntegration(TestIntegrationFixtures):
    """Test scan summary integration"""

    def test_get_scan_summary_integration(self, state):
        """Test getting scan summary through integrated managers"""
        state.add_file("bucket-a", "file1.txt", 1000, "abc1", "STANDARD", "2024-01-01T00:00:00Z")
        state.add_file("bucket-a", "file2.txt", 2000, "abc2", "GLACIER", "2024-01-01T00:00:00Z")
        state.add_file("bucket-b", "file3.txt", 3000, "def1", "STANDARD", "2024-01-01T00:00:00Z")

        state.save_bucket_status("bucket-a", 2, 3000, {"STANDARD": 1, "GLACIER": 1}, True)
        state.save_bucket_status("bucket-b", 1, 3000, {"STANDARD": 1}, True)

        summary = state.get_scan_summary()

        assert_equal(summary["bucket_count"], 2)
        assert_equal(summary["total_files"], 3)
        assert_equal(summary["total_size"], 6000)
        assert_equal(summary["storage_classes"]["STANDARD"], 2)
        assert_equal(summary["storage_classes"]["GLACIER"], 1)
