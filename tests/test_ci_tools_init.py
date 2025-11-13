"""Tests for ci_tools/__init__.py shim module."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def test_exception_classes_exist():
    """Test that exception classes are defined."""
    shim_path = Path(__file__).parent.parent / "ci_tools" / "__init__.py"
    source = shim_path.read_text()

    assert "SharedPackageMissingError" in source
    assert "SharedDirectoryNotFoundError" in source
    assert "ImportSpecCreationError" in source


def test_shared_package_missing_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test SharedPackageMissingError when __init__.py is missing."""
    # Create ci_tools dir without __init__.py
    shared_root = tmp_path / "ci_shared"
    ci_tools_dir = shared_root / "ci_tools"
    ci_tools_dir.mkdir(parents=True)

    monkeypatch.setenv("CI_SHARED_ROOT", str(shared_root))

    # Clear any cached imports
    for name in list(sys.modules.keys()):
        if name.startswith("ci_tools"):
            del sys.modules[name]

    with pytest.raises(ImportError, match="Shared ci_tools package missing"):
        importlib.import_module("ci_tools")


def test_import_spec_creation_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test ImportSpecCreationError when spec creation fails."""
    shared_root = tmp_path / "ci_shared"
    ci_tools_dir = shared_root / "ci_tools"
    ci_tools_dir.mkdir(parents=True)

    # Create __init__.py file
    init_path = ci_tools_dir / "__init__.py"
    init_path.write_text("")

    monkeypatch.setenv("CI_SHARED_ROOT", str(shared_root))

    # Clear any cached imports
    for name in list(sys.modules.keys()):
        if name.startswith("ci_tools"):
            del sys.modules[name]

    # Mock spec_from_file_location to return None
    with patch("importlib.util.spec_from_file_location", return_value=None):
        with pytest.raises(ImportError, match="Unable to create import spec"):
            importlib.import_module("ci_tools")
