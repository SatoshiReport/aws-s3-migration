"""Unit tests for MigrationStateV2 bucket operations and phase management."""

import json
from pathlib import Path

from migration_state_v2 import MigrationStateV2, Phase

DEFAULT_BUCKET = "test-bucket"
DEFAULT_FILE_COUNT = 50
DEFAULT_TOTAL_SIZE = 5_000
DEFAULT_STORAGE = {"STANDARD": 40, "GLACIER": 10}
SMALL_FILE_COUNT = 10
SMALL_TOTAL_SIZE = 100
MEDIUM_FILE_COUNT = 20
MEDIUM_TOTAL_SIZE = 200
LARGE_FILE_COUNT = 30
LARGE_TOTAL_SIZE = 300
INFO_FILE_COUNT = 25
INFO_TOTAL_SIZE = 2_500
INFO_STORAGE = {"STANDARD": 20, "GLACIER": 5}
SUMMARY_STANDARD_COUNT = 2
SUMMARY_GLACIER_COUNT = 1
INCOMPLETE_FILE_COUNT = 5
INCOMPLETE_TOTAL_SIZE = 50
PARTIAL_CHECKSUM_COUNT = 5
COMPLETED_BUCKET_COUNT = 2
SUMMARY_FILE_TOTAL = 3


def test_migration_state_v2_save_bucket_status(tmp_path: Path):
    """MigrationStateV2.save_bucket_status persists bucket info."""
    db_path = tmp_path / "test.db"
    state = MigrationStateV2(str(db_path))

    state.save_bucket_status(
        bucket=DEFAULT_BUCKET,
        file_count=DEFAULT_FILE_COUNT,
        total_size=DEFAULT_TOTAL_SIZE,
        storage_classes=DEFAULT_STORAGE,
        scan_complete=True,
    )

    with state.db_conn.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM bucket_status WHERE bucket = ?", (DEFAULT_BUCKET,))
        row = cursor.fetchone()
        assert row is not None
        assert row["file_count"] == DEFAULT_FILE_COUNT
        assert row["total_size"] == DEFAULT_TOTAL_SIZE
        assert row["scan_complete"] == 1


def test_migration_state_v2_mark_bucket_sync_complete(tmp_path: Path):
    """MigrationStateV2.mark_bucket_sync_complete updates bucket status."""
    db_path = tmp_path / "test.db"
    state = MigrationStateV2(str(db_path))

    state.save_bucket_status("bucket1", SMALL_FILE_COUNT, SMALL_TOTAL_SIZE, {})
    state.mark_bucket_sync_complete("bucket1")

    with state.db_conn.get_connection() as conn:
        cursor = conn.execute(
            "SELECT sync_complete FROM bucket_status WHERE bucket = ?", ("bucket1",)
        )
        row = cursor.fetchone()
        assert row["sync_complete"] == 1


def test_migration_state_v2_mark_bucket_verify_complete_with_metrics(tmp_path: Path):
    """MigrationStateV2.mark_bucket_verify_complete stores verification metrics."""
    db_path = tmp_path / "test.db"
    state = MigrationStateV2(str(db_path))

    state.save_bucket_status("bucket1", SMALL_FILE_COUNT, SMALL_TOTAL_SIZE, {})
    state.mark_bucket_verify_complete(
        bucket="bucket1",
        verified_file_count=SMALL_FILE_COUNT,
        size_verified_count=SMALL_FILE_COUNT,
        checksum_verified_count=PARTIAL_CHECKSUM_COUNT,
        total_bytes_verified=SMALL_TOTAL_SIZE,
        local_file_count=SMALL_FILE_COUNT,
    )

    with state.db_conn.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM bucket_status WHERE bucket = ?", ("bucket1",))
        row = cursor.fetchone()
        assert row["verify_complete"] == 1
        assert row["verified_file_count"] == SMALL_FILE_COUNT
        assert row["checksum_verified_count"] == PARTIAL_CHECKSUM_COUNT


def test_migration_state_v2_mark_bucket_delete_complete(tmp_path: Path):
    """MigrationStateV2.mark_bucket_delete_complete updates bucket status."""
    db_path = tmp_path / "test.db"
    state = MigrationStateV2(str(db_path))

    state.save_bucket_status("bucket1", SMALL_FILE_COUNT, SMALL_TOTAL_SIZE, {})
    state.mark_bucket_delete_complete("bucket1")

    with state.db_conn.get_connection() as conn:
        cursor = conn.execute(
            "SELECT delete_complete FROM bucket_status WHERE bucket = ?",
            ("bucket1",),
        )
        row = cursor.fetchone()
        assert row["delete_complete"] == 1


def test_migration_state_v2_get_all_buckets(tmp_path: Path):
    """MigrationStateV2.get_all_buckets returns all bucket names."""
    db_path = tmp_path / "test.db"
    state = MigrationStateV2(str(db_path))

    state.save_bucket_status("bucket1", SMALL_FILE_COUNT, SMALL_TOTAL_SIZE, {})
    state.save_bucket_status("bucket2", MEDIUM_FILE_COUNT, MEDIUM_TOTAL_SIZE, {})
    state.save_bucket_status("bucket3", LARGE_FILE_COUNT, LARGE_TOTAL_SIZE, {})

    buckets = state.get_all_buckets()

    assert set(buckets) == {"bucket1", "bucket2", "bucket3"}
    assert buckets == sorted(buckets)


def test_migration_state_v2_get_completed_buckets_for_phase(tmp_path: Path):
    """MigrationStateV2.get_completed_buckets_for_phase filters by phase flag."""
    db_path = tmp_path / "test.db"
    state = MigrationStateV2(str(db_path))

    state.save_bucket_status("bucket1", SMALL_FILE_COUNT, SMALL_TOTAL_SIZE, {})
    state.save_bucket_status("bucket2", MEDIUM_FILE_COUNT, MEDIUM_TOTAL_SIZE, {})
    state.save_bucket_status("bucket3", LARGE_FILE_COUNT, LARGE_TOTAL_SIZE, {})

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
            DEFAULT_BUCKET, INFO_FILE_COUNT, INFO_TOTAL_SIZE, INFO_STORAGE, scan_complete=True
        )

        info = state.get_bucket_info(DEFAULT_BUCKET)

        assert info["bucket"] == DEFAULT_BUCKET
        assert info["file_count"] == INFO_FILE_COUNT
        assert info["total_size"] == INFO_TOTAL_SIZE
        assert info["scan_complete"] == 1
        storage_classes = json.loads(info["storage_class_counts"])
        assert storage_classes == INFO_STORAGE

    def test_migration_state_v2_get_bucket_info_nonexistent(self, tmp_path: Path):
        """MigrationStateV2.get_bucket_info returns empty dict for missing bucket."""
        db_path = tmp_path / "test.db"
        state = MigrationStateV2(str(db_path))

        info = state.get_bucket_info("nonexistent-bucket")

        assert not info


def test_migration_state_v2_get_scan_summary(tmp_path: Path):
    """MigrationStateV2.get_scan_summary aggregates scan data."""
    db_path = tmp_path / "test.db"
    state = MigrationStateV2(str(db_path))

    state.add_file("b1", "k1", SMALL_TOTAL_SIZE, "e1", "STANDARD", "2025-10-31T00:00:00Z")
    state.add_file("b1", "k2", SMALL_TOTAL_SIZE, "e2", "GLACIER", "2025-10-31T00:00:00Z")
    state.add_file("b2", "k3", SMALL_TOTAL_SIZE, "e3", "STANDARD", "2025-10-31T00:00:00Z")

    state.save_bucket_status(
        "b1", 2, 2 * SMALL_TOTAL_SIZE, {"STANDARD": 1, "GLACIER": 1}, scan_complete=True
    )
    state.save_bucket_status("b2", 1, SMALL_TOTAL_SIZE, {"STANDARD": 1}, scan_complete=True)
    state.save_bucket_status(
        "b3",
        INCOMPLETE_FILE_COUNT,
        INCOMPLETE_TOTAL_SIZE,
        {"STANDARD": INCOMPLETE_FILE_COUNT},
        scan_complete=False,
    )

    summary = state.get_scan_summary()

    assert summary["bucket_count"] == COMPLETED_BUCKET_COUNT
    assert summary["total_files"] == SUMMARY_FILE_TOTAL
    assert summary["total_size"] == 3 * SMALL_TOTAL_SIZE
    assert summary["storage_classes"]["STANDARD"] == SUMMARY_STANDARD_COUNT
    assert summary["storage_classes"]["GLACIER"] == SUMMARY_GLACIER_COUNT


def test_migration_state_v2_get_current_phase_default(tmp_path: Path):
    """MigrationStateV2.get_current_phase returns SCANNING by default."""
    db_path = tmp_path / "test.db"
    state = MigrationStateV2(str(db_path))

    phase = state.get_current_phase()

    assert phase == Phase.SCANNING


def test_migration_state_v2_set_current_phase(tmp_path: Path):
    """MigrationStateV2.set_current_phase updates phase."""
    db_path = tmp_path / "test.db"
    state = MigrationStateV2(str(db_path))

    state.set_current_phase(Phase.GLACIER_RESTORE)
    phase = state.get_current_phase()

    assert phase == Phase.GLACIER_RESTORE


def test_migration_state_v2_set_current_phase_persists(tmp_path: Path):
    """MigrationStateV2 phase change persists across instances."""
    db_path = tmp_path / "test.db"

    state1 = MigrationStateV2(str(db_path))
    state1.set_current_phase(Phase.GLACIER_WAIT)

    state2 = MigrationStateV2(str(db_path))
    phase = state2.get_current_phase()

    assert phase == Phase.GLACIER_WAIT


def test_migration_state_v2_phase_transition_sequence(tmp_path: Path):
    """MigrationStateV2 supports full phase transition sequence."""
    db_path = tmp_path / "test.db"
    state = MigrationStateV2(str(db_path))

    phases = list(Phase)

    for expected_phase in phases:
        state.set_current_phase(expected_phase)
        assert state.get_current_phase() == expected_phase
