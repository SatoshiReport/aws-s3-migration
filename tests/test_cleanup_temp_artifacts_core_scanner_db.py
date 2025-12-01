"""Tests for cleanup_temp_artifacts/core_scanner.py database scanning operations."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

# pylint: disable=no-name-in-module
from cleanup_temp_artifacts import categories, core_scanner
from cleanup_temp_artifacts.core_scanner import CandidateLoadError
from tests.assertions import assert_equal

Category = categories.Category
scan_candidates_from_db = core_scanner.scan_candidates_from_db


def _dummy_matcher(path: Path, is_dir: bool) -> bool:  # pylint: disable=unused-argument
    """Dummy matcher that always returns True."""
    return True


def _pycache_matcher(path: Path, is_dir: bool) -> bool:
    """Match __pycache__ directories."""
    return is_dir and path.name == "__pycache__"


def test_scan_candidates_from_db_empty_database(tmp_path):
    """Test scan_candidates_from_db with empty database."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")
    conn.commit()

    category = Category("pycache", "Python cache", _pycache_matcher, prune=True)

    result = scan_candidates_from_db(
        conn,
        tmp_path,
        [category],
        cutoff_ts=None,
        min_size_bytes=None,
        total_files=0,
    )

    assert_equal(len(result), 0)
    conn.close()


def test_scan_candidates_from_db_with_data(tmp_path):
    """Test scan_candidates_from_db with actual data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")

    pycache_dir = tmp_path / "mybucket" / "code" / "__pycache__"
    pycache_dir.mkdir(parents=True)

    conn.execute(
        "INSERT INTO files (bucket, key, size) VALUES (?, ?, ?)",
        ("mybucket", "code/__pycache__/module.pyc", 1024),
    )
    conn.commit()

    category = Category("pycache", "Python cache", _pycache_matcher, prune=True)

    result = scan_candidates_from_db(
        conn,
        tmp_path,
        [category],
        cutoff_ts=None,
        min_size_bytes=None,
        total_files=1,
    )

    assert_equal(len(result), 1)
    assert pycache_dir.resolve() == result[0].path
    assert_equal(result[0].size_bytes, 1024)
    conn.close()


def test_scan_candidates_from_db_filters_by_size(tmp_path):
    """Test scan_candidates_from_db applies size filter."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")

    small_dir = tmp_path / "mybucket" / "small" / "__pycache__"
    small_dir.mkdir(parents=True)

    large_dir = tmp_path / "mybucket" / "large" / "__pycache__"
    large_dir.mkdir(parents=True)

    conn.execute(
        "INSERT INTO files (bucket, key, size) VALUES (?, ?, ?)",
        ("mybucket", "small/__pycache__/module.pyc", 100),
    )
    conn.execute(
        "INSERT INTO files (bucket, key, size) VALUES (?, ?, ?)",
        ("mybucket", "large/__pycache__/module.pyc", 10000),
    )
    conn.commit()

    category = Category("pycache", "Python cache", _pycache_matcher, prune=True)

    result = scan_candidates_from_db(
        conn,
        tmp_path,
        [category],
        cutoff_ts=None,
        min_size_bytes=5000,
        total_files=2,
    )

    assert_equal(len(result), 1)
    assert large_dir.resolve() == result[0].path
    conn.close()


def test_scan_candidates_from_db_applies_cutoff(tmp_path):
    """Test scan_candidates_from_db applies cutoff timestamp."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")

    pycache_dir = tmp_path / "mybucket" / "code" / "__pycache__"
    pycache_dir.mkdir(parents=True)

    conn.execute(
        "INSERT INTO files (bucket, key, size) VALUES (?, ?, ?)",
        ("mybucket", "code/__pycache__/module.pyc", 1024),
    )
    conn.commit()

    category = Category("pycache", "Python cache", _pycache_matcher, prune=True)

    cutoff_ts = time.time() - 1000

    result = scan_candidates_from_db(
        conn,
        tmp_path,
        [category],
        cutoff_ts=cutoff_ts,
        min_size_bytes=None,
        total_files=1,
    )

    assert_equal(len(result), 0)
    conn.close()


def test_scan_candidates_from_db_skips_invalid_paths(tmp_path):
    """Test scan_candidates_from_db skips files with invalid paths."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")

    conn.execute(
        "INSERT INTO files (bucket, key, size) VALUES (?, ?, ?)",
        ("mybucket", "../../../etc/passwd", 1024),
    )
    conn.commit()

    category = Category("any", "Any category", _dummy_matcher, prune=True)

    result = scan_candidates_from_db(
        conn,
        tmp_path,
        [category],
        cutoff_ts=None,
        min_size_bytes=None,
        total_files=1,
    )

    assert_equal(len(result), 0)
    conn.close()


def test_scan_candidates_from_db_multiple_files_same_dir(tmp_path):
    """Test scan_candidates_from_db accumulates sizes for same directory."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")

    pycache_dir = tmp_path / "mybucket" / "code" / "__pycache__"
    pycache_dir.mkdir(parents=True)

    conn.execute(
        "INSERT INTO files (bucket, key, size) VALUES (?, ?, ?)",
        ("mybucket", "code/__pycache__/module1.pyc", 1024),
    )
    conn.execute(
        "INSERT INTO files (bucket, key, size) VALUES (?, ?, ?)",
        ("mybucket", "code/__pycache__/module2.pyc", 2048),
    )
    conn.commit()

    category = Category("pycache", "Python cache", _pycache_matcher, prune=True)

    result = scan_candidates_from_db(
        conn,
        tmp_path,
        [category],
        cutoff_ts=None,
        min_size_bytes=None,
        total_files=2,
    )

    assert_equal(len(result), 1)
    assert_equal(result[0].size_bytes, 3072)
    conn.close()


def test_scan_candidates_from_db_multiple_categories(tmp_path):
    """Test scan_candidates_from_db with multiple categories."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")

    pycache_dir = tmp_path / "mybucket" / "__pycache__"
    pycache_dir.mkdir(parents=True)

    cache_dir = tmp_path / "mybucket" / ".cache"
    cache_dir.mkdir(parents=True)

    conn.execute(
        "INSERT INTO files (bucket, key, size) VALUES (?, ?, ?)",
        ("mybucket", "__pycache__/module.pyc", 1024),
    )
    conn.execute(
        "INSERT INTO files (bucket, key, size) VALUES (?, ?, ?)",
        ("mybucket", ".cache/data.bin", 2048),
    )
    conn.commit()

    def cache_matcher(path: Path, is_dir: bool) -> bool:
        return is_dir and path.name == ".cache"

    cat1 = Category("pycache", "Python cache", _pycache_matcher, prune=True)
    cat2 = Category("cache", "Generic cache", cache_matcher, prune=True)

    result = scan_candidates_from_db(
        conn,
        tmp_path,
        [cat1, cat2],
        cutoff_ts=None,
        min_size_bytes=None,
        total_files=2,
    )

    assert_equal(len(result), 2)
    paths = [c.path for c in result]
    assert pycache_dir.resolve() in paths
    assert cache_dir.resolve() in paths
    conn.close()


def test_scan_candidates_from_db_raises_on_null_sizes(tmp_path):
    """Test scan_candidates_from_db raises CandidateLoadError for NULL sizes."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE files (bucket TEXT, key TEXT, size INTEGER)")

    pycache_dir = tmp_path / "mybucket" / "__pycache__"
    pycache_dir.mkdir(parents=True)

    conn.execute(
        "INSERT INTO files (bucket, key, size) VALUES (?, ?, ?)",
        ("mybucket", "__pycache__/module.pyc", None),
    )
    conn.commit()

    category = Category("pycache", "Python cache", _pycache_matcher, prune=True)

    with pytest.raises(CandidateLoadError) as exc_info:
        scan_candidates_from_db(
            conn,
            tmp_path,
            [category],
            cutoff_ts=None,
            min_size_bytes=None,
            total_files=1,
        )

    assert "NULL size in database" in str(exc_info.value)
    conn.close()
