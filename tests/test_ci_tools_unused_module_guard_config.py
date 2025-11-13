"""Tests for config loading and overrides in ci_tools/scripts/unused_module_guard.py."""

# pylint: disable=missing-class-docstring,missing-function-docstring,too-few-public-methods,protected-access,import-outside-toplevel,unused-argument,redefined-outer-name,unused-import

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.assertions import assert_equal


def _load_shim_module(isolate=False):
    """
    Load the shim module directly from its source file.

    Args:
        isolate: If True, load in isolation without running bootstrap
    """
    import importlib.util
    import os
    import sys
    import tempfile

    shim_path = Path(__file__).parent.parent / "ci_tools" / "scripts" / "unused_module_guard.py"

    if isolate:
        # Load module with a temporary fake shared guard to allow bootstrap to succeed
        # This avoids needing exec() to partially load the module
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal fake shared guard structure
            shared_root = Path(tmpdir) / "ci_shared"
            scripts_dir = shared_root / "ci_tools" / "scripts"
            scripts_dir.mkdir(parents=True)

            # Write minimal guard module that bootstrap can load
            # Don't include main - let bootstrap fail and handle the error
            guard_file = scripts_dir / "unused_module_guard.py"
            guard_file.write_text(
                """
SUSPICIOUS_PATTERNS = ()

def find_unused_modules(root, exclude_patterns=None):
    return []

def find_suspicious_duplicates(root):
    return []
"""
            )

            # Load module with CI_SHARED_ROOT pointing to temp directory
            # Bootstrap will fail because guard.main doesn't exist, but that's OK
            with patch.dict(os.environ, {"CI_SHARED_ROOT": str(shared_root)}):
                spec = importlib.util.spec_from_file_location("_test_shim_isolated", shim_path)
                if spec is None or spec.loader is None:
                    raise ImportError(f"Cannot load {shim_path}")

                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module

                # Load module - bootstrap will fail with AttributeError (guard.main doesn't exist)
                # but the module functions will still be defined before the failure
                try:
                    spec.loader.exec_module(module)
                except AttributeError as e:
                    # Expected: bootstrap tries to access guard.main but it doesn't exist
                    # The module is partially loaded but that's OK for testing internal functions
                    if "main" not in str(e):
                        raise

                # Ensure _DELEGATED_MAIN is None (it should be since bootstrap failed)
                if not hasattr(module, "_DELEGATED_MAIN"):
                    module._DELEGATED_MAIN = None  # type: ignore[attr-defined]

                return module
    else:
        # Load normally (with bootstrap)
        import ci_tools.scripts.unused_module_guard as guard_module

        return guard_module


@pytest.fixture
def mock_shared_guard():
    """Create a mock shared guard module."""

    # Use a simple object instead of MagicMock to avoid attribute assignment issues
    class MockGuard:
        SUSPICIOUS_PATTERNS = ["test", "example", "_v2", "_backup"]

        def find_unused_modules(self, root, exclude_patterns=None):
            return []

        def find_suspicious_duplicates(self, root):
            return []

        def main(self):
            return 0

    return MockGuard()


def test_load_config_missing_file(tmp_path: Path):
    """Test _load_config returns empty lists when config file missing."""
    guard_module = _load_shim_module(isolate=True)
    guard_module._CONFIG_FILE = tmp_path  # type: ignore[attr-defined] / "nonexistent.json"

    excludes, allow_list, duplicate_excludes = guard_module._load_config()

    assert_equal(excludes, [])
    assert_equal(allow_list, [])
    assert_equal(duplicate_excludes, [])


def test_load_config_invalid_json(tmp_path: Path):
    """Test _load_config returns empty lists on JSON parse error."""
    config_file = tmp_path / "config.json"
    config_file.write_text("{ invalid json }")

    guard_module = _load_shim_module(isolate=True)
    guard_module._CONFIG_FILE = config_file  # type: ignore[attr-defined]

    excludes, allow_list, duplicate_excludes = guard_module._load_config()

    assert_equal(excludes, [])
    assert_equal(allow_list, [])
    assert_equal(duplicate_excludes, [])


def test_load_config_os_error(tmp_path: Path):
    """Test _load_config returns empty lists on OS error."""
    config_file = tmp_path / "config.json"

    guard_module = _load_shim_module(isolate=True)
    guard_module._CONFIG_FILE = config_file  # type: ignore[attr-defined]

    with patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
        excludes, allow_list, duplicate_excludes = guard_module._load_config()

    assert_equal(excludes, [])
    assert_equal(allow_list, [])
    assert_equal(duplicate_excludes, [])


def test_load_config_valid_file(tmp_path: Path):
    """Test _load_config successfully loads valid config."""
    config_file = tmp_path / "config.json"
    config_data = {
        "exclude_patterns": ["tests/", "build/"],
        "suspicious_allow_patterns": ["_v2", "_backup"],
        "duplicate_exclude_patterns": ["migrations/"],
    }
    config_file.write_text(json.dumps(config_data))

    guard_module = _load_shim_module(isolate=True)
    guard_module._CONFIG_FILE = config_file  # type: ignore[attr-defined]

    excludes, allow_list, duplicate_excludes = guard_module._load_config()

    assert_equal(excludes, ["tests/", "build/"])
    assert_equal(allow_list, ["_v2", "_backup"])
    assert_equal(duplicate_excludes, ["migrations/"])


def test_apply_config_overrides_no_overrides(mock_shared_guard):
    """Test _apply_config_overrides with no overrides."""
    guard_module = _load_shim_module(isolate=True)

    original_patterns = mock_shared_guard.SUSPICIOUS_PATTERNS
    guard_module._apply_config_overrides(mock_shared_guard, [], [], [])

    assert_equal(mock_shared_guard.SUSPICIOUS_PATTERNS, original_patterns)


def test_apply_config_overrides_allowed_patterns(mock_shared_guard):
    """Test _apply_config_overrides filters SUSPICIOUS_PATTERNS."""
    guard_module = _load_shim_module(isolate=True)

    guard_module._apply_config_overrides(mock_shared_guard, [], ["_v2", "_backup"], [])

    # Should remove _v2 and _backup from SUSPICIOUS_PATTERNS
    assert "_v2" not in mock_shared_guard.SUSPICIOUS_PATTERNS
    assert "_backup" not in mock_shared_guard.SUSPICIOUS_PATTERNS
    assert "test" in mock_shared_guard.SUSPICIOUS_PATTERNS
    assert "example" in mock_shared_guard.SUSPICIOUS_PATTERNS


def test_apply_config_overrides_extra_excludes(mock_shared_guard):
    """Test _apply_config_overrides wraps find_unused_modules."""
    guard_module = _load_shim_module(isolate=True)

    # Store original function
    original_func = mock_shared_guard.find_unused_modules

    guard_module._apply_config_overrides(mock_shared_guard, ["tests/", "build/"], [], [])

    # Call the wrapped function
    mock_shared_guard.find_unused_modules("/fake/root", exclude_patterns=["*.pyc"])

    # The function should have been wrapped, verify it's different
    assert mock_shared_guard.find_unused_modules != original_func


def test_apply_config_overrides_extra_excludes_no_existing(mock_shared_guard):
    """Test _apply_config_overrides with no existing exclude patterns."""
    guard_module = _load_shim_module(isolate=True)

    # Create a real function that we can test
    calls = []

    def mock_find_unused(root, exclude_patterns=None):
        calls.append({"root": root, "exclude_patterns": exclude_patterns})
        return []

    mock_shared_guard.find_unused_modules = mock_find_unused

    guard_module._apply_config_overrides(mock_shared_guard, ["tests/"], [], [])

    # Call the wrapped function
    mock_shared_guard.find_unused_modules("/fake/root")

    # Verify it was called with our patterns
    assert len(calls) == 1
    assert "tests/" in calls[0]["exclude_patterns"]


def test_apply_config_overrides_duplicate_excludes(mock_shared_guard):
    """Test _apply_config_overrides wraps find_suspicious_duplicates."""
    guard_module = _load_shim_module(isolate=True)

    # Create a real function
    def mock_find_duplicates(root):
        return [
            ("/path/to/migrations/file.py", "duplicate"),
            ("/path/to/normal/file.py", "duplicate"),
        ]

    mock_shared_guard.find_suspicious_duplicates = mock_find_duplicates

    guard_module._apply_config_overrides(mock_shared_guard, [], [], ["migrations/"])

    # Call the wrapped function
    results = mock_shared_guard.find_suspicious_duplicates("/fake/root")

    # Should filter out migrations
    assert_equal(len(results), 1)
    assert "/path/to/normal/file.py" in str(results[0])
    assert "migrations" not in str(results[0])


def test_apply_config_overrides_duplicate_excludes_combined(mock_shared_guard):
    """Test duplicate excludes combine with extra excludes."""
    guard_module = _load_shim_module(isolate=True)

    def mock_find_duplicates(root):
        return [
            ("/path/to/tests/file.py", "duplicate"),
            ("/path/to/migrations/file.py", "duplicate"),
            ("/path/to/normal/file.py", "duplicate"),
        ]

    mock_shared_guard.find_suspicious_duplicates = mock_find_duplicates

    guard_module._apply_config_overrides(mock_shared_guard, ["tests/"], [], ["migrations/"])

    results = mock_shared_guard.find_suspicious_duplicates("/fake/root")

    # Should filter out both tests and migrations
    assert_equal(len(results), 1)
    assert "/path/to/normal/file.py" in str(results[0])


def test_config_loading_with_empty_dict(tmp_path: Path):
    """Test _load_config handles empty dict."""
    config_file = tmp_path / "test_empty_config.json"
    config_file.write_text(json.dumps({}))

    guard_module = _load_shim_module(isolate=True)
    guard_module._CONFIG_FILE = config_file  # type: ignore[attr-defined]

    excludes, allow_list, duplicate_excludes = guard_module._load_config()

    assert_equal(excludes, [])
    assert_equal(allow_list, [])
    assert_equal(duplicate_excludes, [])
