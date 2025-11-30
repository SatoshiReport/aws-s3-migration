"""Tests for cleanup_temp_artifacts/db_loader.py integration and helpers."""

# pylint: disable=redefined-outer-name

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
CacheWriteError = db_loader.CacheWriteError
DatabaseInfo = db_loader.DatabaseInfo
ScanContext = db_loader.ScanContext
_try_load_from_cache = db_loader._try_load_from_cache  # pylint: disable=protected-access
load_candidates_from_db = db_loader.load_candidates_from_db
write_cache_if_needed = db_loader.write_cache_if_needed


def _dummy_matcher(path: Path, is_dir: bool) -> bool:  # pylint: disable=unused-argument
    return True


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


@pytest.fixture
def mock_category():
    """Create mock Category."""
    return Category("cat1", "desc1", _dummy_matcher)


def test_try_load_from_cache_valid(tmp_path, capsys):
    """Test _try_load_from_cache with valid cache."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "test.json"
    cache_file.write_text('{"version": 1}')

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

    category = Category("cat1", "desc1", _dummy_matcher)
    candidate = Candidate(path=Path("/tmp/test"), category=category, size_bytes=1024, mtime=12345)
    metadata = {
        "generated_at": "2025-11-12T00:00:00+00:00",
        "rowcount": 100,
        "max_rowid": 500,
        "db_mtime_ns": 123456789,
    }

    with patch("cleanup_temp_artifacts.db_loader.build_cache_key", return_value="test"):
        with patch(
            "cleanup_temp_artifacts.db_loader.load_cache", return_value=([candidate], metadata)
        ):
            with patch("cleanup_temp_artifacts.db_loader.cache_is_valid", return_value=True):
                cache_path, cache_used, candidates = _try_load_from_cache(
                    cache_config,
                    Path("/base"),
                    mock_db_info,
                    {"categories": ["cat1"]},
                    {"cat1": category},
                )

    assert cache_path is not None
    assert cache_used is True
    assert candidates is not None
    assert len(candidates) == 1

    captured = capsys.readouterr()
    assert "Using cached results" in captured.out


def test_try_load_from_cache_cache_invalid_validation_failed(tmp_path):
    """Test _try_load_from_cache when cache validation explicitly fails."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "test.json"
    cache_file.write_text('{"version": 1}')

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

    category = Category("cat1", "desc1", _dummy_matcher)
    candidate = Candidate(path=Path("/tmp/test"), category=category, size_bytes=1024, mtime=12345)
    metadata = {
        "generated_at": "2025-11-12T00:00:00+00:00",
        "rowcount": 100,
        "max_rowid": 500,
        "db_mtime_ns": 123456789,
    }

    with patch("cleanup_temp_artifacts.db_loader.build_cache_key", return_value="test"):
        with patch(
            "cleanup_temp_artifacts.db_loader.load_cache", return_value=([candidate], metadata)
        ):
            with patch("cleanup_temp_artifacts.db_loader.cache_is_valid", return_value=False):
                cache_path, cache_used, candidates = _try_load_from_cache(
                    cache_config,
                    Path("/base"),
                    mock_db_info,
                    {"categories": ["cat1"]},
                    {"cat1": category},
                )

    assert cache_path is not None
    assert cache_used is False
    assert candidates is None


def test_load_candidates_from_db_success(mock_args, tmp_path):
    """Test load_candidates_from_db end-to-end."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")
    conn.execute("INSERT INTO files VALUES ('b1', 'k1', 100)")
    conn.commit()
    conn.close()

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
        result = load_candidates_from_db(
            args=mock_args,
            base_path=Path("/base"),
            db_path=db_path,
            db_stat=mock_stat,
            cutoff_ts=None,
            scan_params={"categories": ["cat1"]},
        )

    assert len(result.candidates) == 1
    assert_equal(result.total_files, 1)


def test_load_candidates_from_db_closes_connection(mock_args, tmp_path):
    """Test load_candidates_from_db closes connection even on error."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")
    conn.commit()
    conn.close()

    mock_stat = MagicMock()
    mock_stat.st_mtime_ns = 123456789

    with patch("cleanup_temp_artifacts.db_loader._perform_scan_operations") as mock_scan:
        mock_scan.side_effect = RuntimeError("Test error")

        with pytest.raises(RuntimeError, match="Test error"):
            load_candidates_from_db(
                args=mock_args,
                base_path=Path("/base"),
                db_path=db_path,
                db_stat=mock_stat,
                cutoff_ts=None,
                scan_params={"categories": ["cat1"]},
            )


def test_scan_context_dataclass(mock_args):
    """Test ScanContext dataclass creation."""
    category = Category("cat1", "desc1", _dummy_matcher)
    ctx = ScanContext(
        args=mock_args,
        scan_params={"categories": ["cat1"]},
        category_map={"cat1": category},
        cutoff_ts=12345.67,
    )

    assert ctx.args == mock_args
    assert_equal(ctx.scan_params, {"categories": ["cat1"]})
    assert_equal(ctx.category_map["cat1"].name, "cat1")
    assert_equal(ctx.cutoff_ts, 12345.67)


def test_scan_context_none_cutoff(mock_args):
    """Test ScanContext with None cutoff_ts."""
    category = Category("cat1", "desc1", _dummy_matcher)
    ctx = ScanContext(
        args=mock_args,
        scan_params={"categories": ["cat1"]},
        category_map={"cat1": category},
        cutoff_ts=None,
    )

    assert ctx.cutoff_ts is None


def test_write_cache_if_needed_disabled():
    """Test write_cache_if_needed when cache is disabled."""
    cache_config = CacheConfig(
        enabled=False,
        cache_dir=Path("/tmp/cache"),
        refresh_cache=False,
        cache_ttl=3600,
    )
    load_result = MagicMock()

    with patch("cleanup_temp_artifacts.db_loader.write_cache") as mock_write:
        write_cache_if_needed(
            cache_config,
            load_result,
            cache_path=Path("/cache/test.json"),
            cache_used=False,
            base_path=Path("/base"),
            db_info=MagicMock(),
            scan_params={},
        )

        mock_write.assert_not_called()


def test_write_cache_if_needed_cache_used():
    """Test write_cache_if_needed when cache was already used."""
    cache_config = CacheConfig(
        enabled=True,
        cache_dir=Path("/tmp/cache"),
        refresh_cache=False,
        cache_ttl=3600,
    )
    load_result = MagicMock()

    with patch("cleanup_temp_artifacts.db_loader.write_cache") as mock_write:
        write_cache_if_needed(
            cache_config,
            load_result,
            cache_path=Path("/cache/test.json"),
            cache_used=True,
            base_path=Path("/base"),
            db_info=MagicMock(),
            scan_params={},
        )

        mock_write.assert_not_called()


def test_write_cache_if_needed_no_cache_path():
    """Test write_cache_if_needed when no cache path provided."""
    cache_config = CacheConfig(
        enabled=True,
        cache_dir=Path("/tmp/cache"),
        refresh_cache=False,
        cache_ttl=3600,
    )
    load_result = MagicMock()

    with patch("cleanup_temp_artifacts.db_loader.write_cache") as mock_write:
        write_cache_if_needed(
            cache_config,
            load_result,
            cache_path=None,
            cache_used=False,
            base_path=Path("/base"),
            db_info=MagicMock(),
            scan_params={},
        )

        mock_write.assert_not_called()


def test_write_cache_if_needed_success(tmp_path):
    """Test write_cache_if_needed writes cache successfully."""
    cache_config = CacheConfig(
        enabled=True,
        cache_dir=tmp_path / "cache",
        refresh_cache=False,
        cache_ttl=3600,
    )
    category = Category("cat1", "desc1", _dummy_matcher)
    candidate = Candidate(path=Path("/tmp/test"), category=category, size_bytes=1024, mtime=12345)
    load_result = MagicMock()
    load_result.candidates = [candidate]

    mock_db_info = MagicMock()
    mock_db_info.db_path = Path("/tmp/test.db")
    mock_db_info.total_files = 100
    mock_db_info.max_rowid = 500
    mock_db_info.db_stat.st_mtime_ns = 123456789

    cache_path = tmp_path / "cache" / "test.json"
    scan_params = {"categories": ["cat1"]}

    with patch("cleanup_temp_artifacts.db_loader.write_cache") as mock_write:
        write_cache_if_needed(
            cache_config,
            load_result,
            cache_path=cache_path,
            cache_used=False,
            base_path=Path("/base"),
            db_info=mock_db_info,
            scan_params=scan_params,
        )

        mock_write.assert_called_once_with(
            cache_path,
            [candidate],
            scan_params=scan_params,
            base_path=Path("/base"),
            db_info=mock_db_info,
        )


def test_write_cache_if_needed_handles_oserror(tmp_path):
    """Test write_cache_if_needed raises CacheWriteError on OSError."""
    cache_config = CacheConfig(
        enabled=True,
        cache_dir=tmp_path / "cache",
        refresh_cache=False,
        cache_ttl=3600,
    )
    load_result = MagicMock()
    load_result.candidates = []

    cache_path = tmp_path / "cache" / "test.json"

    with patch("cleanup_temp_artifacts.db_loader.write_cache") as mock_write:
        mock_write.side_effect = OSError("Permission denied")

        with pytest.raises(CacheWriteError, match="Failed to write cache.*Permission denied"):
            write_cache_if_needed(
                cache_config,
                load_result,
                cache_path=cache_path,
                cache_used=False,
                base_path=Path("/base"),
                db_info=MagicMock(),
                scan_params={},
            )
