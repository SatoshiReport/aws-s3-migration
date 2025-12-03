"""Shared fixtures for cleanup_temp_artifacts DB loader tests."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cleanup_temp_artifacts.categories import Category
from cleanup_temp_artifacts.core_scanner import Candidate
from cleanup_temp_artifacts.db_loader import DatabaseInfo


def _dummy_matcher(_path: Path) -> bool:
    return True


@pytest.fixture
def mock_args():
    """Create mock argparse.Namespace with required attributes."""
    args = argparse.Namespace()
    args.cache_enabled = True
    args.cache_dir = Path("/tmp/cache")
    args.refresh_cache = False
    args.cache_ttl = 3600
    args.categories = [Category("cat1", "desc1", _dummy_matcher, prune=True)]
    args.min_size_bytes = None
    return args


@pytest.fixture
def mock_db_info():
    """Create mock DatabaseInfo."""
    mock_stat = MagicMock()
    mock_stat.st_mtime_ns = 123456789
    return DatabaseInfo(
        db_path=Path("/tmp/test.db"),
        db_stat=mock_stat,
        total_files=100,
        max_rowid=500,
    )


@pytest.fixture(name="mock_category")
def _mock_category():
    """Create mock Category."""
    return Category("cat1", "desc1", _dummy_matcher, prune=True)


@pytest.fixture
def dummy_candidate(mock_category):
    """Create a reusable dummy Candidate."""
    return Candidate(
        path=Path("/tmp/test"),
        category=mock_category,
        size_bytes=1024,
        mtime=12345,
    )
