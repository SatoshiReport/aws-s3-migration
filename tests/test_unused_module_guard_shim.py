"""Tests for the repo-local unused_module_guard shim."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

from tests.assertions import assert_equal


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
    module = _import_shim(tmp_path, monkeypatch, shared_code)

    assert_equal(module.main(), 123)
    module.find_unused_modules(".", ["existing"])
    shared_module = sys.modules["_ci_shared_unused_module_guard"]
    assert shared_module.LAST_EXCLUDES[0] == "existing"
    assert "tests/" in shared_module.LAST_EXCLUDES
    assert "_v2" not in module.SUSPICIOUS_PATTERNS


def test_missing_shared_guard_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test that ImportError is raised when shared guard module is missing."""
    monkeypatch.setenv("CI_SHARED_ROOT", str(tmp_path))
    with pytest.raises(ImportError):
        importlib.import_module("ci_tools.scripts.unused_module_guard")
