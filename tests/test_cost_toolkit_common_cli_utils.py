"""Tests for cost_toolkit/common/cli_utils.py module."""

from __future__ import annotations

import argparse
from unittest.mock import patch

from cost_toolkit.common.cli_utils import add_reset_state_db_args, confirm_reset_state_db
from tests.assertions import assert_equal


def test_add_reset_state_db_args():
    """Test add_reset_state_db_args adds expected arguments."""
    parser = argparse.ArgumentParser()

    result = add_reset_state_db_args(parser)

    # Should return the same parser
    assert result is parser

    # Parse args to verify the arguments were added
    args = parser.parse_args(["--reset-state-db", "--yes"])
    assert args.reset_state_db is True
    assert args.yes is True


def test_add_reset_state_db_args_defaults():
    """Test default values when arguments not provided."""
    parser = argparse.ArgumentParser()
    add_reset_state_db_args(parser)

    args = parser.parse_args([])
    assert args.reset_state_db is False
    assert args.yes is False


def test_confirm_reset_state_db_skip_prompt():
    """Test confirm_reset_state_db when skip_prompt is True."""
    result = confirm_reset_state_db("/tmp/test.db", skip_prompt=True)
    assert_equal(result, True)


def test_confirm_reset_state_db_yes():
    """Test confirm_reset_state_db with 'y' response."""
    with patch("builtins.input", return_value="y"):
        result = confirm_reset_state_db("/tmp/test.db", skip_prompt=False)
        assert_equal(result, True)

    with patch("builtins.input", return_value="yes"):
        result = confirm_reset_state_db("/tmp/test.db", skip_prompt=False)
        assert_equal(result, True)

    with patch("builtins.input", return_value="YES"):
        result = confirm_reset_state_db("/tmp/test.db", skip_prompt=False)
        assert_equal(result, True)

    with patch("builtins.input", return_value="  Y  "):
        result = confirm_reset_state_db("/tmp/test.db", skip_prompt=False)
        assert_equal(result, True)


def test_confirm_reset_state_db_no():
    """Test confirm_reset_state_db with 'n' or empty response."""
    with patch("builtins.input", return_value="n"):
        result = confirm_reset_state_db("/tmp/test.db", skip_prompt=False)
        assert_equal(result, False)

    with patch("builtins.input", return_value=""):
        result = confirm_reset_state_db("/tmp/test.db", skip_prompt=False)
        assert_equal(result, False)

    with patch("builtins.input", return_value="no"):
        result = confirm_reset_state_db("/tmp/test.db", skip_prompt=False)
        assert_equal(result, False)

    with patch("builtins.input", return_value="maybe"):
        result = confirm_reset_state_db("/tmp/test.db", skip_prompt=False)
        assert_equal(result, False)
