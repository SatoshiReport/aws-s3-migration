"""Tests for cleanup_temp_artifacts.py wrapper module."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


def test_cleanup_temp_artifacts_wrapper_imports_main():
    """Test that wrapper imports main from cleanup_temp_artifacts.cli."""
    # Import wrapper to ensure the import statement is covered
    with patch("cleanup_temp_artifacts.cli.main"):
        # Reload the module to cover the import
        wrapper_path = Path(__file__).parent.parent / "cleanup_temp_artifacts.py"
        spec = importlib.util.spec_from_file_location("_test_cleanup_wrapper", wrapper_path)
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Verify main was imported
        assert hasattr(module, "main")


def test_cleanup_temp_artifacts_cli_main_imported():
    """Test importing the wrapper module."""
    wrapper_path = Path(__file__).parent.parent / "cleanup_temp_artifacts.py"
    spec = importlib.util.spec_from_file_location("_test_cleanup_main_import", wrapper_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    # Module should have main function
    assert hasattr(module, "main")
    assert callable(module.main)
