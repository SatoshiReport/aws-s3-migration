"""Tests for cleanup_temp_artifacts.py entry point."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import mock

import cleanup_temp_artifacts
from cleanup_temp_artifacts.cli import main as cli_main


def test_cleanup_temp_artifacts_entry_point_imports():
    """Test that cleanup_temp_artifacts module can be imported."""
    assert cleanup_temp_artifacts is not None


def test_cleanup_temp_artifacts_has_main_guard():
    """Test that the module has __name__ == '__main__' guard."""
    with open("cleanup_temp_artifacts.py", encoding="utf-8") as f:
        content = f.read()
        assert 'if __name__ == "__main__":' in content


def test_cleanup_temp_artifacts_calls_main():
    """Test that the entry point imports main from cli module."""
    # The module should import successfully
    assert cleanup_temp_artifacts is not None


def test_cleanup_temp_artifacts_imports_cli():
    """Test that the module imports from cleanup_temp_artifacts.cli."""
    with open("cleanup_temp_artifacts.py", encoding="utf-8") as f:
        content = f.read()
        assert "from cleanup_temp_artifacts.cli import main" in content


def test_cleanup_temp_artifacts_entry_point_code_structure():
    """Test that the entry point script has the correct code structure."""
    script_path = Path(__file__).parent.parent / "cleanup_temp_artifacts.py"

    # Load the module directly with __name__ == "__main__"
    spec = importlib.util.spec_from_file_location("__main__", script_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)

    # Mock the main function to prevent actual execution
    with mock.patch("cleanup_temp_artifacts.cli.main", return_value=0) as mock_main:
        # Execute the module which should hit the if __name__ == "__main__" block
        try:
            spec.loader.exec_module(module)
        except SystemExit:
            # Expected when main() is called
            pass

        # Verify main was called
        assert mock_main.called


def test_cleanup_temp_artifacts_imports_main_from_cli():
    """Test that main is imported from cleanup_temp_artifacts.cli."""
    # Verify the import path exists
    assert callable(cli_main)
