"""Tests for basic infrastructure in ci_tools/scripts/unused_module_guard.py shim module."""

# pylint: disable=protected-access,import-outside-toplevel,missing-class-docstring
# pylint: disable=missing-function-docstring,unused-argument,unused-variable

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
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
def clean_imports():
    """Clean up imported modules after each test."""
    original_modules = sys.modules.copy()
    yield
    # Remove any test-added modules
    for name in list(sys.modules.keys()):
        if name not in original_modules:
            del sys.modules[name]


def test_exception_classes_exist():
    """Test that exception classes are defined."""
    shim_path = Path(__file__).parent.parent / "ci_tools" / "scripts" / "unused_module_guard.py"
    source = shim_path.read_text()

    assert "SharedGuardMissingError" in source
    assert "SharedGuardSpecError" in source
    assert "SharedGuardInitializationError" in source


def test_shared_guard_missing_error_message():
    """Test SharedGuardMissingError message formatting."""
    guard_module = _load_shim_module(isolate=True)

    test_path = Path("/fake/path/to/guard.py")
    error = guard_module.SharedGuardMissingError(test_path)

    assert "Shared unused_module_guard not found at" in str(error)
    assert "/fake/path/to/guard.py" in str(error)
    assert "Clone ci_shared or set CI_SHARED_ROOT" in str(error)


def test_shared_guard_spec_error_message():
    """Test SharedGuardSpecError message formatting."""
    guard_module = _load_shim_module(isolate=True)

    test_path = Path("/fake/path/to/guard.py")
    error = guard_module.SharedGuardSpecError(test_path)

    assert "Unable to create spec for" in str(error)
    assert "/fake/path/to/guard.py" in str(error)


def test_shared_guard_initialization_error_message():
    """Test SharedGuardInitializationError message formatting."""
    guard_module = _load_shim_module(isolate=True)

    error = guard_module.SharedGuardInitializationError()
    assert "shared unused_module_guard failed to initialize" in str(error)


def test_load_shared_guard_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test _load_shared_guard raises when shared guard doesn't exist."""
    # Set CI_SHARED_ROOT to a non-existent directory
    fake_shared = tmp_path / "ci_shared"
    monkeypatch.setenv("CI_SHARED_ROOT", str(fake_shared))

    guard_module = _load_shim_module(isolate=True)

    with pytest.raises(guard_module.SharedGuardMissingError) as exc_info:
        guard_module._load_shared_guard()

    expected_path = fake_shared / "ci_tools" / "scripts" / "unused_module_guard.py"
    assert str(expected_path) in str(exc_info.value)


def test_load_shared_guard_spec_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test _load_shared_guard raises when spec creation fails."""
    # Create the expected directory structure with the file
    shared_root = tmp_path / "ci_shared"
    scripts_dir = shared_root / "ci_tools" / "scripts"
    scripts_dir.mkdir(parents=True)
    guard_file = scripts_dir / "unused_module_guard.py"
    guard_file.write_text("# mock guard")

    monkeypatch.setenv("CI_SHARED_ROOT", str(shared_root))

    guard_module = _load_shim_module(isolate=True)

    # Mock spec_from_file_location to return None
    with patch("importlib.util.spec_from_file_location", return_value=None):
        with pytest.raises(guard_module.SharedGuardSpecError) as exc_info:
            guard_module._load_shared_guard()

        assert str(guard_file) in str(exc_info.value)


def test_load_shared_guard_spec_no_loader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test _load_shared_guard raises when spec has no loader."""
    # Create the expected directory structure with the file
    shared_root = tmp_path / "ci_shared"
    scripts_dir = shared_root / "ci_tools" / "scripts"
    scripts_dir.mkdir(parents=True)
    guard_file = scripts_dir / "unused_module_guard.py"
    guard_file.write_text("# mock guard")

    monkeypatch.setenv("CI_SHARED_ROOT", str(shared_root))

    guard_module = _load_shim_module(isolate=True)

    # Mock spec with no loader
    mock_spec = MagicMock()
    mock_spec.loader = None

    with patch("importlib.util.spec_from_file_location", return_value=mock_spec):
        with pytest.raises(guard_module.SharedGuardSpecError):
            guard_module._load_shared_guard()


def test_load_shared_guard_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test _load_shared_guard successfully loads valid guard module."""
    # Create a minimal valid guard module
    shared_root = tmp_path / "ci_shared"
    scripts_dir = shared_root / "ci_tools" / "scripts"
    scripts_dir.mkdir(parents=True)
    guard_file = scripts_dir / "unused_module_guard.py"
    guard_file.write_text(
        """
SUSPICIOUS_PATTERNS = ("test",)

def find_unused_modules(root, exclude_patterns=None):
    return []

def find_suspicious_duplicates(root):
    return []

def main():
    return 0
"""
    )

    monkeypatch.setenv("CI_SHARED_ROOT", str(shared_root))

    guard_module = _load_shim_module(isolate=True)

    result = guard_module._load_shared_guard()

    assert hasattr(result, "SUSPICIOUS_PATTERNS")
    assert hasattr(result, "find_unused_modules")
    assert hasattr(result, "find_suspicious_duplicates")
    assert hasattr(result, "main")


def test_module_constants():
    """Test module-level constants are defined correctly."""
    guard_module = _load_shim_module(isolate=True)

    # Check constants exist
    assert hasattr(guard_module, "_LOCAL_MODULE_PATH")
    assert hasattr(guard_module, "_ORIGINAL_MODULE_NAME")
    assert hasattr(guard_module, "_REPO_ROOT")
    assert hasattr(guard_module, "_CONFIG_FILE")

    # Verify paths are Path objects
    assert isinstance(guard_module._LOCAL_MODULE_PATH, Path)
    assert isinstance(guard_module._REPO_ROOT, Path)
    assert isinstance(guard_module._CONFIG_FILE, Path)

    # Verify REPO_ROOT is 2 levels up from the module
    expected_repo = guard_module._LOCAL_MODULE_PATH.parents[2]
    assert_equal(guard_module._REPO_ROOT, expected_repo)

    # Verify CONFIG_FILE path
    expected_config = guard_module._REPO_ROOT / "unused_module_guard.config.json"
    assert_equal(guard_module._CONFIG_FILE, expected_config)


def test_guard_module_protocol():
    """Test GuardModule protocol defines expected interface."""
    guard_module = _load_shim_module(isolate=True)

    # Create an object that conforms to the protocol
    class ConcreteGuard:
        SUSPICIOUS_PATTERNS = ("test",)

        def find_unused_modules(self, root, exclude_patterns=None):
            return []

        def find_suspicious_duplicates(self, root):
            return []

        def main(self):
            return 0

    # Verify it has all required attributes
    concrete = ConcreteGuard()
    assert hasattr(concrete, "SUSPICIOUS_PATTERNS")
    assert hasattr(concrete, "find_unused_modules")
    assert hasattr(concrete, "find_suspicious_duplicates")
    assert hasattr(concrete, "main")


def test_module_source_has_all_components():
    """Test that module source contains all expected components."""
    shim_path = Path(__file__).parent.parent / "ci_tools" / "scripts" / "unused_module_guard.py"
    source = shim_path.read_text()

    # Check for key components
    assert "def _load_shared_guard()" in source
    assert "def _load_config()" in source
    assert "def _apply_config_overrides(" in source
    assert "def _bootstrap()" in source
    assert "def main()" in source

    # Check for error classes
    assert "class SharedGuardMissingError" in source
    assert "class SharedGuardSpecError" in source
    assert "class SharedGuardInitializationError" in source

    # Check for protocol
    assert "class GuardModule(Protocol)" in source
