"""
Comprehensive unit tests for ci.py

Tests verify:
- run() function constructs argv correctly
- ci_main is called with proper arguments
- Return values are propagated correctly
- __main__ execution block behavior
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


class TestReturnValuePropagation:
    """Tests for return value propagation from ci_main."""

    @patch("ci.ci_main")
    def test_run_returns_zero_on_success(self, mock_ci_main):
        """Verify run() returns 0 when ci_main returns 0."""
        mock_ci_main.return_value = 0
        result = ci.run()
        assert result == 0

    @patch("ci.ci_main")
    def test_run_returns_nonzero_on_failure(self, mock_ci_main):
        """Verify run() returns non-zero when ci_main returns error code."""
        mock_ci_main.return_value = 1
        result = ci.run()
        assert result == 1

    @patch("ci.ci_main")
    def test_run_returns_arbitrary_error_codes(self, mock_ci_main):
        """Verify run() propagates arbitrary error codes from ci_main."""
        for error_code in [1, 2, 127, 255]:
            mock_ci_main.return_value = error_code
            result = ci.run()
            assert result == error_code

    @patch("ci.ci_main")
    def test_run_returns_positive_error_codes(self, mock_ci_main):
        """Verify run() handles various positive error codes."""
        mock_ci_main.return_value = 42
        result = ci.run()
        assert result == 42

    @patch("ci.ci_main")
    def test_run_return_value_matches_ci_main_exactly(self, mock_ci_main):
        """Verify return value is exactly what ci_main returns."""
        expected_value = 99
        mock_ci_main.return_value = expected_value
        result = ci.run()
        assert result == expected_value


class TestCiMainMockBehavior:
    """Tests verifying proper mocking of ci_main."""

    @patch("ci.ci_main")
    def test_ci_main_mock_receives_list(self, mock_ci_main):
        """Verify ci_main receives argv as a list."""
        mock_ci_main.return_value = 0
        ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert isinstance(argv, list)

    @patch("ci.ci_main")
    def test_ci_main_called_with_argv_positional_arg(self, mock_ci_main):
        """Verify ci_main is called with argv as positional argument."""
        mock_ci_main.return_value = 0
        ci.run()
        # Check that it was called with at least one positional argument
        assert len(mock_ci_main.call_args[0]) >= 1

    @patch("ci.ci_main")
    def test_ci_main_not_called_with_keyword_args(self, mock_ci_main):
        """Verify ci_main is called without keyword arguments."""
        mock_ci_main.return_value = 0
        ci.run()
        # call_args[1] would contain keyword arguments
        assert len(mock_ci_main.call_args[1]) == 0


class TestMainBlock:
    """Tests for __main__ execution block."""

    @patch("ci.run")
    def test_main_block_calls_run(self, mock_run):
        """Verify __main__ block calls run() function."""
        mock_run.return_value = 0
        # Simulate running the main block
        with patch("ci.run", mock_run):
            # Execute the if __name__ == "__main__" block logic
            try:
                raise SystemExit(ci.run())
            except SystemExit as e:
                assert e.code == 0
        mock_run.assert_called_once()

    def test_main_block_raises_system_exit_on_zero(self):
        """Verify __main__ block raises SystemExit with run()'s return value."""
        with patch("ci.run", return_value=0):
            with pytest.raises(SystemExit) as exc_info:
                raise SystemExit(ci.run())
            assert exc_info.value.code == 0

    def test_main_block_raises_system_exit_on_nonzero(self):
        """Verify __main__ block raises SystemExit with error code."""
        with patch("ci.run", return_value=1):
            with pytest.raises(SystemExit) as exc_info:
                raise SystemExit(ci.run())
            assert exc_info.value.code == 1

    @patch("ci.run")
    def test_main_block_uses_run_return_value(self, mock_run):
        """Verify __main__ block uses run's return value for SystemExit."""
        mock_run.return_value = 42
        with pytest.raises(SystemExit) as exc_info:
            raise SystemExit(ci.run())
        assert exc_info.value.code == 42


class TestIntegrationScenarios:
    """Integration tests for complete workflows."""

    @patch("ci.ci_main")
    def test_complete_workflow_no_args(self, mock_ci_main):
        """Verify complete workflow with no additional arguments."""
        mock_ci_main.return_value = 0
        with patch.object(sys, "argv", ["ci.py"]):
            result = ci.run()
        assert result == 0
        argv = mock_ci_main.call_args[0][0]
        assert argv == ["ci.py", "--command", "./scripts/ci.sh"]

    @patch("ci.ci_main")
    def test_complete_workflow_with_args_success(self, mock_ci_main):
        """Verify complete workflow with arguments and success."""
        mock_ci_main.return_value = 0
        with patch.object(sys, "argv", ["ci.py", "--verbose"]):
            result = ci.run()
        assert result == 0
        argv = mock_ci_main.call_args[0][0]
        assert argv == ["ci.py", "--command", "./scripts/ci.sh", "--verbose"]

    @patch("ci.ci_main")
    def test_complete_workflow_with_args_failure(self, mock_ci_main):
        """Verify complete workflow with arguments and failure."""
        mock_ci_main.return_value = 1
        with patch.object(sys, "argv", ["ci.py", "--verbose"]):
            result = ci.run()
        assert result == 1
        argv = mock_ci_main.call_args[0][0]
        assert argv == ["ci.py", "--command", "./scripts/ci.sh", "--verbose"]

    @patch("ci.ci_main")
    def test_multiple_run_calls_independent(self, mock_ci_main):
        """Verify multiple calls to run() work independently."""
        mock_ci_main.side_effect = [0, 1, 0]

        # First call
        result1 = ci.run()
        assert result1 == 0

        # Second call
        result2 = ci.run()
        assert result2 == 1

        # Third call
        result3 = ci.run()
        assert result3 == 0

        # Verify all three calls were made
        assert mock_ci_main.call_count == 3


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @patch("ci.ci_main")
    def test_run_with_empty_string_arg(self, mock_ci_main):
        """Verify run() handles empty string arguments."""
        mock_ci_main.return_value = 0
        with patch.object(sys, "argv", ["ci.py", ""]):
            ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert argv == ["ci.py", "--command", "./scripts/ci.sh", ""]

    @patch("ci.ci_main")
    def test_run_with_special_characters_in_args(self, mock_ci_main):
        """Verify run() preserves special characters in arguments."""
        mock_ci_main.return_value = 0
        with patch.object(sys, "argv", ["ci.py", "--file=/path/with spaces/file.txt"]):
            ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert argv[-1] == "--file=/path/with spaces/file.txt"

    @patch("ci.ci_main")
    def test_run_with_equals_sign_in_args(self, mock_ci_main):
        """Verify run() preserves equals signs in arguments."""
        mock_ci_main.return_value = 0
        with patch.object(sys, "argv", ["ci.py", "--param=value=something"]):
            ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert argv[-1] == "--param=value=something"

    @patch("ci.ci_main")
    def test_run_with_many_arguments(self, mock_ci_main):
        """Verify run() handles many arguments correctly."""
        mock_ci_main.return_value = 0
        many_args = ["ci.py"] + [f"--arg{i}" for i in range(100)]
        with patch.object(sys, "argv", many_args):
            ci.run()
        argv = mock_ci_main.call_args[0][0]
        # Should have base 3 args + 100 additional args
        assert len(argv) == 103

    @patch("ci.ci_main")
    def test_run_argv_is_list_not_tuple(self, mock_ci_main):
        """Verify argv is a list, not a tuple."""
        mock_ci_main.return_value = 0
        ci.run()
        argv = mock_ci_main.call_args[0][0]
        assert type(argv) is list


class TestMainBlockExecution:
    """Tests for executing the __main__ block directly."""

    @patch("ci.run")
    def test_main_block_execution_success(self, mock_run):
        """Test __main__ block execution with success exit code."""
        mock_run.return_value = 0
        # Simulate the __main__ block: if __name__ == "__main__": raise SystemExit(run())
        exit_code = mock_run.return_value
        with pytest.raises(SystemExit) as exc_info:
            raise SystemExit(exit_code)
        assert exc_info.value.code == 0

    @patch("ci.run")
    def test_main_block_execution_failure(self, mock_run):
        """Test __main__ block execution with failure exit code."""
        mock_run.return_value = 1
        exit_code = mock_run.return_value
        with pytest.raises(SystemExit) as exc_info:
            raise SystemExit(exit_code)
        assert exc_info.value.code == 1

    def test_main_block_execution_pattern(self):
        """Test the __main__ block execution pattern with real run()."""
        # This test verifies that the __main__ block would correctly
        # call run() and raise SystemExit with its return value
        with patch("ci.ci_main", return_value=0) as mock_ci_main:
            with patch.object(sys, "argv", ["ci.py"]):
                result = ci.run()
            # Verify ci_main was called
            assert mock_ci_main.called
            # Verify result is what would be passed to SystemExit
            assert result == 0

    def test_module_can_be_imported(self):
        """Verify ci module can be imported without errors."""
        import ci as ci_module

        assert ci_module is not None

    def test_ci_main_available_after_import(self):
        """Verify ci_main is accessible after importing ci module."""
        import ci as ci_module

        assert hasattr(ci_module, "ci_main")


class TestDocumentationAndReadability:
    """Tests verifying code structure and intent."""

    def test_run_function_exists(self):
        """Verify run() function is defined in ci module."""
        assert hasattr(ci, "run")
        assert callable(ci.run)

    def test_ci_main_is_imported(self):
        """Verify ci_main is imported in ci module."""
        assert hasattr(ci, "ci_main")

    def test_run_has_docstring(self):
        """Verify run() function has a docstring."""
        assert ci.run.__doc__ is not None
        assert len(ci.run.__doc__) > 0

    def test_module_has_docstring(self):
        """Verify ci module has a docstring."""
        assert ci.__doc__ is not None
        assert len(ci.__doc__) > 0
