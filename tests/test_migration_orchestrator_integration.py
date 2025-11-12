"""Integration tests for migration_orchestrator.py

Tests cover:
- Complete migration pipeline (sync → verify → delete)
- Multi-bucket orchestration with errors
- Resumable migration state preservation
"""

# pylint: disable=redefined-outer-name  # pytest fixtures

from unittest import mock

import pytest

from migration_orchestrator import (
    BucketMigrationOrchestrator,
    BucketMigrator,
)


@pytest.fixture
def mock_deps(tmp_path):
    """Create mock dependencies for integration tests"""
    mock_s3 = mock.Mock()
    mock_state = mock.Mock()
    mock_drive_checker = mock.Mock()
    base_path = tmp_path / "migration"
    base_path.mkdir()

    return {
        "s3": mock_s3,
        "state": mock_state,
        "base_path": base_path,
        "drive_checker": mock_drive_checker,
    }


def test_full_bucket_migration_pipeline(mock_deps):
    """Test complete migration pipeline: sync → verify → delete"""
    with (
        mock.patch("migration_orchestrator.BucketSyncer"),
        mock.patch("migration_orchestrator.BucketVerifier"),
        mock.patch("migration_orchestrator.BucketDeleter"),
    ):
        migrator = BucketMigrator(
            mock_deps["s3"],
            mock_deps["state"],
            mock_deps["base_path"],
        )
        migrator.syncer = mock.Mock()
        migrator.verifier = mock.Mock()
        migrator.deleter = mock.Mock()

    bucket = "test-bucket"
    bucket_info = {
        "sync_complete": False,
        "verify_complete": False,
        "delete_complete": False,
        "file_count": 100,
        "total_size": 1000000,
        "local_file_count": 100,
        "verified_file_count": 100,
        "size_verified_count": 100,
        "checksum_verified_count": 100,
        "total_bytes_verified": 1000000,
    }
    mock_deps["state"].get_bucket_info.return_value = bucket_info

    verify_results = {
        "verified_count": 100,
        "size_verified": 100,
        "checksum_verified": 100,
        "total_bytes_verified": 1000000,
        "local_file_count": 100,
    }
    migrator.verifier.verify_bucket.return_value = verify_results

    with mock.patch("builtins.input", return_value="yes"):
        migrator.process_bucket(bucket)

    # Verify all steps completed in order
    migrator.syncer.sync_bucket.assert_called_once()
    migrator.verifier.verify_bucket.assert_called_once()
    migrator.deleter.delete_bucket.assert_called_once()


def test_multi_bucket_orchestration_with_one_error(mock_deps):
    """Test orchestration continues despite error in one bucket"""
    mock_bucket_migrator = mock.Mock()
    orchestrator = BucketMigrationOrchestrator(
        mock_deps["s3"],
        mock_deps["state"],
        mock_deps["base_path"],
        mock_deps["drive_checker"],
        mock_bucket_migrator,
    )

    all_buckets = ["bucket-1", "bucket-2"]
    mock_deps["state"].get_all_buckets.return_value = all_buckets
    mock_deps["state"].get_completed_buckets_for_phase.return_value = []

    # First bucket fails, exit occurs
    mock_bucket_migrator.process_bucket.side_effect = RuntimeError("Sync failed")

    with mock.patch("builtins.print"):
        with pytest.raises(SystemExit) as exc_info:
            orchestrator.migrate_all_buckets()

    assert exc_info.value.code == 1


def test_resumable_migration_state_preserved(mock_deps):
    """Test that migration state is preserved for resumption"""
    mock_bucket_migrator = mock.Mock()
    orchestrator = BucketMigrationOrchestrator(
        mock_deps["s3"],
        mock_deps["state"],
        mock_deps["base_path"],
        mock_deps["drive_checker"],
        mock_bucket_migrator,
    )

    all_buckets = ["bucket-1", "bucket-2", "bucket-3"]
    completed_buckets = ["bucket-1", "bucket-2"]  # Two already done
    mock_deps["state"].get_all_buckets.return_value = all_buckets
    mock_deps["state"].get_completed_buckets_for_phase.return_value = completed_buckets

    with mock.patch("builtins.print"):
        orchestrator.migrate_all_buckets()

    # Only bucket-3 should be processed
    mock_bucket_migrator.process_bucket.assert_called_once_with("bucket-3")
