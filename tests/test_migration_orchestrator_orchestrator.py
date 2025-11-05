"""Unit tests for BucketMigrationOrchestrator class from migration_orchestrator.py

Tests cover:
- Multi-bucket migration orchestration
- Error handling for drive and migration errors
- Completion status reporting
"""

from unittest import mock

import pytest

from migration_orchestrator import BucketMigrationOrchestrator
from migration_state_v2 import Phase


@pytest.fixture
def mock_dependencies(tmp_path):
    """Create mock dependencies"""
    mock_s3 = mock.Mock()
    mock_state = mock.Mock()
    mock_drive_checker = mock.Mock()
    mock_bucket_migrator = mock.Mock()
    base_path = tmp_path / "migration"
    base_path.mkdir()

    return {
        "s3": mock_s3,
        "state": mock_state,
        "base_path": base_path,
        "drive_checker": mock_drive_checker,
        "bucket_migrator": mock_bucket_migrator,
    }


@pytest.fixture
def orchestrator(mock_dependencies):
    """Create BucketMigrationOrchestrator instance"""
    return BucketMigrationOrchestrator(
        mock_dependencies["s3"],
        mock_dependencies["state"],
        mock_dependencies["base_path"],
        mock_dependencies["drive_checker"],
        mock_dependencies["bucket_migrator"],
    )


class TestOrchestratorBasicMigration:
    """Tests for basic multi-bucket migration orchestration"""

    def test_migrate_all_buckets_single_bucket(self, orchestrator, mock_dependencies):
        """Test migrate_all_buckets with single bucket"""
        mock_dependencies["state"].get_all_buckets.return_value = ["bucket-1"]
        mock_dependencies["state"].get_completed_buckets_for_phase.return_value = []

        with mock.patch("builtins.print"):
            orchestrator.migrate_all_buckets()

        mock_dependencies["drive_checker"].check_available.assert_called_once()
        mock_dependencies["bucket_migrator"].process_bucket.assert_called_once_with("bucket-1")

    def test_migrate_all_buckets_multiple_buckets(self, orchestrator, mock_dependencies):
        """Test migrate_all_buckets with multiple buckets"""
        buckets = ["bucket-1", "bucket-2", "bucket-3"]
        mock_dependencies["state"].get_all_buckets.return_value = buckets
        mock_dependencies["state"].get_completed_buckets_for_phase.return_value = []

        with mock.patch("builtins.print"):
            orchestrator.migrate_all_buckets()

        assert mock_dependencies["bucket_migrator"].process_bucket.call_count == 3
        calls = [
            mock.call("bucket-1"),
            mock.call("bucket-2"),
            mock.call("bucket-3"),
        ]
        mock_dependencies["bucket_migrator"].process_bucket.assert_has_calls(calls)


class TestOrchestratorCompletedBuckets:
    """Tests for orchestrator handling of already-completed buckets"""

    def test_migrate_all_buckets_skips_already_completed(self, orchestrator, mock_dependencies):
        """Test migrate_all_buckets skips already completed buckets"""
        all_buckets = ["bucket-1", "bucket-2"]
        completed_buckets = ["bucket-1"]
        mock_dependencies["state"].get_all_buckets.return_value = all_buckets
        mock_dependencies["state"].get_completed_buckets_for_phase.return_value = completed_buckets

        with mock.patch("builtins.print"):
            orchestrator.migrate_all_buckets()

        # Only bucket-2 should be processed
        mock_dependencies["bucket_migrator"].process_bucket.assert_called_once_with("bucket-2")

    def test_migrate_all_buckets_all_already_complete(self, orchestrator, mock_dependencies):
        """Test migrate_all_buckets when all buckets are complete"""
        all_buckets = ["bucket-1", "bucket-2"]
        mock_dependencies["state"].get_all_buckets.return_value = all_buckets
        mock_dependencies["state"].get_completed_buckets_for_phase.return_value = all_buckets

        with mock.patch("builtins.print") as mock_print:
            orchestrator.migrate_all_buckets()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "already migrated" in printed_text


class TestOrchestratorInterruption:
    """Tests for orchestrator interruption handling"""

    def test_migrate_all_buckets_respects_interrupted_flag(self, orchestrator, mock_dependencies):
        """Test migrate_all_buckets stops when interrupted"""
        all_buckets = ["bucket-1", "bucket-2", "bucket-3"]
        mock_dependencies["state"].get_all_buckets.return_value = all_buckets
        mock_dependencies["state"].get_completed_buckets_for_phase.return_value = []

        # Set interrupted flag during processing
        def side_effect(*args, **kwargs):
            orchestrator.interrupted = True

        mock_dependencies["bucket_migrator"].process_bucket.side_effect = side_effect

        with mock.patch("builtins.print"):
            orchestrator.migrate_all_buckets()

        # Only first bucket should be processed before interruption
        assert mock_dependencies["bucket_migrator"].process_bucket.call_count == 1


class TestSingleBucketMigration:
    """Tests for single bucket migration operations"""

    def test_migrate_single_bucket_success(self, orchestrator, mock_dependencies):
        """Test _migrate_single_bucket successful processing"""
        with mock.patch("builtins.print"):
            orchestrator._migrate_single_bucket(1, "bucket-1", 3)

        mock_dependencies["drive_checker"].check_available.assert_called_once()
        mock_dependencies["bucket_migrator"].process_bucket.assert_called_once_with("bucket-1")


class TestSingleBucketDriveErrors:
    """Tests for single bucket migration drive error handling"""

    def test_migrate_single_bucket_handles_file_not_found_error(
        self, orchestrator, mock_dependencies
    ):
        """Test _migrate_single_bucket handles FileNotFoundError"""
        mock_dependencies["bucket_migrator"].process_bucket.side_effect = FileNotFoundError(
            "Local path not found"
        )

        with mock.patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                orchestrator._migrate_single_bucket(1, "bucket-1", 1)

        assert exc_info.value.code == 1

    def test_migrate_single_bucket_handles_permission_error(self, orchestrator, mock_dependencies):
        """Test _migrate_single_bucket handles PermissionError"""
        mock_dependencies["bucket_migrator"].process_bucket.side_effect = PermissionError(
            "Permission denied"
        )

        with mock.patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                orchestrator._migrate_single_bucket(1, "bucket-1", 1)

        assert exc_info.value.code == 1

    def test_migrate_single_bucket_handles_oserror(self, orchestrator, mock_dependencies):
        """Test _migrate_single_bucket handles OSError"""
        mock_dependencies["bucket_migrator"].process_bucket.side_effect = OSError(
            "Drive disconnected"
        )

        with mock.patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                orchestrator._migrate_single_bucket(1, "bucket-1", 1)

        assert exc_info.value.code == 1


class TestSingleBucketMigrationErrors:
    """Tests for single bucket migration error handling"""

    def test_migrate_single_bucket_handles_runtime_error(self, orchestrator, mock_dependencies):
        """Test _migrate_single_bucket handles RuntimeError from migration"""
        mock_dependencies["bucket_migrator"].process_bucket.side_effect = RuntimeError(
            "Sync failed"
        )

        with mock.patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                orchestrator._migrate_single_bucket(1, "bucket-1", 1)

        assert exc_info.value.code == 1

    def test_migrate_single_bucket_handles_value_error(self, orchestrator, mock_dependencies):
        """Test _migrate_single_bucket handles ValueError from verification"""
        mock_dependencies["bucket_migrator"].process_bucket.side_effect = ValueError(
            "File count mismatch"
        )

        with mock.patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                orchestrator._migrate_single_bucket(1, "bucket-1", 1)

        assert exc_info.value.code == 1


class TestErrorHandlers:
    """Tests for global error handler functions"""

    def test_handle_drive_error_prints_error_message(self, mock_dependencies):
        """Test handle_drive_error prints proper error message"""
        from migration_orchestrator import handle_drive_error

        error = FileNotFoundError("Drive not found")

        with mock.patch("builtins.print") as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                handle_drive_error(error)

        assert exc_info.value.code == 1
        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "Drive error" in printed_text
        assert "MIGRATION INTERRUPTED" in printed_text

    def test_handle_migration_error_prints_error_details(self, mock_dependencies):
        """Test handle_migration_error prints error details"""
        from migration_orchestrator import handle_migration_error

        error = RuntimeError("Sync failed")
        bucket = "test-bucket"

        with mock.patch("builtins.print") as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                handle_migration_error(bucket, error)

        assert exc_info.value.code == 1
        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "MIGRATION STOPPED" in printed_text
        assert "test-bucket" in printed_text


class TestCompletionStatusReporting:
    """Tests for completion status reporting"""

    def test_print_completion_status_all_complete(self, orchestrator, mock_dependencies):
        """Test _print_completion_status when all buckets complete"""
        all_buckets = ["bucket-1", "bucket-2"]
        mock_dependencies["state"].get_completed_buckets_for_phase.return_value = all_buckets

        with mock.patch("builtins.print") as mock_print:
            orchestrator._print_completion_status(all_buckets)

        mock_dependencies["state"].set_current_phase.assert_called_once_with(Phase.COMPLETE)
        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "PHASE 4 COMPLETE" in printed_text

    def test_print_completion_status_partial_complete(self, orchestrator, mock_dependencies):
        """Test _print_completion_status when some buckets remain"""
        all_buckets = ["bucket-1", "bucket-2", "bucket-3"]
        completed_buckets = ["bucket-1"]
        mock_dependencies["state"].get_completed_buckets_for_phase.return_value = completed_buckets

        with mock.patch("builtins.print") as mock_print:
            orchestrator._print_completion_status(all_buckets)

        mock_dependencies["state"].set_current_phase.assert_not_called()
        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "MIGRATION PAUSED" in printed_text
        assert "Completed: 1/3" in printed_text
        assert "Remaining: 2" in printed_text
