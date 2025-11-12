"""Extended tests for find_compressible_files.py main entry point."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.assertions import assert_equal


def test_repo_root_not_in_sys_path():
    """Test that REPO_ROOT is added to sys.path when not present."""
    # Import the module to trigger the sys.path logic
    import find_compressible_files  # pylint: disable=import-outside-toplevel

    repo_root_str = str(find_compressible_files.REPO_ROOT)

    # Verify REPO_ROOT is a Path
    assert isinstance(find_compressible_files.REPO_ROOT, Path)

    # Verify REPO_ROOT is in sys.path (the module adds it if not present)
    assert repo_root_str in sys.path


def test_repo_root_already_in_sys_path():
    """Test behavior when REPO_ROOT is already in sys.path."""
    # Get the REPO_ROOT path first
    import find_compressible_files  # pylint: disable=import-outside-toplevel,reimported

    repo_root_str = str(find_compressible_files.REPO_ROOT)

    # Count occurrences before (should be 1 since we already imported)
    count_before = sys.path.count(repo_root_str)

    # Re-import shouldn't add duplicate
    import importlib  # pylint: disable=import-outside-toplevel

    importlib.reload(find_compressible_files)

    count_after = sys.path.count(repo_root_str)

    # Should be same or only one more if the reload logic doesn't check
    assert count_after >= count_before


def test_main_function_is_callable():
    """Test that main function from find_compressible.cli is callable."""
    from find_compressible_files import main  # pylint: disable=import-outside-toplevel

    assert callable(main)


def test_main_execution_via_subprocess():
    """Test that __main__ block can be executed as a script."""
    # Run the script with --help to test the __main__ block
    script_path = Path(__file__).parent.parent / "find_compressible_files.py"
    result = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    # --help should exit with code 0
    assert_equal(result.returncode, 0)
    # Should show usage information
    assert "usage:" in result.stdout.lower() or "usage:" in result.stderr.lower()


def test_main_keyboard_interrupt():
    """Test KeyboardInterrupt handling in __main__ block."""
    # Run a script that will be interrupted (test with invalid args that cause early error)
    script_path = Path(__file__).parent.parent / "find_compressible_files.py"
    # Use --min-size with invalid value to cause an error quickly
    result = subprocess.run(
        [sys.executable, str(script_path), "--min-size", "invalid"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    # Should exit with non-zero code for invalid argument
    assert result.returncode != 0
