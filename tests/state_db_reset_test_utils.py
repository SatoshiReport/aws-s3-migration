"""Shared helpers for state DB reset tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


def build_reset_context(tmp_path=None):
    """Return (base_path, db_path, reseed_function) for handle_state_db_reset tests."""
    if tmp_path is None:
        base_path = Path("/tmp/base")
        db_path = Path("/tmp/test.db")
    else:
        base_path = tmp_path / "base"
        base_path.mkdir(exist_ok=True)
        db_path = tmp_path / "test.db"

    def mock_reseed(_bp, dp):
        return dp, 100, 1000

    return base_path, db_path, mock_reseed


def build_magic_reseed(db_path):
    """Return a MagicMock reseed function returning deterministic values."""
    return MagicMock(return_value=(db_path, 1000, 1024 * 1024 * 1024))
