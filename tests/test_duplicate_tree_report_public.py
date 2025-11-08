"""Coverage-focused tests for duplicate_tree_report re-exports."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

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
    dummy_cli = SimpleNamespace(main=lambda argv=None: 42)
    monkeypatch.setitem(sys.modules, "duplicate_tree_cli", dummy_cli)
    monkeypatch.setitem(sys.modules, "aws.duplicate_tree_cli", dummy_cli)
    module = importlib.reload(dtr)
    assert_equal(module.main([]), 42)
