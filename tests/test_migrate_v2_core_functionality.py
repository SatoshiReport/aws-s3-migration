"""Unit tests for S3MigrationV2 core functionality in migrate_v2.py.

Tests cover:
- S3MigrationV2 initialization
- Signal handler
- run() method for all phases
- Phase transitions and state management
"""

import signal

import pytest

from migrate_v2 import MigrationComponents, S3MigrationV2
from migration_state_v2 import Phase


class TestS3MigrationV2Initialization:
    """Tests for S3MigrationV2 initialization."""

    def _create_migrator(self, mock_dependencies):
        """Helper to build a migrator with shared dependency wiring."""
        components = MigrationComponents(
            drive_checker=mock_dependencies["drive_checker"],
            scanner=mock_dependencies["scanner"],
            glacier_restorer=mock_dependencies["glacier_restorer"],
            glacier_waiter=mock_dependencies["glacier_waiter"],
            migration_orchestrator=mock_dependencies["migration_orchestrator"],
            bucket_migrator=mock_dependencies["bucket_migrator"],
            status_reporter=mock_dependencies["status_reporter"],
        )
        return S3MigrationV2(mock_dependencies["state"], components)

    def test_dependencies_are_wired(self, mock_dependencies):
        """S3MigrationV2 stores the provided dependencies unchanged."""
        migrator = self._create_migrator(mock_dependencies)

        expected_mappings = {
            "state": "state",
            "drive_checker": "drive_checker",
            "scanner": "scanner",
            "glacier_restorer": "glacier_restorer",
            "glacier_waiter": "glacier_waiter",
            "bucket_migrator": "bucket_migrator",
            "migration_orchestrator": "migration_orchestrator",
            "status_reporter": "status_reporter",
        }

        for attr_name, dependency_key in expected_mappings.items():
            assert getattr(migrator, attr_name) == mock_dependencies[dependency_key]

    def test_initial_interrupted_flag_is_false(self, mock_dependencies):
        """S3MigrationV2 starts in a non-interrupted state."""
        migrator = self._create_migrator(mock_dependencies)
        assert migrator.interrupted is False


class TestS3MigrationV2SignalHandler:
    """Tests for signal handler functionality."""

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


class TestS3MigrationV2RunComplete:
    """Tests for run() when migration is already complete."""

    def test_run_already_complete(self, migrator, mock_dependencies, capsys):
        """run() shows completion message when already complete."""
        mock_dependencies["state"].get_current_phase.return_value = Phase.COMPLETE

        migrator.run()

        captured = capsys.readouterr()
        assert "Migration already complete!" in captured.out
        mock_dependencies["status_reporter"].show_status.assert_called_once()


class TestS3MigrationV2RunFromScanning:
    """Tests for run() from SCANNING phase."""

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


class TestS3MigrationV2RunFromGlacier:
    """Tests for run() from GLACIER phases."""

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


class TestS3MigrationV2RunFromSyncing:
    """Tests for run() from SYNCING phase."""

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


class TestS3MigrationV2RunHelpers:
    """Tests for run() helper methods and checks."""

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


class TestS3MigrationV2PhaseTransitions:
    """Tests for phase transitions."""

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
