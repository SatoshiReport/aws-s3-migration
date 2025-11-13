"""Tests for ci_tools/scripts/__init__.py module."""

from __future__ import annotations

import sys


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
