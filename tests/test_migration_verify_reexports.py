"""Tests ensuring migration_verify re-exports primary helpers."""

from __future__ import annotations

import migration_verify as mv
from migration_verify_bucket import BucketVerifier
from migration_verify_checksums import FileChecksumVerifier
from migration_verify_delete import BucketDeleter
from migration_verify_inventory import FileInventoryChecker


def test_reexports_match_original_symbols():
    """Test that migration_verify module reexports original symbols correctly."""
    assert mv.BucketVerifier is BucketVerifier
    assert mv.FileChecksumVerifier is FileChecksumVerifier
    assert mv.BucketDeleter is BucketDeleter
    assert mv.FileInventoryChecker is FileInventoryChecker
    assert isinstance(mv.IGNORED_FILE_PATTERNS, list)
    assert mv.MAX_ERROR_DISPLAY > 0


def test_fallback_import_path_executes():
    """Load migration_verify as a standalone module to hit the fallback branch."""
    import importlib.util
    import pathlib

    module_path = pathlib.Path(mv.__file__)
    spec = importlib.util.spec_from_file_location("mv_standalone", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)  # type: ignore[assignment]
    assert hasattr(module, "BucketVerifier")


def test_package_import_triggers_relative_branch():
    """Import the module via the aws package to exercise the relative import path."""
    import importlib
    import sys

    top_level = sys.modules.pop("migration_verify", None)
    package_level = sys.modules.pop("aws.migration_verify", None)
    try:
        pkg_module = importlib.import_module("aws.migration_verify")
        assert pkg_module.__package__ == "aws"
        assert hasattr(pkg_module, "BucketVerifier")
    finally:
        if top_level is not None:
            sys.modules["migration_verify"] = top_level
        if package_level is not None:
            sys.modules["aws.migration_verify"] = package_level
