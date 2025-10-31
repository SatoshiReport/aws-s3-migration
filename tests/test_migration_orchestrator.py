"""Comprehensive unit tests for migration_orchestrator.py

Tests cover:
- BucketMigrator: Full pipeline, user input handling, verification
- StatusReporter: Status display for all phases
- BucketMigrationOrchestrator: Multi-bucket migration and error handling
"""

from unittest import mock

import pytest

from migration_orchestrator import (
    BucketMigrationOrchestrator,
    BucketMigrator,
    StatusReporter,
)
from migration_state_v2 import Phase


class TestBucketMigrator:
    """Tests for BucketMigrator class"""

    @pytest.fixture
    def mock_dependencies(self, tmp_path):
        """Create mock dependencies for BucketMigrator"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock()
        base_path = tmp_path / "migration"
        base_path.mkdir()

        return {
            "s3": mock_s3,
            "state": mock_state,
            "base_path": base_path,
        }

    @pytest.fixture
    def migrator(self, mock_dependencies):
        """Create BucketMigrator instance with mocked dependencies"""
        with (
            mock.patch("migration_orchestrator.BucketSyncer"),
            mock.patch("migration_orchestrator.BucketVerifier"),
            mock.patch("migration_orchestrator.BucketDeleter"),
        ):
            migrator = BucketMigrator(
                mock_dependencies["s3"],
                mock_dependencies["state"],
                mock_dependencies["base_path"],
            )
            migrator.syncer = mock.Mock()
            migrator.verifier = mock.Mock()
            migrator.deleter = mock.Mock()
        return migrator

    def test_process_bucket_first_time_sync_verify_delete(self, migrator, mock_dependencies):
        """Test process_bucket for first time: sync → verify → delete pipeline"""
        bucket = "test-bucket"
        bucket_info = {
            "sync_complete": False,
            "verify_complete": False,
            "delete_complete": False,
            "file_count": 100,
            "total_size": 1024000,
            "local_file_count": 100,
            "verified_file_count": 100,
            "size_verified_count": 100,
            "checksum_verified_count": 100,
            "total_bytes_verified": 1024000,
        }
        mock_dependencies["state"].get_bucket_info.return_value = bucket_info

        verify_results = {
            "verified_count": 100,
            "size_verified": 100,
            "checksum_verified": 100,
            "total_bytes_verified": 1024000,
            "local_file_count": 100,
        }
        migrator.verifier.verify_bucket.return_value = verify_results

        with mock.patch("builtins.input", return_value="yes"):
            migrator.process_bucket(bucket)

        # Verify sync was called
        migrator.syncer.sync_bucket.assert_called_once_with(bucket)
        mock_dependencies["state"].mark_bucket_sync_complete.assert_called_once_with(bucket)

        # Verify verification was called
        migrator.verifier.verify_bucket.assert_called_once_with(bucket)
        assert mock_dependencies["state"].mark_bucket_verify_complete.called

        # Verify deletion was called
        migrator.deleter.delete_bucket.assert_called_once_with(bucket)
        mock_dependencies["state"].mark_bucket_delete_complete.assert_called_once_with(bucket)

    def test_process_bucket_already_synced_skips_sync(self, migrator, mock_dependencies):
        """Test process_bucket skips sync if already complete"""
        bucket = "test-bucket"
        bucket_info = {
            "sync_complete": True,
            "verify_complete": False,
            "delete_complete": False,
            "file_count": 50,
            "total_size": 512000,
            "local_file_count": 50,
            "verified_file_count": 50,
            "size_verified_count": 50,
            "checksum_verified_count": 50,
            "total_bytes_verified": 512000,
        }
        mock_dependencies["state"].get_bucket_info.return_value = bucket_info

        verify_results = {
            "verified_count": 50,
            "size_verified": 50,
            "checksum_verified": 50,
            "total_bytes_verified": 512000,
            "local_file_count": 50,
        }
        migrator.verifier.verify_bucket.return_value = verify_results

        with mock.patch("builtins.input", return_value="yes"):
            migrator.process_bucket(bucket)

        # Verify sync was NOT called
        migrator.syncer.sync_bucket.assert_not_called()

    def test_process_bucket_already_verified_recomputes_stats(self, migrator, mock_dependencies):
        """Test process_bucket re-verifies when verify_complete but missing stats"""
        bucket = "test-bucket"
        bucket_info = {
            "sync_complete": True,
            "verify_complete": True,
            "delete_complete": False,
            "file_count": 75,
            "total_size": 768000,
            "verified_file_count": None,  # Missing stats
            "local_file_count": 75,
            "size_verified_count": 75,
            "checksum_verified_count": 75,
            "total_bytes_verified": 768000,
        }
        mock_dependencies["state"].get_bucket_info.return_value = bucket_info

        verify_results = {
            "verified_count": 75,
            "size_verified": 75,
            "checksum_verified": 75,
            "total_bytes_verified": 768000,
            "local_file_count": 75,
        }
        migrator.verifier.verify_bucket.return_value = verify_results

        # After verification, update bucket_info with verified stats
        def update_bucket_info_on_verify_complete(bucket_name, **kwargs):
            bucket_info["verified_file_count"] = 75

        mock_dependencies["state"].mark_bucket_verify_complete.side_effect = (
            update_bucket_info_on_verify_complete
        )

        with mock.patch("builtins.input", return_value="yes"):
            migrator.process_bucket(bucket)

        # Verify sync was NOT called, but verify was
        migrator.syncer.sync_bucket.assert_not_called()
        migrator.verifier.verify_bucket.assert_called_once()

    def test_process_bucket_already_deleted_skips_delete(self, migrator, mock_dependencies):
        """Test process_bucket skips delete if already complete"""
        bucket = "test-bucket"
        bucket_info = {
            "sync_complete": True,
            "verify_complete": True,
            "delete_complete": True,
            "file_count": 10,
            "total_size": 102400,
            "verified_file_count": 10,
            "local_file_count": 10,
            "size_verified_count": 10,
            "checksum_verified_count": 10,
            "total_bytes_verified": 102400,
        }
        mock_dependencies["state"].get_bucket_info.return_value = bucket_info

        migrator.process_bucket(bucket)

        # Verify sync and delete were NOT called
        migrator.syncer.sync_bucket.assert_not_called()
        migrator.deleter.delete_bucket.assert_not_called()

    def test_delete_with_confirmation_user_confirms_yes(self, migrator, mock_dependencies):
        """Test _delete_with_confirmation when user inputs 'yes'"""
        bucket = "test-bucket"
        bucket_info = {
            "file_count": 100,
            "total_size": 1024000,
            "local_file_count": 100,
            "verified_file_count": 100,
            "size_verified_count": 100,
            "checksum_verified_count": 100,
            "total_bytes_verified": 1024000,
        }

        with mock.patch("builtins.input", return_value="yes"):
            migrator._delete_with_confirmation(bucket, bucket_info)

        migrator.deleter.delete_bucket.assert_called_once_with(bucket)
        mock_dependencies["state"].mark_bucket_delete_complete.assert_called_once_with(bucket)

    def test_delete_with_confirmation_user_confirms_no(self, migrator, mock_dependencies):
        """Test _delete_with_confirmation when user inputs 'no'"""
        bucket = "test-bucket"
        bucket_info = {
            "file_count": 50,
            "total_size": 512000,
            "local_file_count": 50,
            "verified_file_count": 50,
            "size_verified_count": 50,
            "checksum_verified_count": 50,
            "total_bytes_verified": 512000,
        }

        with mock.patch("builtins.input", return_value="no"):
            migrator._delete_with_confirmation(bucket, bucket_info)

        # Verify deletion was NOT called
        migrator.deleter.delete_bucket.assert_not_called()
        mock_dependencies["state"].mark_bucket_delete_complete.assert_not_called()

    def test_delete_with_confirmation_user_confirms_other_input(self, migrator, mock_dependencies):
        """Test _delete_with_confirmation with non-yes, non-no input"""
        bucket = "test-bucket"
        bucket_info = {
            "file_count": 75,
            "total_size": 768000,
            "local_file_count": 75,
            "verified_file_count": 75,
            "size_verified_count": 75,
            "checksum_verified_count": 75,
            "total_bytes_verified": 768000,
        }

        with mock.patch("builtins.input", return_value="maybe"):
            migrator._delete_with_confirmation(bucket, bucket_info)

        # Verify deletion was NOT called for non-yes input
        migrator.deleter.delete_bucket.assert_not_called()

    def test_show_verification_summary_formats_output(self, migrator, mock_dependencies):
        """Test _show_verification_summary displays all stats correctly"""
        bucket = "test-bucket"
        bucket_info = {
            "file_count": 1000,
            "total_size": 10737418240,  # 10 GB
            "local_file_count": 1000,
            "verified_file_count": 1000,
            "size_verified_count": 1000,
            "checksum_verified_count": 1000,
            "total_bytes_verified": 10737418240,
        }

        with mock.patch("builtins.print") as mock_print:
            migrator._show_verification_summary(bucket, bucket_info)

        # Verify summary output includes key information
        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "VERIFICATION SUMMARY" in printed_text
        assert "1,000" in printed_text  # file count formatted
        assert "Size verified" in printed_text

    def test_show_verification_summary_matches_verified_file_count(
        self, migrator, mock_dependencies
    ):
        """Test _show_verification_summary with all files verified"""
        bucket = "test-bucket"
        bucket_info = {
            "file_count": 500,
            "total_size": 5242880,  # 5 MB
            "local_file_count": 500,
            "verified_file_count": 500,
            "size_verified_count": 500,
            "checksum_verified_count": 500,
            "total_bytes_verified": 5242880,
        }

        with mock.patch("builtins.print"):
            migrator._show_verification_summary(bucket, bucket_info)

        # Should complete without raising an error
        assert True


class TestStatusReporter:
    """Tests for StatusReporter class"""

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock()

    @pytest.fixture
    def reporter(self, mock_state):
        """Create StatusReporter instance"""
        return StatusReporter(mock_state)

    def test_show_status_scanning_phase(self, reporter, mock_state):
        """Test show_status for SCANNING phase"""
        mock_state.get_current_phase.return_value = Phase.SCANNING
        mock_state.get_all_buckets.return_value = []
        mock_state.get_scan_summary.return_value = {
            "bucket_count": 0,
            "total_files": 0,
            "total_size": 0,
        }

        with mock.patch("builtins.print") as mock_print:
            reporter.show_status()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "MIGRATION STATUS" in printed_text
        assert "scanning" in printed_text.lower()

    def test_show_status_glacier_restore_phase_shows_summary(self, reporter, mock_state):
        """Test show_status for GLACIER_RESTORE phase shows scan summary"""
        mock_state.get_current_phase.return_value = Phase.GLACIER_RESTORE
        mock_state.get_all_buckets.return_value = ["bucket-1", "bucket-2"]
        mock_state.get_scan_summary.return_value = {
            "bucket_count": 2,
            "total_files": 1000,
            "total_size": 10737418240,
        }
        mock_state.get_completed_buckets_for_phase.return_value = []

        bucket_infos = [
            {
                "file_count": 500,
                "total_size": 5368709120,
                "sync_complete": False,
                "verify_complete": False,
                "delete_complete": False,
            },
            {
                "file_count": 500,
                "total_size": 5368709120,
                "sync_complete": False,
                "verify_complete": False,
                "delete_complete": False,
            },
        ]
        mock_state.get_bucket_info.side_effect = bucket_infos

        with mock.patch("builtins.print") as mock_print:
            reporter.show_status()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "Overall Summary" in printed_text
        assert "Total Buckets: 2" in printed_text
        assert "Total Files: 1,000" in printed_text

    def test_show_status_shows_bucket_progress(self, reporter, mock_state):
        """Test show_status displays bucket progress"""
        mock_state.get_current_phase.return_value = Phase.SYNCING
        mock_state.get_all_buckets.return_value = ["bucket-1", "bucket-2", "bucket-3"]
        mock_state.get_scan_summary.return_value = {
            "bucket_count": 3,
            "total_files": 1500,
            "total_size": 15000000000,
        }
        mock_state.get_completed_buckets_for_phase.return_value = ["bucket-1"]

        bucket_infos = [
            {
                "file_count": 500,
                "total_size": 5000000000,
                "sync_complete": True,
                "verify_complete": True,
                "delete_complete": True,
            },
            {
                "file_count": 500,
                "total_size": 5000000000,
                "sync_complete": False,
                "verify_complete": False,
                "delete_complete": False,
            },
            {
                "file_count": 500,
                "total_size": 5000000000,
                "sync_complete": False,
                "verify_complete": False,
                "delete_complete": False,
            },
        ]
        mock_state.get_bucket_info.side_effect = bucket_infos

        with mock.patch("builtins.print") as mock_print:
            reporter.show_status()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "Bucket Progress" in printed_text
        assert "Completed: 1/3" in printed_text

    def test_show_status_displays_bucket_details(self, reporter, mock_state):
        """Test show_status shows individual bucket details"""
        mock_state.get_current_phase.return_value = Phase.SYNCING
        mock_state.get_all_buckets.return_value = ["bucket-1"]
        mock_state.get_scan_summary.return_value = {
            "bucket_count": 1,
            "total_files": 100,
            "total_size": 1000000,
        }
        mock_state.get_completed_buckets_for_phase.return_value = []

        mock_state.get_bucket_info.return_value = {
            "file_count": 100,
            "total_size": 1000000,
            "sync_complete": True,
            "verify_complete": False,
            "delete_complete": False,
        }

        with mock.patch("builtins.print") as mock_print:
            reporter.show_status()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "bucket-1" in printed_text
        assert "100" in printed_text

    def test_show_status_no_buckets(self, reporter, mock_state):
        """Test show_status when no buckets exist"""
        mock_state.get_current_phase.return_value = Phase.SCANNING
        mock_state.get_all_buckets.return_value = []
        mock_state.get_scan_summary.return_value = {
            "bucket_count": 0,
            "total_files": 0,
            "total_size": 0,
        }

        with mock.patch("builtins.print") as mock_print:
            reporter.show_status()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "MIGRATION STATUS" in printed_text

    def test_show_status_complete_phase(self, reporter, mock_state):
        """Test show_status for COMPLETE phase"""
        mock_state.get_current_phase.return_value = Phase.COMPLETE
        mock_state.get_all_buckets.return_value = ["bucket-1"]
        mock_state.get_scan_summary.return_value = {
            "bucket_count": 1,
            "total_files": 100,
            "total_size": 1000000,
        }
        mock_state.get_completed_buckets_for_phase.return_value = ["bucket-1"]
        mock_state.get_bucket_info.return_value = {
            "file_count": 100,
            "total_size": 1000000,
            "sync_complete": True,
            "verify_complete": True,
            "delete_complete": True,
        }

        with mock.patch("builtins.print") as mock_print:
            reporter.show_status()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "MIGRATION STATUS" in printed_text


class TestBucketMigrationOrchestrator:
    """Tests for BucketMigrationOrchestrator class"""

    @pytest.fixture
    def mock_dependencies(self, tmp_path):
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
    def orchestrator(self, mock_dependencies):
        """Create BucketMigrationOrchestrator instance"""
        return BucketMigrationOrchestrator(
            mock_dependencies["s3"],
            mock_dependencies["state"],
            mock_dependencies["base_path"],
            mock_dependencies["drive_checker"],
            mock_dependencies["bucket_migrator"],
        )

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

    def test_migrate_single_bucket_success(self, orchestrator, mock_dependencies):
        """Test _migrate_single_bucket successful processing"""
        with mock.patch("builtins.print"):
            orchestrator._migrate_single_bucket(1, "bucket-1", 3)

        mock_dependencies["drive_checker"].check_available.assert_called_once()
        mock_dependencies["bucket_migrator"].process_bucket.assert_called_once_with("bucket-1")

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

    def test_handle_drive_error_prints_error_message(self, orchestrator, mock_dependencies):
        """Test _handle_drive_error prints proper error message"""
        error = FileNotFoundError("Drive not found")

        with mock.patch("builtins.print") as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                orchestrator._handle_drive_error(error)

        assert exc_info.value.code == 1
        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "Drive error" in printed_text
        assert "MIGRATION INTERRUPTED" in printed_text

    def test_handle_migration_error_prints_error_details(self, orchestrator, mock_dependencies):
        """Test _handle_migration_error prints error details"""
        error = RuntimeError("Sync failed")
        bucket = "test-bucket"

        with mock.patch("builtins.print") as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                orchestrator._handle_migration_error(bucket, error)

        assert exc_info.value.code == 1
        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "MIGRATION STOPPED" in printed_text
        assert "test-bucket" in printed_text

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


class TestIntegrationScenarios:
    """Integration tests for complex scenarios"""

    @pytest.fixture
    def mock_dependencies(self, tmp_path):
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

    def test_full_bucket_migration_pipeline(self, mock_dependencies):
        """Test complete migration pipeline: sync → verify → delete"""
        with (
            mock.patch("migration_orchestrator.BucketSyncer"),
            mock.patch("migration_orchestrator.BucketVerifier"),
            mock.patch("migration_orchestrator.BucketDeleter"),
        ):
            migrator = BucketMigrator(
                mock_dependencies["s3"],
                mock_dependencies["state"],
                mock_dependencies["base_path"],
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
        mock_dependencies["state"].get_bucket_info.return_value = bucket_info

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

    def test_multi_bucket_orchestration_with_one_error(self, mock_dependencies):
        """Test orchestration continues despite error in one bucket"""
        mock_bucket_migrator = mock.Mock()
        orchestrator = BucketMigrationOrchestrator(
            mock_dependencies["s3"],
            mock_dependencies["state"],
            mock_dependencies["base_path"],
            mock_dependencies["drive_checker"],
            mock_bucket_migrator,
        )

        all_buckets = ["bucket-1", "bucket-2"]
        mock_dependencies["state"].get_all_buckets.return_value = all_buckets
        mock_dependencies["state"].get_completed_buckets_for_phase.return_value = []

        # First bucket fails, exit occurs
        mock_bucket_migrator.process_bucket.side_effect = RuntimeError("Sync failed")

        with mock.patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                orchestrator.migrate_all_buckets()

        assert exc_info.value.code == 1

    def test_resumable_migration_state_preserved(self, mock_dependencies):
        """Test that migration state is preserved for resumption"""
        mock_bucket_migrator = mock.Mock()
        orchestrator = BucketMigrationOrchestrator(
            mock_dependencies["s3"],
            mock_dependencies["state"],
            mock_dependencies["base_path"],
            mock_dependencies["drive_checker"],
            mock_bucket_migrator,
        )

        all_buckets = ["bucket-1", "bucket-2", "bucket-3"]
        completed_buckets = ["bucket-1", "bucket-2"]  # Two already done
        mock_dependencies["state"].get_all_buckets.return_value = all_buckets
        mock_dependencies["state"].get_completed_buckets_for_phase.return_value = completed_buckets

        with mock.patch("builtins.print"):
            orchestrator.migrate_all_buckets()

        # Only bucket-3 should be processed
        mock_bucket_migrator.process_bucket.assert_called_once_with("bucket-3")
