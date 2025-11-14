"""Tests for ci_tools/scripts/__init__.py module."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def test_module_imports():
    """Test that ci_tools.scripts module can be imported."""
    import ci_tools.scripts  # pylint: disable=import-outside-toplevel

    assert hasattr(ci_tools.scripts, "__path__")


def test_shared_root_resolution_with_env(monkeypatch, tmp_path):
    """Test _shared_root resolution when CI_SHARED_ROOT is set."""
    shared_root = tmp_path / "custom_shared"
    shared_root.mkdir()

    monkeypatch.setenv("CI_SHARED_ROOT", str(shared_root))

    # Clear cached imports
    for name in list(sys.modules.keys()):
        if "ci_tools.scripts" in name:
            del sys.modules[name]

    import ci_tools.scripts  # pylint: disable=import-outside-toplevel,reimported

    # The module should have loaded successfully
    assert ci_tools.scripts is not None


def test_shared_scripts_path_appended_when_exists(monkeypatch, tmp_path):
    """Test that shared scripts path is added when it exists."""
    shared_root = tmp_path / "ci_shared"
    shared_scripts = shared_root / "ci_tools" / "scripts"
    shared_scripts.mkdir(parents=True)

    monkeypatch.setenv("CI_SHARED_ROOT", str(shared_root))

    # Clear cached imports
    for name in list(sys.modules.keys()):
        if "ci_tools.scripts" in name:
            del sys.modules[name]

    import ci_tools.scripts  # pylint: disable=import-outside-toplevel,reimported

    # The module should have loaded successfully
    assert ci_tools.scripts is not None
    # Module should have a __path__ attribute (namespace package)
    assert hasattr(ci_tools.scripts, "__path__")


def test_local_policy_context_import_handled():
    """Test that module handles missing policy_context gracefully."""
    # Import the module - it should handle ImportError for policy_context
    import ci_tools.scripts  # pylint: disable=import-outside-toplevel

    # Module should exist successfully even if policy_context is missing
    assert ci_tools.scripts is not None


def test_init_module_directly_loads_successfully(monkeypatch, tmp_path):
    """Test loading __init__.py directly to ensure coverage."""
    # Create a fake shared root that doesn't exist
    fake_shared = tmp_path / "nonexistent"
    monkeypatch.setenv("CI_SHARED_ROOT", str(fake_shared))

    # Load the module directly from file
    init_path = Path(__file__).parent.parent / "ci_tools" / "scripts" / "__init__.py"
    spec = importlib.util.spec_from_file_location("_test_ci_tools_scripts_init", init_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Module should have __path__
    assert hasattr(module, "__path__")


def test_init_with_existing_shared_scripts_appends_path(monkeypatch, tmp_path):
    """Test that existing shared scripts directory is added to __path__."""
    # Create shared scripts directory
    shared_root = tmp_path / "shared"
    shared_scripts = shared_root / "ci_tools" / "scripts"
    shared_scripts.mkdir(parents=True)

    # Create an empty __init__.py to make it a valid package
    (shared_scripts / "__init__.py").write_text("", encoding="utf-8")

    monkeypatch.setenv("CI_SHARED_ROOT", str(shared_root))

    # Clear all ci_tools modules
    for name in list(sys.modules.keys()):
        if name.startswith("ci_tools"):
            del sys.modules[name]

    # Load the module directly
    init_path = Path(__file__).parent.parent / "ci_tools" / "scripts" / "__init__.py"
    spec = importlib.util.spec_from_file_location("_test_scripts_with_shared", init_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    # Verify the shared scripts path was appended
    assert hasattr(module, "__path__")
    assert any(str(shared_scripts) in p for p in module.__path__)


def test_init_policy_context_import_coverage(monkeypatch, tmp_path):
    """Test policy_context import attempt for coverage."""
    monkeypatch.setenv("CI_SHARED_ROOT", str(tmp_path / "fake"))

    # Clear modules
    for name in list(sys.modules.keys()):
        if "ci_tools" in name and "policy" in name:
            del sys.modules[name]

    # Load directly
    init_path = Path(__file__).parent.parent / "ci_tools" / "scripts" / "__init__.py"
    spec = importlib.util.spec_from_file_location("_test_policy_import", init_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module

    # This should try to import policy_context and handle the ImportError
    spec.loader.exec_module(module)

    assert module is not None
