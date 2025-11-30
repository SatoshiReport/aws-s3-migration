"""Tests for cost_toolkit/common/terminal_utils.py"""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.common.terminal_utils import clear_screen


@patch("builtins.print")
def test_clear_screen_outputs_escape_sequence(mock_print):
    """Test clear_screen emits ANSI clear sequence."""
    clear_screen()

    mock_print.assert_called_once_with("\033[2J\033[H", end="", flush=True)
