"""
Comprehensive unit tests for ci.py - Part 1: Basic Functionality

Tests verify:
- run() function basic behavior
- argv construction
- Additional arguments passthrough
"""

import sys
from unittest.mock import patch

import pytest

# Import the module under test
import ci


class TestRunFunctionBasics:
    """Tests for the run() function basic behavior."""

    @patch("ci.ci_main")
    def test_run_returns_int(self, mock_ci_main):
        """Verify run() returns an integer."""
        mock_ci_main.return_value = 0
        result = ci.run()
        assert isinstance(result, int)

    @patch("ci.ci_main")
    def test_run_calls_ci_main(self, mock_ci_main):
        """Verify run() calls ci_main exactly once."""
        mock_ci_main.return_value = 0
        ci.run()
        mock_ci_main.assert_called_once()

    @patch("ci.ci_main")
    def test_run_calls_ci_main_once_only(self, mock_ci_main):
        """Verify run() calls ci_main only once, not multiple times."""
        mock_ci_main.return_value = 0
        ci.run()
        assert mock_ci_main.call_count == 1


class TestArgvConstruction:
    """Tests for argv construction in run()."""

    @patch("ci.ci_main")
    def test_argv_includes_ci_py_first_element(self, mock_ci_main):
        """Verify argv[0] is 'ci.py'."""
        mock_ci_main.return_value = 0
        ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert argv[0] == "ci.py"

    @patch("ci.ci_main")
    def test_argv_includes_command_flag(self, mock_ci_main):
        """Verify argv includes '--command' flag."""
        mock_ci_main.return_value = 0
        ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert "--command" in argv

    @patch("ci.ci_main")
    def test_argv_includes_ci_sh_script(self, mock_ci_main):
        """Verify argv includes './scripts/ci.sh' as command value."""
        mock_ci_main.return_value = 0
        ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert "./scripts/ci.sh" in argv

    @patch("ci.ci_main")
    def test_argv_structure_without_additional_args(self, mock_ci_main):
        """Verify argv structure when no additional arguments provided."""
        mock_ci_main.return_value = 0
        # Patch sys.argv to have no additional args
        with patch.object(sys, "argv", ["ci.py"]):
            ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert argv == ["ci.py", "--command", "./scripts/ci.sh"]

    @patch("ci.ci_main")
    def test_argv_command_follows_ci_py(self, mock_ci_main):
        """Verify --command appears right after 'ci.py'."""
        mock_ci_main.return_value = 0
        ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert argv[1] == "--command"

    @patch("ci.ci_main")
    def test_argv_script_follows_command_flag(self, mock_ci_main):
        """Verify ./scripts/ci.sh appears right after --command."""
        mock_ci_main.return_value = 0
        ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert argv[2] == "./scripts/ci.sh"


class TestAdditionalArgumentsPassthrough:
    """Tests for passing through additional command-line arguments."""

    @patch("ci.ci_main")
    def test_run_with_single_additional_arg(self, mock_ci_main):
        """Verify single additional argument is appended to argv."""
        mock_ci_main.return_value = 0
        with patch.object(sys, "argv", ["ci.py", "--verbose"]):
            ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert argv == ["ci.py", "--command", "./scripts/ci.sh", "--verbose"]

    @patch("ci.ci_main")
    def test_run_with_multiple_additional_args(self, mock_ci_main):
        """Verify multiple additional arguments are appended in order."""
        mock_ci_main.return_value = 0
        with patch.object(sys, "argv", ["ci.py", "--verbose", "--debug", "--output=file.txt"]):
            ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert argv == [
            "ci.py",
            "--command",
            "./scripts/ci.sh",
            "--verbose",
            "--debug",
            "--output=file.txt",
        ]

    @patch("ci.ci_main")
    def test_run_with_positional_args(self, mock_ci_main):
        """Verify positional arguments are passed through."""
        mock_ci_main.return_value = 0
        with patch.object(sys, "argv", ["ci.py", "build", "test"]):
            ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert argv == ["ci.py", "--command", "./scripts/ci.sh", "build", "test"]

    @patch("ci.ci_main")
    def test_run_with_mixed_args(self, mock_ci_main):
        """Verify mix of flags and positional arguments are passed through."""
        mock_ci_main.return_value = 0
        with patch.object(sys, "argv", ["ci.py", "--flag", "value", "--another-flag"]):
            ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert argv == [
            "ci.py",
            "--command",
            "./scripts/ci.sh",
            "--flag",
            "value",
            "--another-flag",
        ]

    @patch("ci.ci_main")
    def test_run_args_order_preserved(self, mock_ci_main):
        """Verify order of additional arguments is preserved."""
        mock_ci_main.return_value = 0
        with patch.object(sys, "argv", ["ci.py", "first", "second", "third"]):
            ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert argv[-3:] == ["first", "second", "third"]
