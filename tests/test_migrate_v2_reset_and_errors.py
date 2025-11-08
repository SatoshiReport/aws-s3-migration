"""Unit tests for S3MigrationV2 reset behavior and error handling."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

import migrate_v2
from migration_state_v2 import Phase


def _override_state_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, create: bool) -> Path:
    """Point migrate_v2.STATE_DB_PATH at a temp file for reset tests."""
    state_db = tmp_path / "state.db"
    monkeypatch.setattr(migrate_v2, "STATE_DB_PATH", str(state_db), raising=False)
    if create:
        state_db.touch()
    return state_db


class TestResetFlow:
    """Reset command confirmation flows."""

    def test_reset_with_yes_confirmation(self, monkeypatch, capsys, tmp_path, migrator):
        """Test reset with 'yes' confirmation."""
        state_db = _override_state_db(tmp_path, monkeypatch, create=True)

        with mock.patch("builtins.input", return_value="yes"):
            migrator.reset()

        assert state_db.exists()
        captured = capsys.readouterr()
        assert "RESET MIGRATION" in captured.out

    def test_reset_with_no_confirmation(self, monkeypatch, capsys, tmp_path, migrator):
        """Test reset with 'no' confirmation."""
        state_db = _override_state_db(tmp_path, monkeypatch, create=True)

        with mock.patch("builtins.input", return_value="no"):
            migrator.reset()

        assert state_db.exists()
        captured = capsys.readouterr()
        assert "Reset cancelled" in captured.out

    def test_reset_when_database_missing(self, monkeypatch, capsys, tmp_path, migrator):
        """Test reset when database doesn't exist."""
        _override_state_db(tmp_path, monkeypatch, create=False)

        with mock.patch("builtins.input", return_value="yes"):
            migrator.reset()

        captured = capsys.readouterr()
        assert "Created fresh state database" in captured.out

    def test_reset_case_insensitive_confirmation(self, monkeypatch, tmp_path, migrator):
        """Test reset accepts case-insensitive 'YES'."""
        state_db = _override_state_db(tmp_path, monkeypatch, create=True)

        with mock.patch("builtins.input", return_value="YES"):
            migrator.reset()

        assert state_db.exists()

    def test_reset_prints_header_message(self, monkeypatch, capsys, tmp_path, migrator):
        """Test reset prints header message."""
        _override_state_db(tmp_path, monkeypatch, create=False)

        with mock.patch("builtins.input", return_value="no"):
            migrator.reset()

        captured = capsys.readouterr()
        assert "RESET MIGRATION" in captured.out
        assert "delete all migration state" in captured.out


class TestRunPhaseSkipping:
    """Ensure run() skips irrelevant phases."""

    def __repr__(self):
        return f"{self.__class__.__name__}()"

    def test_run_skips_scanner_in_middle_phases(self, migrator, mock_dependencies):
        mock_state = mock_dependencies["state"]
        mock_state.get_current_phase.side_effect = [Phase.GLACIER_RESTORE, Phase.COMPLETE]

        migrator.run()

        mock_dependencies["scanner"].scan_all_buckets.assert_not_called()
        mock_dependencies["glacier_restorer"].request_all_restores.assert_called_once()


class TestRunPhaseTransitions:
    """Validate run() transitions through expected phases."""

    def __repr__(self):
        return f"{self.__class__.__name__}()"

    def test_run_completes_all_phase_transitions(self, migrator, mock_dependencies):
        mock_state = mock_dependencies["state"]
        mock_state.get_current_phase.side_effect = [
            Phase.SCANNING,
            Phase.GLACIER_RESTORE,
            Phase.GLACIER_WAIT,
            Phase.SYNCING,
            Phase.COMPLETE,
        ]

        migrator.run()

        assert mock_dependencies["scanner"].scan_all_buckets.called
        assert mock_dependencies["glacier_restorer"].request_all_restores.called
        assert mock_dependencies["glacier_waiter"].wait_for_restores.called
        assert mock_dependencies["migration_orchestrator"].migrate_all_buckets.called


class TestS3MigrationV2ErrorHandling:
    """Drive checker and other failure scenarios."""

    def __repr__(self):
        return f"{self.__class__.__name__}()"

    def test_run_with_drive_check_failure(self, migrator, mock_dependencies):
        mock_dependencies["drive_checker"].check_available.side_effect = SystemExit(1)

        with pytest.raises(SystemExit):
            migrator.run()
