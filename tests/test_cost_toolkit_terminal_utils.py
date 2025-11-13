"""Tests for cost_toolkit/common/terminal_utils.py"""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.common.terminal_utils import clear_screen


@patch("subprocess.run")
@patch("os.name", "posix")
def test_clear_screen_unix(mock_run):
    """Test clear_screen uses 'clear' command on Unix."""
    clear_screen()

    mock_run.assert_called_once_with(["clear"], check=False)


@patch("subprocess.run")
@patch("os.name", "nt")
def test_clear_screen_windows(mock_run):
    """Test clear_screen uses 'cls' command on Windows."""
    clear_screen()

    mock_run.assert_called_once_with(["cmd", "/c", "cls"], check=False)


@patch("builtins.print")
@patch("subprocess.run")
@patch("os.name", "posix")
def test_clear_screen_fallback_on_error(mock_run, mock_print):
    """Test clear_screen falls back to ANSI escape on FileNotFoundError."""
    mock_run.side_effect = FileNotFoundError("clear command not found")

    clear_screen()

    mock_print.assert_called_once_with("\033c", end="")
