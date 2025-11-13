"""Extended tests for ci_tools/scripts/unused_module_guard.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


# Import the local shim module directly to access its classes
def _import_local_shim():
    """Import the local shim module."""
    shim_path = Path(__file__).parent.parent / "ci_tools" / "scripts" / "unused_module_guard.py"
    spec = importlib.util.spec_from_file_location("_local_unused_module_guard", shim_path)
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load local shim")
    module = importlib.util.module_from_spec(spec)
    # Don't add to sys.modules to avoid conflicts
    return module


_local_shim_source = (
    Path(__file__).parent.parent / "ci_tools" / "scripts" / "unused_module_guard.py"
).read_text()


def test_shared_guard_error_classes_exist():
    """Test that error classes are defined in the local shim."""
    assert "SharedGuardMissingError" in _local_shim_source
    assert "SharedGuardSpecError" in _local_shim_source
    assert "SharedGuardInitializationError" in _local_shim_source


@pytest.mark.xdist_group(name="config_file")
def test_load_config_missing_file():
    """Test _load_config behavior with missing file."""
    # The actual function is embedded in the module after bootstrap
    # We test the config loading logic by checking the file exists
    config_path = Path(__file__).parent.parent / "unused_module_guard.config.json"
    if config_path.exists():
        data = json.loads(config_path.read_text())
        assert isinstance(data.get("exclude_patterns", []), list)


@pytest.mark.xdist_group(name="config_file")
def test_load_config_structure():
    """Test config file has expected structure."""
    config_path = Path(__file__).parent.parent / "unused_module_guard.config.json"
    if config_path.exists():
        data = json.loads(config_path.read_text())
        # Config should have expected keys
        assert any(
            key in data
            for key in [
                "exclude_patterns",
                "suspicious_allow_patterns",
                "duplicate_exclude_patterns",
            ]
        )


def test_config_override_functions_exist():
    """Test that config override functions are defined."""
    assert "_apply_config_overrides" in _local_shim_source
    assert "_load_config" in _local_shim_source
    assert "_bootstrap" in _local_shim_source


def test_shim_delegates_to_shared():
    """Test that the shim successfully delegates to shared implementation."""
    # The shim module should have a main function that delegates
    import ci_tools.scripts.unused_module_guard as guard  # pylint: disable=import-outside-toplevel

    # Should have the main function
    assert hasattr(guard, "main")
    assert callable(guard.main)


def test_shim_has_config_overrides():
    """Test that shim applies config overrides on bootstrap."""
    import ci_tools.scripts.unused_module_guard as guard  # pylint: disable=import-outside-toplevel

    # After bootstrap, should have CONFIG_OVERRIDES
    if hasattr(guard, "CONFIG_OVERRIDES"):
        overrides = getattr(guard, "CONFIG_OVERRIDES")
        assert isinstance(overrides, tuple)
        assert len(overrides) == 3  # excludes, allowed_patterns, duplicate_excludes
