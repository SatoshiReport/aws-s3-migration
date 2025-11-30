"""Tests for cleanup_temp_artifacts/db_loader.py database operations."""

# pylint: disable=import-outside-toplevel

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# pylint: disable=no-name-in-module
from cleanup_temp_artifacts import categories, core_scanner, db_loader
from tests.assertions import assert_equal

Category = categories.Category
CandidateLoadError = core_scanner.CandidateLoadError
_build_cache_and_db_info = db_loader._build_cache_and_db_info  # pylint: disable=protected-access
_create_db_connection = db_loader._create_db_connection  # pylint: disable=protected-access
_get_db_file_stats = db_loader._get_db_file_stats  # pylint: disable=protected-access


def _dummy_matcher(path: Path, is_dir: bool) -> bool:  # pylint: disable=unused-argument
    return True


def test_get_db_file_stats_success(tmp_path):
    """Test _get_db_file_stats returns correct counts."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")
    conn.execute("INSERT INTO files VALUES ('b1', 'k1', 100)")
    conn.execute("INSERT INTO files VALUES ('b2', 'k2', 200)")
    conn.commit()

    total_files, max_rowid = _get_db_file_stats(conn)

    assert_equal(total_files, 2)
    assert_equal(max_rowid, 2)
    conn.close()


def test_get_db_file_stats_empty_table(tmp_path):
    """Test _get_db_file_stats with empty table."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")
    conn.commit()

    total_files, max_rowid = _get_db_file_stats(conn)

    assert_equal(total_files, 0)
    assert_equal(max_rowid, 0)
    conn.close()


def test_get_db_file_stats_missing_table(tmp_path):
    """Test _get_db_file_stats raises error when files table missing."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE wrong_table (id INTEGER)")
    conn.commit()

    with pytest.raises(CandidateLoadError, match="missing expected 'files' table"):
        _get_db_file_stats(conn)

    conn.close()


def test_get_db_file_stats_requires_rowid(tmp_path):
    """Test _get_db_file_stats fails when MAX(rowid) cannot be read."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE files (bucket TEXT PRIMARY KEY, key TEXT, size INTEGER) WITHOUT ROWID"
    )
    conn.execute("INSERT INTO files VALUES ('b1', 'k1', 100)")
    conn.execute("INSERT INTO files VALUES ('b2', 'k2', 200)")
    conn.execute("INSERT INTO files VALUES ('b3', 'k3', 300)")
    conn.execute("INSERT INTO files VALUES ('b4', 'k4', 400)")
    conn.execute("INSERT INTO files VALUES ('b5', 'k5', 500)")
    conn.commit()

    with pytest.raises(CandidateLoadError, match="rowid"):
        _get_db_file_stats(conn)

    conn.close()


def test_create_db_connection_success(tmp_path):
    """Test _create_db_connection creates valid connection."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE test (id INTEGER)")
    conn.close()

    conn = _create_db_connection(db_path)

    assert conn is not None
    assert isinstance(conn.row_factory, type(sqlite3.Row))
    conn.close()


def test_create_db_connection_nonexistent_path():
    """Test _create_db_connection with nonexistent path creates new DB."""
    db_path = Path("/tmp/nonexistent_test_db_12345.db")

    try:
        conn = _create_db_connection(db_path)
        assert conn is not None
        conn.close()
    finally:
        if db_path.exists():
            db_path.unlink()


def test_cache_config_dataclass():
    """Test CacheConfig dataclass creation."""
    from cleanup_temp_artifacts.db_loader import CacheConfig  # pylint: disable=no-name-in-module

    config = CacheConfig(
        enabled=True,
        cache_dir=Path("/tmp/cache"),
        refresh_cache=False,
        cache_ttl=3600,
    )

    assert_equal(config.enabled, True)
    assert_equal(config.cache_dir, Path("/tmp/cache"))
    assert_equal(config.refresh_cache, False)
    assert_equal(config.cache_ttl, 3600)


def test_database_info_dataclass():
    """Test DatabaseInfo dataclass creation."""
    from cleanup_temp_artifacts.db_loader import DatabaseInfo  # pylint: disable=no-name-in-module

    mock_stat = MagicMock()
    mock_stat.st_mtime_ns = 123456789

    info = DatabaseInfo(
        db_path=Path("/tmp/test.db"),
        db_stat=mock_stat,
        total_files=100,
        max_rowid=500,
    )

    assert_equal(info.db_path, Path("/tmp/test.db"))
    assert_equal(info.total_files, 100)
    assert_equal(info.max_rowid, 500)
    assert_equal(info.db_stat.st_mtime_ns, 123456789)


def test_build_cache_and_db_info():
    """Test _build_cache_and_db_info creates correct objects."""
    args = argparse.Namespace()
    args.cache_enabled = True
    args.cache_dir = Path("/tmp/cache")
    args.refresh_cache = False
    args.cache_ttl = 3600
    args.categories = [Category("cat1", "desc1", _dummy_matcher)]
    args.min_size_bytes = 1024

    mock_stat = MagicMock()
    mock_stat.st_mtime_ns = 123456789
    db_path = Path("/tmp/test.db")

    cache_config, db_info = _build_cache_and_db_info(
        args, db_path, mock_stat, total_files=100, max_rowid=500
    )

    assert_equal(cache_config.enabled, True)
    assert_equal(cache_config.cache_dir, Path("/tmp/cache"))
    assert_equal(cache_config.refresh_cache, False)
    assert_equal(cache_config.cache_ttl, 3600)

    assert_equal(db_info.db_path, db_path)
    assert_equal(db_info.total_files, 100)
    assert_equal(db_info.max_rowid, 500)
