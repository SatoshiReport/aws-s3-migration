"""Unit tests for S3MigrationV2 signal handling and interruption in migrate_v2.py.

Tests cover:
- Signal handler integration
- Interruption handling during migration
"""

import signal

import pytest

from migration_state_v2 import Phase


class TestSignalHandlerIntegration:
    """Integration tests for signal handler."""

    def test_signal_handler_propagates_to_all_components(self, migrator, mock_dependencies):
        """Signal handler properly propagates interrupted flag to all components."""
        # Initialize interrupted attributes
        mock_dependencies["scanner"].interrupted = False
        mock_dependencies["glacier_restorer"].interrupted = False
        mock_dependencies["glacier_waiter"].interrupted = False
        mock_dependencies["bucket_migrator"].interrupted = False
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


class TestInterruptionHandling:
    """Tests for interruption handling during migration."""

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
