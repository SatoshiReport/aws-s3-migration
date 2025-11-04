"""Unit tests for S3MigrationV2 reset and error handling in migrate_v2.py.

Tests cover:
- Reset confirmation handling (yes/no)
- Edge cases in phase execution
- Error handling
"""

from pathlib import Path
from unittest import mock

import pytest

from migrate_v2 import S3MigrationV2
from migration_state_v2 import Phase


class TestResetYesConfirmation:
    """Tests for reset() with yes confirmation."""

    def test_reset_with_yes_confirmation(self, monkeypatch, capsys):
        """reset() deletes state database when user confirms with 'yes'."""
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


class TestResetNoConfirmation:
    """Tests for reset() with no confirmation."""

    def test_reset_with_no_confirmation(self, capsys):
        """reset() cancels when user does not confirm."""
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
        assert "Reset cancelled" in captured.out


class TestResetDatabaseMissing:
    """Tests for reset() with missing database."""

    def test_reset_database_not_exists(self, capsys):
        """reset() handles missing database gracefully."""
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

        with mock.patch("builtins.input", return_value="yes"):
            with mock.patch("os.path.exists", return_value=False):
                migrator.reset()

        captured = capsys.readouterr()
        assert "No state database found" in captured.out


class TestResetCaseInsensitive:
    """Tests for reset() case insensitive confirmation."""

    def test_reset_case_insensitive_confirmation(self):
        """reset() handles uppercase confirmation (YES becomes yes via lower())."""
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

        with mock.patch("builtins.input", return_value="YES"):
            with mock.patch("os.path.exists", return_value=True):
                with mock.patch("os.remove") as mock_remove:
                    migrator.reset()
                    # Should delete because "YES".lower() == "yes"
                    mock_remove.assert_called_once()


class TestResetMessages:
    """Tests for reset() message output."""

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


class TestRunPhaseSkipping:
    """Tests for run() phase skipping."""

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


class TestRunPhaseTransitions:
    """Tests for run() phase transitions."""

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
