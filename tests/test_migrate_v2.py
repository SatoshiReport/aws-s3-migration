"""Comprehensive unit tests for migrate_v2.py with 80%+ coverage.

Tests cover:
- DriveChecker: check_available with various error scenarios
- S3MigrationV2: Initialization, signal handler, run() method for all phases
- Phase transitions and state management
- Reset confirmation handling (yes/no)
- create_migrator factory function
- main entry point with argparse handling
"""

import signal
import sys
from pathlib import Path
from unittest import mock

import pytest

from migrate_v2 import DriveChecker, S3MigrationV2, create_migrator, main
from migration_state_v2 import Phase


class TestDriveChecker:
    """Tests for DriveChecker class."""

    def test_initialization(self, tmp_path):
        """DriveChecker initializes with base path."""
        base_path = tmp_path / "s3_backup"
        checker = DriveChecker(base_path)
        assert checker.base_path == base_path

    def test_check_available_parent_does_not_exist(self, tmp_path, capsys):
        """check_available exits when parent directory does not exist."""
        # Create a path whose parent doesn't exist
        base_path = tmp_path / "nonexistent" / "s3_backup"
        checker = DriveChecker(base_path)

        with pytest.raises(SystemExit) as exc_info:
            checker.check_available()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "DRIVE NOT AVAILABLE" in captured.out
        assert "Expected:" in captured.out

    def test_check_available_parent_exists_creates_directory(self, tmp_path):
        """check_available creates base directory when parent exists."""
        base_path = tmp_path / "s3_backup"
        checker = DriveChecker(base_path)

        # Should not raise
        checker.check_available()

        # Directory should be created
        assert base_path.exists()
        assert base_path.is_dir()

    def test_check_available_directory_already_exists(self, tmp_path):
        """check_available succeeds if directory already exists."""
        base_path = tmp_path / "s3_backup"
        base_path.mkdir(parents=True)

        checker = DriveChecker(base_path)

        # Should not raise
        checker.check_available()
        assert base_path.exists()

    def test_check_available_permission_denied(self, tmp_path, capsys, monkeypatch):
        """check_available exits when directory creation raises PermissionError."""
        base_path = tmp_path / "s3_backup"
        checker = DriveChecker(base_path)

        # Mock mkdir to raise PermissionError
        with mock.patch.object(Path, "mkdir", side_effect=PermissionError()):
            with pytest.raises(SystemExit) as exc_info:
                checker.check_available()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "PERMISSION DENIED" in captured.out
        assert "Cannot write to destination:" in captured.out


class TestS3MigrationV2:
    """Tests for S3MigrationV2 main orchestrator."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for S3MigrationV2."""
        return {
            "state": mock.Mock(),
            "drive_checker": mock.Mock(),
            "scanner": mock.Mock(),
            "glacier_restorer": mock.Mock(),
            "glacier_waiter": mock.Mock(),
            "migration_orchestrator": mock.Mock(),
            "bucket_migrator": mock.Mock(),
            "status_reporter": mock.Mock(),
        }

    @pytest.fixture
    def migrator(self, mock_dependencies):
        """Create S3MigrationV2 instance with mocked dependencies."""
        migrator = S3MigrationV2(
            state=mock_dependencies["state"],
            drive_checker=mock_dependencies["drive_checker"],
            scanner=mock_dependencies["scanner"],
            glacier_restorer=mock_dependencies["glacier_restorer"],
            glacier_waiter=mock_dependencies["glacier_waiter"],
            migration_orchestrator=mock_dependencies["migration_orchestrator"],
            bucket_migrator=mock_dependencies["bucket_migrator"],
            status_reporter=mock_dependencies["status_reporter"],
        )
        # Set up mock attributes for signal handler
        mock_dependencies["scanner"].interrupted = False
        mock_dependencies["glacier_restorer"].interrupted = False
        mock_dependencies["glacier_waiter"].interrupted = False
        mock_dependencies["bucket_migrator"].interrupted = False
        mock_dependencies["bucket_migrator"].syncer = mock.Mock()
        mock_dependencies["bucket_migrator"].syncer.interrupted = False
        mock_dependencies["migration_orchestrator"].interrupted = False

        return migrator

    def test_initialization(self, mock_dependencies):
        """S3MigrationV2 initializes with all dependencies."""
        migrator = S3MigrationV2(
            state=mock_dependencies["state"],
            drive_checker=mock_dependencies["drive_checker"],
            scanner=mock_dependencies["scanner"],
            glacier_restorer=mock_dependencies["glacier_restorer"],
            glacier_waiter=mock_dependencies["glacier_waiter"],
            migration_orchestrator=mock_dependencies["migration_orchestrator"],
            bucket_migrator=mock_dependencies["bucket_migrator"],
            status_reporter=mock_dependencies["status_reporter"],
        )

        assert migrator.state == mock_dependencies["state"]
        assert migrator.drive_checker == mock_dependencies["drive_checker"]
        assert migrator.scanner == mock_dependencies["scanner"]
        assert migrator.glacier_restorer == mock_dependencies["glacier_restorer"]
        assert migrator.glacier_waiter == mock_dependencies["glacier_waiter"]
        assert migrator.bucket_migrator == mock_dependencies["bucket_migrator"]
        assert migrator.migration_orchestrator == mock_dependencies["migration_orchestrator"]
        assert migrator.status_reporter == mock_dependencies["status_reporter"]
        assert migrator.interrupted is False

    def test_signal_handler_sets_interrupted_flags(self, migrator, mock_dependencies):
        """Signal handler sets interrupted flag on all components."""
        # Setup mock attributes
        mock_dependencies["scanner"].interrupted = False
        mock_dependencies["glacier_restorer"].interrupted = False
        mock_dependencies["glacier_waiter"].interrupted = False
        mock_dependencies["bucket_migrator"].interrupted = False
        mock_dependencies["bucket_migrator"].syncer.interrupted = False
        mock_dependencies["migration_orchestrator"].interrupted = False

        with pytest.raises(SystemExit) as exc_info:
            migrator._signal_handler(signal.SIGINT, None)

        assert exc_info.value.code == 0
        assert migrator.interrupted is True
        assert mock_dependencies["scanner"].interrupted is True
        assert mock_dependencies["glacier_restorer"].interrupted is True
        assert mock_dependencies["glacier_waiter"].interrupted is True
        assert mock_dependencies["bucket_migrator"].interrupted is True
        assert mock_dependencies["bucket_migrator"].syncer.interrupted is True
        assert mock_dependencies["migration_orchestrator"].interrupted is True

    def test_signal_handler_prints_message(self, migrator, capsys):
        """Signal handler prints interruption message."""
        with pytest.raises(SystemExit):
            migrator._signal_handler(signal.SIGINT, None)

        captured = capsys.readouterr()
        assert "MIGRATION INTERRUPTED" in captured.out
        assert "State has been saved" in captured.out

    def test_run_already_complete(self, migrator, mock_dependencies, capsys):
        """run() shows completion message when already complete."""
        mock_dependencies["state"].get_current_phase.return_value = Phase.COMPLETE

        migrator.run()

        captured = capsys.readouterr()
        assert "Migration already complete!" in captured.out
        mock_dependencies["status_reporter"].show_status.assert_called_once()

    def test_run_from_scanning_phase(self, migrator, mock_dependencies, capsys):
        """run() executes all phases starting from SCANNING."""
        mock_dependencies["state"].get_current_phase.side_effect = [
            Phase.SCANNING,
            Phase.SYNCING,
            Phase.COMPLETE,
        ]

        migrator.run()

        # Verify all phases are called
        mock_dependencies["scanner"].scan_all_buckets.assert_called_once()
        mock_dependencies["glacier_restorer"].request_all_restores.assert_called_once()
        mock_dependencies["glacier_waiter"].wait_for_restores.assert_called_once()
        mock_dependencies["migration_orchestrator"].migrate_all_buckets.assert_called_once()

        captured = capsys.readouterr()
        assert "S3 MIGRATION V2" in captured.out

    def test_run_from_glacier_restore_phase(self, migrator, mock_dependencies):
        """run() executes from GLACIER_RESTORE phase."""
        mock_dependencies["state"].get_current_phase.side_effect = [
            Phase.GLACIER_RESTORE,
            Phase.SYNCING,
            Phase.COMPLETE,
        ]

        migrator.run()

        # Scanning should not be called
        mock_dependencies["scanner"].scan_all_buckets.assert_not_called()
        # But restore and subsequent phases should be called
        mock_dependencies["glacier_restorer"].request_all_restores.assert_called_once()
        mock_dependencies["glacier_waiter"].wait_for_restores.assert_called_once()

    def test_run_from_glacier_wait_phase(self, migrator, mock_dependencies):
        """run() executes from GLACIER_WAIT phase."""
        mock_dependencies["state"].get_current_phase.side_effect = [
            Phase.GLACIER_WAIT,
            Phase.SYNCING,
            Phase.COMPLETE,
        ]

        migrator.run()

        # Scanning and restore should not be called
        mock_dependencies["scanner"].scan_all_buckets.assert_not_called()
        mock_dependencies["glacier_restorer"].request_all_restores.assert_not_called()
        # Wait and sync should be called
        mock_dependencies["glacier_waiter"].wait_for_restores.assert_called_once()
        mock_dependencies["migration_orchestrator"].migrate_all_buckets.assert_called_once()

    def test_run_from_syncing_phase(self, migrator, mock_dependencies):
        """run() executes from SYNCING phase."""
        mock_dependencies["state"].get_current_phase.side_effect = [
            Phase.SYNCING,
            Phase.COMPLETE,
        ]

        migrator.run()

        # Only migration orchestrator should be called
        mock_dependencies["scanner"].scan_all_buckets.assert_not_called()
        mock_dependencies["glacier_restorer"].request_all_restores.assert_not_called()
        mock_dependencies["glacier_waiter"].wait_for_restores.assert_not_called()
        mock_dependencies["migration_orchestrator"].migrate_all_buckets.assert_called_once()

    def test_run_calls_drive_checker(self, migrator, mock_dependencies):
        """run() calls drive_checker before starting."""
        mock_dependencies["state"].get_current_phase.return_value = Phase.COMPLETE

        migrator.run()

        mock_dependencies["drive_checker"].check_available.assert_called_once()

    def test_run_prints_completion_message(self, migrator, mock_dependencies, capsys):
        """run() prints completion message at end."""
        mock_dependencies["state"].get_current_phase.side_effect = [
            Phase.SYNCING,
            Phase.COMPLETE,
        ]

        migrator.run()

        mock_dependencies["state"].set_current_phase.assert_called_with(Phase.COMPLETE)
        captured = capsys.readouterr()
        assert "MIGRATION COMPLETE!" in captured.out
        assert "All files have been migrated and verified" in captured.out

    def test_show_status(self, migrator, mock_dependencies):
        """show_status() delegates to status reporter."""
        migrator.show_status()
        mock_dependencies["status_reporter"].show_status.assert_called_once()

    def test_reset_with_yes_confirmation(self, migrator, mock_dependencies, capsys, monkeypatch):
        """reset() deletes state database when user confirms with 'yes'."""
        monkeypatch.setenv("STATE_DB_PATH", "/tmp/test.db")
        test_db = "/tmp/test_reset.db"

        # Create a temporary database file
        Path(test_db).touch()
        assert Path(test_db).exists()

        # Mock input to return 'yes'
        with mock.patch("builtins.input", return_value="yes"):
            with mock.patch("os.path.exists", return_value=True):
                with mock.patch("os.remove") as mock_remove:
                    migrator.reset()
                    mock_remove.assert_called_once()

    def test_reset_with_no_confirmation(self, migrator, capsys):
        """reset() cancels when user does not confirm."""
        with mock.patch("builtins.input", return_value="no"):
            migrator.reset()

        captured = capsys.readouterr()
        assert "Reset cancelled" in captured.out

    def test_reset_database_not_exists(self, migrator, capsys):
        """reset() handles missing database gracefully."""
        with mock.patch("builtins.input", return_value="yes"):
            with mock.patch("os.path.exists", return_value=False):
                migrator.reset()

        captured = capsys.readouterr()
        assert "No state database found" in captured.out

    def test_reset_case_insensitive_confirmation(self, migrator):
        """reset() handles uppercase confirmation (YES becomes yes via lower())."""
        with mock.patch("builtins.input", return_value="YES"):
            with mock.patch("os.path.exists", return_value=True):
                with mock.patch("os.remove") as mock_remove:
                    migrator.reset()
                    # Should delete because "YES".lower() == "yes"
                    mock_remove.assert_called_once()

    def test_run_handles_interrupted_scanning(self, migrator, mock_dependencies):
        """run() handles interruption during scanning."""

        # Set up to interrupt during scanning
        def interrupt_during_scan():
            migrator.interrupted = True

        mock_dependencies["scanner"].scan_all_buckets.side_effect = interrupt_during_scan
        mock_dependencies["state"].get_current_phase.return_value = Phase.SCANNING

        migrator.run()

        # Scanner should have been called
        mock_dependencies["scanner"].scan_all_buckets.assert_called_once()

    def test_phase_transitions_complete_workflow(self, migrator, mock_dependencies):
        """run() correctly transitions through all phases."""
        phase_sequence = [
            Phase.SCANNING,
            Phase.GLACIER_RESTORE,
            Phase.GLACIER_WAIT,
            Phase.SYNCING,
            Phase.COMPLETE,
        ]
        mock_dependencies["state"].get_current_phase.side_effect = phase_sequence

        migrator.run()

        # Verify all components were called
        mock_dependencies["scanner"].scan_all_buckets.assert_called_once()
        mock_dependencies["glacier_restorer"].request_all_restores.assert_called_once()
        mock_dependencies["glacier_waiter"].wait_for_restores.assert_called_once()
        mock_dependencies["migration_orchestrator"].migrate_all_buckets.assert_called_once()


class TestCreateMigrator:
    """Tests for create_migrator factory function."""

    @pytest.fixture
    def mock_config(self):
        """Mock config module."""
        with mock.patch("migrate_v2.config") as mock_cfg:
            mock_cfg.STATE_DB_PATH = "/tmp/state.db"
            mock_cfg.LOCAL_BASE_PATH = "/tmp/s3_backup"
            yield mock_cfg

    def test_create_migrator_returns_s3_migration_v2(self, mock_config):
        """create_migrator returns S3MigrationV2 instance."""
        with (
            mock.patch("migrate_v2.MigrationStateV2"),
            mock.patch("migrate_v2.boto3.client"),
            mock.patch("migrate_v2.Path"),
            mock.patch("migrate_v2.DriveChecker"),
            mock.patch("migrate_v2.BucketScanner"),
            mock.patch("migrate_v2.GlacierRestorer"),
            mock.patch("migrate_v2.GlacierWaiter"),
            mock.patch("migrate_v2.BucketMigrator"),
            mock.patch("migrate_v2.BucketMigrationOrchestrator"),
            mock.patch("migrate_v2.StatusReporter"),
        ):
            migrator = create_migrator()

            assert isinstance(migrator, S3MigrationV2)
            assert migrator.state is not None
            assert migrator.drive_checker is not None
            assert migrator.scanner is not None
            assert migrator.glacier_restorer is not None
            assert migrator.glacier_waiter is not None
            assert migrator.bucket_migrator is not None
            assert migrator.migration_orchestrator is not None
            assert migrator.status_reporter is not None

    def test_create_migrator_instantiates_all_dependencies(self, mock_config):
        """create_migrator creates all required dependencies."""
        with (
            mock.patch("migrate_v2.MigrationStateV2") as mock_state_class,
            mock.patch("migrate_v2.boto3.client") as mock_boto3,
            mock.patch("migrate_v2.Path"),
            mock.patch("migrate_v2.DriveChecker") as mock_drive_checker_class,
            mock.patch("migrate_v2.BucketScanner") as mock_scanner_class,
            mock.patch("migrate_v2.GlacierRestorer") as mock_restorer_class,
            mock.patch("migrate_v2.GlacierWaiter") as mock_waiter_class,
            mock.patch("migrate_v2.BucketMigrator") as mock_migrator_class,
            mock.patch("migrate_v2.BucketMigrationOrchestrator") as mock_orchestrator_class,
            mock.patch("migrate_v2.StatusReporter") as mock_reporter_class,
        ):

            create_migrator()

            # Verify all classes were instantiated
            mock_state_class.assert_called_once_with(mock_config.STATE_DB_PATH)
            mock_boto3.assert_called_once_with("s3")
            mock_drive_checker_class.assert_called_once()
            mock_scanner_class.assert_called_once()
            mock_restorer_class.assert_called_once()
            mock_waiter_class.assert_called_once()
            mock_migrator_class.assert_called_once()
            mock_orchestrator_class.assert_called_once()
            mock_reporter_class.assert_called_once()


class TestMain:
    """Tests for main entry point."""

    @pytest.fixture
    def mock_migrator(self):
        """Mock migrator instance."""
        with mock.patch("migrate_v2.create_migrator") as mock_create:
            mock_migrator_instance = mock.Mock(spec=S3MigrationV2)
            mock_create.return_value = mock_migrator_instance
            yield mock_migrator_instance

    def test_main_no_command_runs_migration(self, mock_migrator, monkeypatch):
        """main() runs migration when no command provided."""
        monkeypatch.setattr(sys, "argv", ["migrate_v2.py"])

        main()

        mock_migrator.run.assert_called_once()
        mock_migrator.show_status.assert_not_called()
        mock_migrator.reset.assert_not_called()

    def test_main_status_command_shows_status(self, mock_migrator, monkeypatch):
        """main() shows status when 'status' command provided."""
        monkeypatch.setattr(sys, "argv", ["migrate_v2.py", "status"])

        main()

        mock_migrator.show_status.assert_called_once()
        mock_migrator.run.assert_not_called()
        mock_migrator.reset.assert_not_called()

    def test_main_reset_command_resets_state(self, mock_migrator, monkeypatch):
        """main() resets state when 'reset' command provided."""
        monkeypatch.setattr(sys, "argv", ["migrate_v2.py", "reset"])

        main()

        mock_migrator.reset.assert_called_once()
        mock_migrator.run.assert_not_called()
        mock_migrator.show_status.assert_not_called()

    def test_main_creates_migrator(self, monkeypatch):
        """main() creates migrator instance."""
        monkeypatch.setattr(sys, "argv", ["migrate_v2.py"])

        with mock.patch("migrate_v2.create_migrator") as mock_create:
            mock_create.return_value = mock.Mock(spec=S3MigrationV2)
            main()

            mock_create.assert_called_once()

    def test_main_help_text(self, capsys, monkeypatch):
        """main() displays help with -h flag."""
        monkeypatch.setattr(sys, "argv", ["migrate_v2.py", "-h"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "S3 Bucket Migration Tool V2" in captured.out


class TestSignalHandlerIntegration:
    """Integration tests for signal handler."""

    def test_signal_handler_propagates_to_all_components(self, mock_dependencies):
        """Signal handler properly propagates interrupted flag to all components."""
        migrator = S3MigrationV2(
            state=mock_dependencies["state"],
            drive_checker=mock_dependencies["drive_checker"],
            scanner=mock_dependencies["scanner"],
            glacier_restorer=mock_dependencies["glacier_restorer"],
            glacier_waiter=mock_dependencies["glacier_waiter"],
            migration_orchestrator=mock_dependencies["migration_orchestrator"],
            bucket_migrator=mock_dependencies["bucket_migrator"],
            status_reporter=mock_dependencies["status_reporter"],
        )

        # Initialize interrupted attributes
        mock_dependencies["scanner"].interrupted = False
        mock_dependencies["glacier_restorer"].interrupted = False
        mock_dependencies["glacier_waiter"].interrupted = False
        mock_dependencies["bucket_migrator"].interrupted = False
        mock_dependencies["bucket_migrator"].syncer = mock.Mock()
        mock_dependencies["bucket_migrator"].syncer.interrupted = False
        mock_dependencies["migration_orchestrator"].interrupted = False

        with pytest.raises(SystemExit):
            migrator._signal_handler(signal.SIGINT, None)

        # Verify all flags are set
        assert migrator.interrupted is True
        assert mock_dependencies["scanner"].interrupted is True
        assert mock_dependencies["glacier_restorer"].interrupted is True
        assert mock_dependencies["glacier_waiter"].interrupted is True
        assert mock_dependencies["bucket_migrator"].interrupted is True
        assert mock_dependencies["migration_orchestrator"].interrupted is True


class TestResetEdgeCases:
    """Tests for edge cases in reset() functionality."""

    def test_reset_prints_header_message(self, tmp_path, capsys):
        """reset() prints reset migration header."""
        mock_state = mock.Mock()
        mock_drive_checker = mock.Mock()
        mock_scanner = mock.Mock()
        mock_glacier_restorer = mock.Mock()
        mock_glacier_waiter = mock.Mock()
        mock_bucket_migrator = mock.Mock()
        mock_migration_orchestrator = mock.Mock()
        mock_status_reporter = mock.Mock()

        migrator = S3MigrationV2(
            state=mock_state,
            drive_checker=mock_drive_checker,
            scanner=mock_scanner,
            glacier_restorer=mock_glacier_restorer,
            glacier_waiter=mock_glacier_waiter,
            migration_orchestrator=mock_migration_orchestrator,
            bucket_migrator=mock_bucket_migrator,
            status_reporter=mock_status_reporter,
        )

        with mock.patch("builtins.input", return_value="no"):
            migrator.reset()

        captured = capsys.readouterr()
        assert "RESET MIGRATION" in captured.out
        assert "delete all migration state" in captured.out


class TestRunPhaseEdgeCases:
    """Tests for edge cases in phase execution."""

    def test_run_skips_scanner_in_middle_phases(self):
        """run() does not call scanner for middle phases."""
        mock_state = mock.Mock()
        mock_drive_checker = mock.Mock()
        mock_scanner = mock.Mock()
        mock_glacier_restorer = mock.Mock()
        mock_glacier_waiter = mock.Mock()
        mock_bucket_migrator = mock.Mock()
        mock_migration_orchestrator = mock.Mock()
        mock_status_reporter = mock.Mock()

        migrator = S3MigrationV2(
            state=mock_state,
            drive_checker=mock_drive_checker,
            scanner=mock_scanner,
            glacier_restorer=mock_glacier_restorer,
            glacier_waiter=mock_glacier_waiter,
            migration_orchestrator=mock_migration_orchestrator,
            bucket_migrator=mock_bucket_migrator,
            status_reporter=mock_status_reporter,
        )

        # Start from GLACIER_RESTORE phase
        mock_state.get_current_phase.side_effect = [
            Phase.GLACIER_RESTORE,
            Phase.COMPLETE,
        ]

        migrator.run()

        # Scanner should NOT be called
        mock_scanner.scan_all_buckets.assert_not_called()
        # But restorer should
        mock_glacier_restorer.request_all_restores.assert_called_once()

    def test_run_completes_all_phase_transitions(self):
        """run() transitions through phases correctly."""
        mock_state = mock.Mock()
        mock_drive_checker = mock.Mock()
        mock_scanner = mock.Mock()
        mock_glacier_restorer = mock.Mock()
        mock_glacier_waiter = mock.Mock()
        mock_bucket_migrator = mock.Mock()
        mock_migration_orchestrator = mock.Mock()
        mock_status_reporter = mock.Mock()

        migrator = S3MigrationV2(
            state=mock_state,
            drive_checker=mock_drive_checker,
            scanner=mock_scanner,
            glacier_restorer=mock_glacier_restorer,
            glacier_waiter=mock_glacier_waiter,
            migration_orchestrator=mock_migration_orchestrator,
            bucket_migrator=mock_bucket_migrator,
            status_reporter=mock_status_reporter,
        )

        # Set up phase sequence
        mock_state.get_current_phase.side_effect = [
            Phase.SCANNING,
            Phase.GLACIER_RESTORE,
            Phase.GLACIER_WAIT,
            Phase.SYNCING,
            Phase.COMPLETE,
        ]

        migrator.run()

        # All phases should be executed
        assert mock_scanner.scan_all_buckets.called
        assert mock_glacier_restorer.request_all_restores.called
        assert mock_glacier_waiter.wait_for_restores.called
        assert mock_migration_orchestrator.migrate_all_buckets.called


class TestDriveCheckerEdgeCases:
    """Tests for edge cases in DriveChecker."""

    def test_check_available_creates_single_subdirectory(self, tmp_path):
        """check_available creates single subdirectory under existing parent."""
        nested_path = tmp_path / "s3_backup"
        checker = DriveChecker(nested_path)

        checker.check_available()

        # Directory should be created
        assert nested_path.exists()
        # Parent must already exist (requirement of check_available)
        assert nested_path.parent.exists()

    def test_check_available_idempotent(self, tmp_path):
        """check_available can be called multiple times safely."""
        base_path = tmp_path / "s3_backup"
        checker = DriveChecker(base_path)

        # Call twice
        checker.check_available()
        checker.check_available()

        # Should still exist
        assert base_path.exists()


class TestMainEdgeCases:
    """Tests for edge cases in main entry point."""

    def test_main_with_empty_args(self, monkeypatch):
        """main() runs migration with no command specified."""
        monkeypatch.setattr(sys, "argv", ["migrate_v2.py"])

        with mock.patch("migrate_v2.create_migrator") as mock_create:
            mock_migrator_instance = mock.Mock(spec=S3MigrationV2)
            mock_create.return_value = mock_migrator_instance

            main()

            mock_migrator_instance.run.assert_called_once()

    def test_main_parser_accepts_valid_commands(self, monkeypatch):
        """main() parser accepts status and reset commands."""
        for command in ["status", "reset"]:
            monkeypatch.setattr(sys, "argv", ["migrate_v2.py", command])

            with mock.patch("migrate_v2.create_migrator") as mock_create:
                mock_migrator_instance = mock.Mock(spec=S3MigrationV2)
                mock_create.return_value = mock_migrator_instance

                # Should not raise
                main()


class TestS3MigrationV2ErrorHandling:
    """Tests for error handling in S3MigrationV2."""

    def test_run_with_drive_check_failure(self):
        """run() exits if drive check fails."""
        mock_state = mock.Mock()
        mock_drive_checker = mock.Mock()
        mock_scanner = mock.Mock()
        mock_glacier_restorer = mock.Mock()
        mock_glacier_waiter = mock.Mock()
        mock_bucket_migrator = mock.Mock()
        mock_migration_orchestrator = mock.Mock()
        mock_status_reporter = mock.Mock()

        migrator = S3MigrationV2(
            state=mock_state,
            drive_checker=mock_drive_checker,
            scanner=mock_scanner,
            glacier_restorer=mock_glacier_restorer,
            glacier_waiter=mock_glacier_waiter,
            migration_orchestrator=mock_migration_orchestrator,
            bucket_migrator=mock_bucket_migrator,
            status_reporter=mock_status_reporter,
        )

        # Make drive check fail
        mock_drive_checker.check_available.side_effect = SystemExit(1)

        with pytest.raises(SystemExit):
            migrator.run()


@pytest.fixture
def mock_dependencies():
    """Fixture for mock dependencies used across tests."""
    return {
        "state": mock.Mock(),
        "drive_checker": mock.Mock(),
        "scanner": mock.Mock(),
        "glacier_restorer": mock.Mock(),
        "glacier_waiter": mock.Mock(),
        "migration_orchestrator": mock.Mock(),
        "bucket_migrator": mock.Mock(),
        "status_reporter": mock.Mock(),
    }
