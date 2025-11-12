"""Tests for find_compressible/cache.py module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from find_compressible.cache import (
    _confirm_state_db_reset,
    format_size,
    handle_state_db_reset,
)
from tests.assertions import assert_equal


def test_format_size_bytes():
    """Test format_size with bytes."""
    assert format_size(100) == "100.00 B"
    assert format_size(1023) == "1,023.00 B"


def test_format_size_kilobytes():
    """Test format_size with kilobytes."""
    assert format_size(1024) == "1.00 KiB"
    assert format_size(2048) == "2.00 KiB"


def test_format_size_megabytes():
    """Test format_size with megabytes."""
    assert format_size(1024 * 1024) == "1.00 MiB"
    assert format_size(500 * 1024 * 1024) == "500.00 MiB"


def test_format_size_gigabytes():
    """Test format_size with gigabytes."""
    assert format_size(1024 * 1024 * 1024) == "1.00 GiB"
    assert format_size(2 * 1024 * 1024 * 1024) == "2.00 GiB"


def test_format_size_terabytes():
    """Test format_size with terabytes."""
    assert format_size(1024 * 1024 * 1024 * 1024) == "1.00 TiB"
    assert format_size(5 * 1024 * 1024 * 1024 * 1024) == "5.00 TiB"


def test_format_size_petabytes():
    """Test format_size with petabytes."""
    # Note: format_size stops at TiB and shows larger values in TiB
    result = format_size(1024 * 1024 * 1024 * 1024 * 1024)
    assert "TiB" in result


def test_confirm_state_db_reset_with_skip_prompt():
    """Test _confirm_state_db_reset when skip_prompt is True."""
    db_path = Path("/tmp/test.db")
    result = _confirm_state_db_reset(db_path, skip_prompt=True)
    assert result is True


def test_confirm_state_db_reset_with_user_confirmation():
    """Test _confirm_state_db_reset with user confirmation."""
    db_path = Path("/tmp/test.db")
    with patch("find_compressible.cache.confirm_reset_state_db", return_value=True):
        result = _confirm_state_db_reset(db_path, skip_prompt=False)
        assert result is True


def test_confirm_state_db_reset_with_user_rejection():
    """Test _confirm_state_db_reset with user rejection."""
    db_path = Path("/tmp/test.db")
    with patch("find_compressible.cache.confirm_reset_state_db", return_value=False):
        result = _confirm_state_db_reset(db_path, skip_prompt=False)
        assert result is False


def test_handle_state_db_reset_no_reset():
    """Test handle_state_db_reset when should_reset is False."""
    db_path = Path("/tmp/test.db")
    base_path = Path("/tmp/base")
    result = handle_state_db_reset(base_path, db_path, should_reset=False, skip_prompt=False)
    assert_equal(result, db_path)


def test_handle_state_db_reset_cancelled(tmp_path, capsys):
    """Test handle_state_db_reset when user cancels."""
    db_path = tmp_path / "test.db"
    base_path = tmp_path / "base"
    base_path.mkdir()

    with patch("find_compressible.cache._confirm_state_db_reset", return_value=False):
        result = handle_state_db_reset(base_path, db_path, should_reset=True, skip_prompt=False)
        assert_equal(result, db_path)
        captured = capsys.readouterr().out
        assert "cancelled" in captured


def test_handle_state_db_reset_confirmed(tmp_path, capsys):
    """Test handle_state_db_reset when user confirms."""
    db_path = tmp_path / "test.db"
    base_path = tmp_path / "base"
    base_path.mkdir()

    mock_reseed = MagicMock(return_value=(db_path, 1000, 1024 * 1024 * 1024))

    with (
        patch("find_compressible.cache._confirm_state_db_reset", return_value=True),
        patch("find_compressible.cache.reseed_state_db_from_local_drive", mock_reseed),
    ):
        result = handle_state_db_reset(base_path, db_path, should_reset=True, skip_prompt=False)
        assert_equal(result, db_path)
        captured = capsys.readouterr().out
        assert "Recreated" in captured
        assert "1,000 files" in captured


def test_handle_state_db_reset_with_skip_prompt(tmp_path, capsys):
    """Test handle_state_db_reset with skip_prompt=True."""
    db_path = tmp_path / "test.db"
    base_path = tmp_path / "base"
    base_path.mkdir()

    mock_reseed = MagicMock(return_value=(db_path, 500, 512 * 1024 * 1024))

    with patch("find_compressible.cache.reseed_state_db_from_local_drive", mock_reseed):
        result = handle_state_db_reset(base_path, db_path, should_reset=True, skip_prompt=True)
        assert_equal(result, db_path)
        captured = capsys.readouterr().out
        assert "Recreated" in captured
