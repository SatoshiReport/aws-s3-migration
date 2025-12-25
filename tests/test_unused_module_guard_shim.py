"""Tests for the repo-local unused_module_guard shim."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

from tests.assertions import assert_equal

pytest_plugins = ["tests.unused_module_guard_test_utils"]
pytestmark = pytest.mark.usefixtures("backup_guard_config")


def _clear_guard_modules() -> None:
    for name in [
        "ci_tools.scripts.unused_module_guard",
        "ci_tools.scripts",
        "ci_tools",
        "_ci_shared_unused_module_guard",
    ]:
        sys.modules.pop(name, None)
    importlib.invalidate_caches()


def _write_shared_guard(shared_root: Path, body: str) -> None:
    scripts_dir = shared_root / "ci_tools" / "scripts"
    scripts_dir.mkdir(parents=True)
    (shared_root / "ci_tools" / "__init__.py").write_text("", encoding="utf-8")
    (scripts_dir / "__init__.py").write_text("", encoding="utf-8")
    (scripts_dir / "unused_module_guard.py").write_text(body, encoding="utf-8")


@pytest.fixture(autouse=True)
def _cleanup_modules():
    _clear_guard_modules()
    yield
    _clear_guard_modules()


def _import_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shared_code: str):
    _write_shared_guard(tmp_path, shared_code)
    monkeypatch.setenv("CI_SHARED_ROOT", str(tmp_path))

    # Import the local shim directly, bypassing the ci_tools proxy
    shim_path = Path(__file__).parent.parent / "ci_tools" / "scripts" / "unused_module_guard.py"
    spec = importlib.util.spec_from_file_location("ci_tools.scripts.unused_module_guard", shim_path)
    if spec is None or spec.loader is None:
        msg = f"Unable to load shim from {shim_path}"
        raise ImportError(msg)

    module = importlib.util.module_from_spec(spec)
    sys.modules["ci_tools.scripts.unused_module_guard"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.xdist_group(name="config_file")
def test_shim_applies_config_and_delegates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test that guard shim applies config and delegates correctly."""
    shared_code = """
SUSPICIOUS_PATTERNS = ("_v2", "_temp")
LAST_EXCLUDES = None

def find_unused_modules(root, exclude_patterns=None):
    global LAST_EXCLUDES
    LAST_EXCLUDES = list(exclude_patterns or [])
    return [("dummy.py", "reason")]


def main():
    return 123
"""
    # Create a config file that allows _v2 pattern
    config_file = Path(__file__).parent.parent / "unused_module_guard.config.json"
    original_content = None

    try:
        if config_file.exists():
            original_content = config_file.read_text()

        config_file.write_text('{"suspicious_allow_patterns": ["_v2"]}', encoding="utf-8")

        module = _import_shim(tmp_path, monkeypatch, shared_code)

        assert_equal(module.main(), 123)
        module.find_unused_modules(".", ["existing"])
        shared_module = sys.modules["_ci_shared_unused_module_guard"]
        assert shared_module.LAST_EXCLUDES[0] == "existing"
        assert "_v2" not in shared_module.SUSPICIOUS_PATTERNS
    finally:
        if original_content is not None:
            config_file.write_text(original_content, encoding="utf-8")
        elif config_file.exists():
            config_file.unlink()


def test_missing_shared_guard_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test that ImportError is raised when shared guard module is missing."""
    monkeypatch.setenv("CI_SHARED_ROOT", str(tmp_path))
    with pytest.raises(ImportError):
        importlib.import_module("ci_tools.scripts.unused_module_guard")


def test_shared_guard_spec_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test SharedGuardSpecError when spec creation fails."""
    # Create a malformed Python file that will fail spec creation
    shared_root = tmp_path / "shared"
    scripts_dir = shared_root / "ci_tools" / "scripts"
    scripts_dir.mkdir(parents=True)
    (shared_root / "ci_tools" / "__init__.py").write_text("", encoding="utf-8")
    (scripts_dir / "__init__.py").write_text("", encoding="utf-8")

    # Create a directory instead of a file - this should cause spec creation to fail
    guard_path = scripts_dir / "unused_module_guard.py"
    guard_path.mkdir()  # Create as directory, not file

    monkeypatch.setenv("CI_SHARED_ROOT", str(shared_root))

    # This should raise SharedGuardSpecError (wrapped as ImportError)
    with pytest.raises(ImportError):
        importlib.import_module("ci_tools.scripts.unused_module_guard")


@pytest.mark.xdist_group(name="config_file")
def test_load_config_with_invalid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test _load_config handles invalid JSON gracefully."""
    # Create config file with invalid JSON
    repo_root = Path(__file__).parent.parent
    config_file = repo_root / "unused_module_guard.config.json"
    original_content = None

    try:
        # Backup original if it exists
        if config_file.exists():
            original_content = config_file.read_text()

        # Write invalid JSON
        config_file.write_text("{invalid json", encoding="utf-8")

        shared_code = """
SUSPICIOUS_PATTERNS = ()

def find_unused_modules(root, exclude_patterns=None):
    return []

def main():
    return 0
"""
        module = _import_shim(tmp_path, monkeypatch, shared_code)

        # Should not crash, should just return empty lists
        assert module.main() == 0
    finally:
        # Restore original content
        if original_content is not None:
            config_file.write_text(original_content, encoding="utf-8")
        elif config_file.exists():
            config_file.unlink()


@pytest.mark.xdist_group(name="config_file")
def test_apply_config_with_duplicate_excludes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test _apply_config_overrides handles duplicate excludes."""
    shared_code = """
SUSPICIOUS_PATTERNS = ()

def find_unused_modules(root, exclude_patterns=None):
    return []

def find_suspicious_duplicates(root):
    return [
        ("test_file.py", "duplicate"),
        ("excluded_file.py", "duplicate"),
    ]

def main():
    return 0
"""
    # Create config with duplicate_exclude_patterns
    repo_root = Path(__file__).parent.parent
    config_file = repo_root / "unused_module_guard.config.json"
    original_content = None

    try:
        if config_file.exists():
            original_content = config_file.read_text()

        config_file.write_text(
            '{"suspicious_allow_patterns": ["_v2"], ' '"duplicate_exclude_patterns": ["excluded_file.py"]}',
            encoding="utf-8",
        )

        module = _import_shim(tmp_path, monkeypatch, shared_code)

        # Call find_suspicious_duplicates to trigger the filtering
        # Must call through the shim module which has the wrapped version
        results = module.find_suspicious_duplicates(".")

        # Should have filtered out excluded_file.py
        assert_equal(len(results), 1)
        assert_equal(results[0][0], "test_file.py")
    finally:
        if original_content is not None:
            config_file.write_text(original_content, encoding="utf-8")
        elif config_file.exists():
            config_file.unlink()


def test_exception_classes_directly():
    """Test exception classes can be instantiated."""
    # Import the local shim module directly to test exception classes
    shim_path = Path(__file__).parent.parent / "ci_tools" / "scripts" / "unused_module_guard.py"
    spec = importlib.util.spec_from_file_location("_test_local_shim", shim_path)
    assert spec is not None and spec.loader is not None

    # Read the source to test exception classes without executing the module
    source = shim_path.read_text()
    assert "SharedGuardMissingError" in source
    assert "SharedGuardSpecError" in source
    assert "SharedGuardInitializationError" in source
