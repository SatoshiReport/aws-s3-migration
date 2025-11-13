"""Tests for ci.py module."""

from __future__ import annotations

from unittest.mock import patch

from tests.assertions import assert_equal


def test_run_function():
    """Test run() function calls ci_main with correct arguments."""
    with patch("ci.ci_main", return_value=42) as mock_ci_main:
        from ci import run  # pylint: disable=import-outside-toplevel

        result = run()

        assert_equal(result, 42)
        # Verify ci_main was called with correct arguments
        call_args = mock_ci_main.call_args[0][0]
        assert call_args[0] == "ci.py"
        assert call_args[1] == "--command"
        assert call_args[2] == "./scripts/ci.sh"
