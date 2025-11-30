"""Coverage-focused tests for duplicate_tree_report re-exports."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

import duplicate_tree_report as dtr
from tests.assertions import assert_equal


def test_reexported_symbols_are_accessible():
    """Smoke-check that the public API exposes the expected helpers."""
    index = dtr.DirectoryIndex()
    index.add_file("bucket", "dir/path.txt", 10, "abc")
    index.finalize()
    clusters = dtr.find_exact_duplicates(index)
    assert isinstance(clusters, list)
    assert dtr.DuplicateCluster.__name__ == "DuplicateCluster"


def test_main_delegates_to_cli(monkeypatch):
    """Ensure duplicate_tree_report.main routes to duplicate_tree_cli."""
    class DummyCliModule(ModuleType):
        """Minimal module stub that exposes a main entry point."""

        def __init__(self) -> None:
            super().__init__("duplicate_tree_cli")

        def main(self, _argv=None):  # pragma: no cover - stubbed for tests
            """Return the stubbed exit code."""
            return 42

    dummy_cli = DummyCliModule()
    monkeypatch.setitem(sys.modules, "duplicate_tree_cli", dummy_cli)
    module = importlib.reload(dtr)
    assert_equal(module.main([]), 42)
