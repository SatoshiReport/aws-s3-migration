"""Tests for cleanup_temp_artifacts/db_loader.py cache operations."""

# pylint: disable=redefined-outer-name,import-outside-toplevel

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# pylint: disable=no-name-in-module
from cleanup_temp_artifacts import categories, core_scanner, db_loader
from tests.assertions import assert_equal

Category = categories.Category
Candidate = core_scanner.Candidate
CacheConfig = db_loader.CacheConfig
DatabaseInfo = db_loader.DatabaseInfo
ScanContext = db_loader.ScanContext
_load_or_scan_candidates = db_loader._load_or_scan_candidates  # pylint: disable=protected-access
_perform_scan_operations = db_loader._perform_scan_operations  # pylint: disable=protected-access
_try_load_from_cache = db_loader._try_load_from_cache  # pylint: disable=protected-access


def _dummy_matcher(path: Path, is_dir: bool) -> bool:  # pylint: disable=unused-argument
    return True


def test_try_load_from_cache_disabled():
    """Test _try_load_from_cache when cache is disabled."""
    cache_config = CacheConfig(
        enabled=False,
        cache_dir=Path("/tmp/cache"),
        refresh_cache=False,
        cache_ttl=3600,
    )
    mock_db_info = MagicMock()

    cache_path, cache_used, candidates = _try_load_from_cache(
        cache_config,
        Path("/base"),
        mock_db_info,
        {"categories": ["cat1"]},
        {"cat1": Category("cat1", "desc1", _dummy_matcher)},
    )

    assert cache_path is None
    assert cache_used is False
    assert candidates is None


def test_try_load_from_cache_file_not_exists(tmp_path):
    """Test _try_load_from_cache when cache file doesn't exist."""
    cache_config = CacheConfig(
        enabled=True,
        cache_dir=tmp_path / "cache",
        refresh_cache=False,
        cache_ttl=3600,
    )
    mock_db_info = MagicMock()
    mock_db_info.db_path = Path("/tmp/test.db")
    mock_db_info.total_files = 100
    mock_db_info.max_rowid = 500
    mock_db_info.db_stat.st_mtime_ns = 123456789

    cache_path, cache_used, candidates = _try_load_from_cache(
        cache_config,
        Path("/base"),
        mock_db_info,
        {"categories": ["cat1"]},
        {"cat1": Category("cat1", "desc1", _dummy_matcher)},
    )

    assert cache_path is not None
    assert cache_used is False
    assert candidates is None


def test_try_load_from_cache_refresh_requested(tmp_path):
    """Test _try_load_from_cache when refresh is requested."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "test.json"
    cache_file.write_text('{"version": 1}')

    cache_config = CacheConfig(
        enabled=True,
        cache_dir=cache_dir,
        refresh_cache=True,
        cache_ttl=3600,
    )
    mock_db_info = MagicMock()
    mock_db_info.db_path = Path("/tmp/test.db")

    with patch("cleanup_temp_artifacts.db_loader.build_cache_key", return_value="test"):
        cache_path, cache_used, candidates = _try_load_from_cache(
            cache_config,
            Path("/base"),
            mock_db_info,
            {"categories": ["cat1"]},
            {"cat1": Category("cat1", "desc1", _dummy_matcher)},
        )

    assert cache_path is not None
    assert cache_used is False
    assert candidates is None


def test_try_load_from_cache_invalid_cache(tmp_path):
    """Test _try_load_from_cache when cached data is invalid."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "test.json"
    cache_file.write_text('{"version": 0}')

    cache_config = CacheConfig(
        enabled=True,
        cache_dir=cache_dir,
        refresh_cache=False,
        cache_ttl=3600,
    )
    mock_db_info = MagicMock()
    mock_db_info.db_path = Path("/tmp/test.db")
    mock_db_info.total_files = 100
    mock_db_info.max_rowid = 500
    mock_db_info.db_stat.st_mtime_ns = 123456789

    with patch("cleanup_temp_artifacts.db_loader.build_cache_key", return_value="test"):
        with patch("cleanup_temp_artifacts.db_loader.load_cache", return_value=None):
            cache_path, cache_used, candidates = _try_load_from_cache(
                cache_config,
                Path("/base"),
                mock_db_info,
                {"categories": ["cat1"]},
                {"cat1": Category("cat1", "desc1", _dummy_matcher)},
            )

    assert cache_path is not None
    assert cache_used is False
    assert candidates is None


@pytest.fixture
def mock_args():
    """Create mock argparse.Namespace with required attributes."""
    args = argparse.Namespace()
    args.cache_enabled = True
    args.cache_dir = Path("/tmp/cache")
    args.refresh_cache = False
    args.cache_ttl = 3600
    args.categories = [Category("cat1", "desc1", _dummy_matcher)]
    args.min_size_bytes = 1024
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


def test_load_or_scan_candidates_from_cache(mock_args, mock_db_info):
    """Test _load_or_scan_candidates loads from cache when available."""
    conn = MagicMock()
    category = Category("cat1", "desc1", _dummy_matcher)
    candidate = Candidate(path=Path("/tmp/test"), category=category, size_bytes=1024, mtime=12345)

    cache_config = CacheConfig(
        enabled=True,
        cache_dir=Path("/tmp/cache"),
        refresh_cache=False,
        cache_ttl=3600,
    )
    scan_ctx = ScanContext(
        args=mock_args,
        scan_params={"categories": ["cat1"]},
        category_map={"cat1": category},
        cutoff_ts=None,
    )

    with patch(
        "cleanup_temp_artifacts.db_loader._try_load_from_cache",
        return_value=(Path("/cache/test.json"), True, [candidate]),
    ):
        cache_path, cache_used, candidates = _load_or_scan_candidates(
            conn,
            cache_config=cache_config,
            base_path=Path("/base"),
            db_info=mock_db_info,
            scan_ctx=scan_ctx,
        )

    assert cache_path == Path("/cache/test.json")
    assert cache_used is True
    assert len(candidates) == 1
    assert_equal(candidates[0].path, Path("/tmp/test"))


def test_load_or_scan_candidates_from_db(mock_args, mock_db_info):
    """Test _load_or_scan_candidates scans DB when cache unavailable."""
    conn = MagicMock()
    category = Category("cat1", "desc1", _dummy_matcher)
    candidate = Candidate(path=Path("/tmp/test"), category=category, size_bytes=1024, mtime=12345)

    cache_config = CacheConfig(
        enabled=True,
        cache_dir=Path("/tmp/cache"),
        refresh_cache=False,
        cache_ttl=3600,
    )
    scan_ctx = ScanContext(
        args=mock_args,
        scan_params={"categories": ["cat1"]},
        category_map={"cat1": category},
        cutoff_ts=None,
    )

    with patch(
        "cleanup_temp_artifacts.db_loader._try_load_from_cache",
        return_value=(Path("/cache/test.json"), False, None),
    ):
        with patch(
            "cleanup_temp_artifacts.db_loader.scan_candidates_from_db", return_value=[candidate]
        ):
            cache_path, cache_used, candidates = _load_or_scan_candidates(
                conn,
                cache_config=cache_config,
                base_path=Path("/base"),
                db_info=mock_db_info,
                scan_ctx=scan_ctx,
            )

    assert cache_path == Path("/cache/test.json")
    assert cache_used is False
    assert len(candidates) == 1


def test_perform_scan_operations_success(mock_args, tmp_path):
    """Test _perform_scan_operations completes full scan."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")
    conn.execute("INSERT INTO files VALUES ('b1', 'k1', 100)")
    conn.commit()

    mock_stat = MagicMock()
    mock_stat.st_mtime_ns = 123456789

    with patch(
        "cleanup_temp_artifacts.db_loader.scan_candidates_from_db",
        return_value=[
            Candidate(
                path=Path("/tmp/test"),
                category=mock_args.categories[0],
                size_bytes=1024,
                mtime=12345,
            )
        ],
    ):
        result = _perform_scan_operations(
            conn,
            args=mock_args,
            base_path=Path("/base"),
            db_path=db_path,
            db_stat=mock_stat,
            cutoff_ts=None,
            scan_params={"categories": ["cat1"]},
        )

    assert len(result.candidates) == 1
    assert_equal(result.total_files, 1)
    assert result.max_rowid > 0
    conn.close()


def test_perform_scan_operations_with_cache(mock_args, tmp_path):
    """Test _perform_scan_operations uses cache when available."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")
    conn.execute("INSERT INTO files VALUES ('b1', 'k1', 100)")
    conn.commit()

    mock_stat = MagicMock()
    mock_stat.st_mtime_ns = 123456789

    category = mock_args.categories[0]
    cached_candidate = Candidate(
        path=Path("/tmp/cached"), category=category, size_bytes=2048, mtime=54321
    )

    # Use _try_load_from_cache to properly mock the cache loading
    with patch(
        "cleanup_temp_artifacts.db_loader._try_load_from_cache",
        return_value=(Path("/cache/test.json"), True, [cached_candidate]),
    ):
        result = _perform_scan_operations(
            conn,
            args=mock_args,
            base_path=Path("/base"),
            db_path=db_path,
            db_stat=mock_stat,
            cutoff_ts=None,
            scan_params={"categories": ["cat1"]},
        )

    assert len(result.candidates) == 1
    assert_equal(result.candidates[0].path, Path("/tmp/cached"))
    assert result.cache_used is True
    conn.close()
