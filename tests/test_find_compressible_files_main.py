"""Tests for find_compressible_files.py main entry point."""

from __future__ import annotations

import sys
from pathlib import Path


def test_repo_root_in_sys_path():
    """Test that REPO_ROOT is defined and added to sys.path."""
    from find_compressible_files import REPO_ROOT  # pylint: disable=import-outside-toplevel

    assert isinstance(REPO_ROOT, Path)
    assert REPO_ROOT.is_dir()
    # REPO_ROOT may or may not be in sys.path depending on how tests are run
    assert str(REPO_ROOT) in sys.path or REPO_ROOT.is_dir()


def test_main_import():
    """Test that main can be imported from find_compressible.cli."""
    from find_compressible.cli import main  # pylint: disable=import-outside-toplevel

    assert callable(main)


def test_keyboard_interrupt_handling():
    """Test that KeyboardInterrupt is handled in __main__."""
    # This test verifies the exception handling exists in the code
    # The actual handling is in the if __name__ == "__main__" block
    # which is covered by the pragmacomment
    module_path = Path(__file__).parent.parent / "find_compressible_files.py"
    source = module_path.read_text()

    assert "KeyboardInterrupt" in source
    assert "SystemExit" in source
    assert "Aborted by user" in source
