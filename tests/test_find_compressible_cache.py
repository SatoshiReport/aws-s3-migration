"""Tests for find_compressible/cache.py module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cost_toolkit.common.cli_utils import confirm_reset_state_db
from cost_toolkit.common.format_utils import format_bytes
from find_compressible.cache import (
    handle_state_db_reset,
)
from tests.assertions import assert_equal


def test_format_size_bytes():
    """Test format_size with bytes."""
    assert format_bytes(100, use_comma_separators=True) == "100.00 B"
    assert format_bytes(1023, use_comma_separators=True) == "1,023.00 B"


def test_format_size_kilobytes():
    """Test format_size with kilobytes."""
    assert format_bytes(1024, use_comma_separators=True) == "1.00 KiB"
    assert format_bytes(2048, use_comma_separators=True) == "2.00 KiB"


def test_format_size_megabytes():
    """Test format_size with megabytes."""
    assert format_bytes(1024 * 1024, use_comma_separators=True) == "1.00 MiB"
    assert format_bytes(500 * 1024 * 1024, use_comma_separators=True) == "500.00 MiB"


def test_format_size_gigabytes():
    """Test format_size with gigabytes."""
    assert format_bytes(1024 * 1024 * 1024, use_comma_separators=True) == "1.00 GiB"
    assert format_bytes(2 * 1024 * 1024 * 1024, use_comma_separators=True) == "2.00 GiB"


def test_format_size_terabytes():
    """Test format_size with terabytes."""
    assert format_bytes(1024 * 1024 * 1024 * 1024, use_comma_separators=True) == "1.00 TiB"
    assert format_bytes(5 * 1024 * 1024 * 1024 * 1024, use_comma_separators=True) == "5.00 TiB"


def test_format_size_petabytes():
    """Test format_size with petabytes."""
    result = format_bytes(1024 * 1024 * 1024 * 1024 * 1024, use_comma_separators=True)
    assert "PiB" in result


def test_confirm_state_db_reset_with_skip_prompt():
    """Test confirm_reset_state_db when skip_prompt is True."""
    db_path = Path("/tmp/test.db")
    result = confirm_reset_state_db(str(db_path), skip_prompt=True)
    assert result is True


def test_confirm_state_db_reset_with_user_confirmation():
    """Test confirm_reset_state_db with user confirmation."""
    db_path = Path("/tmp/test.db")
    with patch("builtins.input", return_value="y"):
        result = confirm_reset_state_db(str(db_path), skip_prompt=False)
        assert result is True


def test_confirm_state_db_reset_with_user_rejection():
    """Test confirm_reset_state_db with user rejection."""
    db_path = Path("/tmp/test.db")
    with patch("builtins.input", return_value="n"):
        result = confirm_reset_state_db(str(db_path), skip_prompt=False)
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

    with patch("builtins.input", return_value="n"):
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
        patch("builtins.input", return_value="y"),
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
