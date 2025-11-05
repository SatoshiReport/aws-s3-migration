"""Unit tests for MigrationStateV2 bucket operations and phase management."""

import json
from pathlib import Path

import pytest

from migration_state_v2 import MigrationStateV2, Phase


class TestBucketStatusPersistence:
    """Test bucket status save operations"""

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
            assert row["file_count"] == 50  # noqa: PLR2004
            assert row["total_size"] == 5000  # noqa: PLR2004
            assert row["scan_complete"] == 1


class TestBucketSyncOperations:
    """Test bucket sync completion operations"""

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


class TestBucketVerifyOperations:
    """Test bucket verification operations"""

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
            assert row["verified_file_count"] == 10  # noqa: PLR2004
            assert row["checksum_verified_count"] == 5  # noqa: PLR2004


class TestBucketDeleteOperations:
    """Test bucket deletion operations"""

    def test_migration_state_v2_mark_bucket_delete_complete(self, tmp_path: Path):
        """MigrationStateV2.mark_bucket_delete_complete updates bucket status."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.save_bucket_status("bucket1", 10, 100, {})
        state.mark_bucket_delete_complete("bucket1")

        with state.db_conn.get_connection() as conn:
            cursor = conn.execute(
                "SELECT delete_complete FROM bucket_status WHERE bucket = ?",
                ("bucket1",),
            )
            row = cursor.fetchone()
            assert row["delete_complete"] == 1


class TestBucketListOperations:
    """Test bucket listing operations"""

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


class TestBucketPhaseFiltering:
    """Test bucket phase filtering operations"""

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


class TestBucketInfoRetrieval:
    """Test bucket info retrieval operations"""

    def test_migration_state_v2_get_bucket_info(self, tmp_path: Path):
        """MigrationStateV2.get_bucket_info returns bucket details."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.save_bucket_status(
            "test-bucket", 25, 2500, {"STANDARD": 20, "GLACIER": 5}, scan_complete=True
        )

        info = state.get_bucket_info("test-bucket")

        assert info["bucket"] == "test-bucket"
        assert info["file_count"] == 25  # noqa: PLR2004
        assert info["total_size"] == 2500  # noqa: PLR2004
        assert info["scan_complete"] == 1
        storage_classes = json.loads(info["storage_class_counts"])
        assert storage_classes == {"STANDARD": 20, "GLACIER": 5}

    def test_migration_state_v2_get_bucket_info_nonexistent(self, tmp_path: Path):
        """MigrationStateV2.get_bucket_info returns empty dict for missing bucket."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        info = state.get_bucket_info("nonexistent-bucket")

        assert info == {}


class TestScanSummaryOperations:
    """Test scan summary operations"""

    def test_migration_state_v2_get_scan_summary(self, tmp_path: Path):
        """MigrationStateV2.get_scan_summary aggregates scan data."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.add_file("b1", "k1", 100, "e1", "STANDARD", "2025-10-31T00:00:00Z")
        state.add_file("b1", "k2", 100, "e2", "GLACIER", "2025-10-31T00:00:00Z")
        state.add_file("b2", "k3", 100, "e3", "STANDARD", "2025-10-31T00:00:00Z")

        state.save_bucket_status("b1", 2, 200, {"STANDARD": 1, "GLACIER": 1}, scan_complete=True)
        state.save_bucket_status("b2", 1, 100, {"STANDARD": 1}, scan_complete=True)
        state.save_bucket_status("b3", 5, 50, {"STANDARD": 5}, scan_complete=False)

        summary = state.get_scan_summary()

        assert summary["bucket_count"] == 2  # noqa: PLR2004
        assert summary["total_files"] == 3  # noqa: PLR2004
        assert summary["total_size"] == 300  # noqa: PLR2004
        assert summary["storage_classes"]["STANDARD"] == 2  # noqa: PLR2004
        assert summary["storage_classes"]["GLACIER"] == 1


class TestPhaseDefaultState:
    """Test default phase state"""

    def test_migration_state_v2_get_current_phase_default(self, tmp_path: Path):
        """MigrationStateV2.get_current_phase returns SCANNING by default."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        phase = state.get_current_phase()

        assert phase == Phase.SCANNING


class TestPhaseTransitions:
    """Test phase transition operations"""

    def test_migration_state_v2_set_current_phase(self, tmp_path: Path):
        """MigrationStateV2.set_current_phase updates phase."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        state.set_current_phase(Phase.GLACIER_RESTORE)
        phase = state.get_current_phase()

        assert phase == Phase.GLACIER_RESTORE


class TestPhasePersistence:
    """Test phase persistence across instances"""

    def test_migration_state_v2_set_current_phase_persists(self, tmp_path: Path):
        """MigrationStateV2 phase change persists across instances."""
        db_path = tmp_path / "test.db"

        state1 = MigrationStateV2(str(db_path))
        state1.set_current_phase(Phase.GLACIER_WAIT)

        state2 = MigrationStateV2(str(db_path))
        phase = state2.get_current_phase()

        assert phase == Phase.GLACIER_WAIT


class TestPhaseSequence:
    """Test phase sequence transitions"""

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
