"""Unit tests for S3MigrationV2 core functionality in migrate_v2.py.

Tests cover:
- S3MigrationV2 initialization
- Signal handler
- run() method for all phases
- Phase transitions and state management
- Reset confirmation handling (yes/no)
- Error handling
"""

import signal
from pathlib import Path
from unittest import mock

import pytest

from migrate_v2 import S3MigrationV2
from migration_state_v2 import Phase


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


class TestSignalHandlerIntegration:
    """Integration tests for signal handler."""

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
