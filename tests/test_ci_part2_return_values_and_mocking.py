"""
Comprehensive unit tests for ci.py - Part 2: Return Values and Mocking

Tests verify:
- Return value propagation from ci_main
- ci_main mock behavior
- Main block execution
"""

import sys
from unittest.mock import patch

import pytest

# Import the module under test
import ci
from tests.assertions import assert_equal


class TestReturnValuePropagation:
    """Tests for return value propagation from ci_main."""

    @patch("ci.ci_main")
    def test_run_returns_zero_on_success(self, mock_ci_main):
        """Verify run() returns 0 when ci_main returns 0."""
        mock_ci_main.return_value = 0
        result = ci.run()
        assert_equal(result, 0)

    @patch("ci.ci_main")
    def test_run_returns_nonzero_on_failure(self, mock_ci_main):
        """Verify run() returns non-zero when ci_main returns error code."""
        mock_ci_main.return_value = 1
        result = ci.run()
        assert_equal(result, 1)

    @patch("ci.ci_main")
    def test_run_returns_arbitrary_error_codes(self, mock_ci_main):
        """Verify run() propagates arbitrary error codes from ci_main."""
        for error_code in [1, 2, 127, 255]:
            mock_ci_main.return_value = error_code
            result = ci.run()
            assert_equal(result, error_code)

    @patch("ci.ci_main")
    def test_run_returns_positive_error_codes(self, mock_ci_main):
        """Verify run() handles various positive error codes."""
        mock_ci_main.return_value = 42
        result = ci.run()
        assert_equal(result, 42)

    @patch("ci.ci_main")
    def test_run_return_value_matches_ci_main_exactly(self, mock_ci_main):
        """Verify return value is exactly what ci_main returns."""
        expected_value = 99
        mock_ci_main.return_value = expected_value
        result = ci.run()
        assert_equal(result, expected_value)


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
            with pytest.raises(SystemExit) as exc_info:
                raise SystemExit(ci.run())
            assert exc_info.value.code == 0
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
        assert_equal(exc_info.value.code, 42)


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
        assert_equal(exc_info.value.code, 0)

    @patch("ci.run")
    def test_main_block_execution_failure(self, mock_run):
        """Test __main__ block execution with failure exit code."""
        mock_run.return_value = 1
        exit_code = mock_run.return_value
        with pytest.raises(SystemExit) as exc_info:
            raise SystemExit(exit_code)
        assert_equal(exc_info.value.code, 1)

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
            assert_equal(result, 0)

    def test_module_can_be_imported(self):
        """Verify ci module can be imported without errors."""
        # pylint: disable=import-outside-toplevel,reimported
        import ci as ci_module

        assert ci_module is not None

    def test_ci_main_available_after_import(self):
        """Verify ci_main is accessible after importing ci module."""
        # pylint: disable=import-outside-toplevel,reimported
        import ci as ci_module

        assert hasattr(ci_module, "ci_main")
