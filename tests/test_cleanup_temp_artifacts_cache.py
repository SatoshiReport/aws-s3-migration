"""Tests for cleanup_temp_artifacts/cache.py module."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cleanup_temp_artifacts.cache import (  # pylint: disable=no-name-in-module
    CACHE_VERSION,
    CacheReadError,
    CacheValidationError,
    build_cache_key,
    build_scan_params,
    cache_is_valid,
    load_cache,
    write_cache,
)
from cleanup_temp_artifacts.categories import Category  # pylint: disable=no-name-in-module
from cleanup_temp_artifacts.core_scanner import Candidate  # pylint: disable=no-name-in-module
from tests.assertions import assert_equal
from tests.conftest_test_values import TEST_MAX_ROWID


def _dummy_matcher(path: Path, is_dir: bool) -> bool:  # pylint: disable=unused-argument
    return True


def test_build_scan_params():
    """Test build_scan_params creates correct parameter dict."""
    category1 = Category("cat1", "desc1", _dummy_matcher, prune=True)
    category2 = Category("cat2", "desc2", _dummy_matcher, prune=True)

    params = build_scan_params(
        categories=[category1, category2],
        older_than=30,
        min_size_bytes=1024,
    )

    assert_equal(params["categories"], ["cat1", "cat2"])
    assert_equal(params["older_than"], 30)
    assert_equal(params["min_size_bytes"], 1024)


def test_build_scan_params_with_none():
    """Test build_scan_params with None values."""
    category = Category("cat1", "desc1", _dummy_matcher, prune=True)

    params = build_scan_params(
        categories=[category],
        older_than=None,
        min_size_bytes=None,
    )

    assert_equal(params["categories"], ["cat1"])
    assert params["older_than"] is None
    assert params["min_size_bytes"] is None


def test_build_cache_key():
    """Test build_cache_key generates consistent hash."""
    scan_params = {"categories": ["cat1"], "older_than": 30}

    key1 = build_cache_key(Path("/base"), Path("/db"), scan_params)
    key2 = build_cache_key(Path("/base"), Path("/db"), scan_params)

    assert_equal(key1, key2)
    assert len(key1) == 64  # SHA256 produces 64 hex characters


def test_build_cache_key_different_inputs():
    """Test build_cache_key produces different keys for different inputs."""
    scan_params = {"categories": ["cat1"]}

    key1 = build_cache_key(Path("/base1"), Path("/db"), scan_params)
    key2 = build_cache_key(Path("/base2"), Path("/db"), scan_params)

    assert key1 != key2


def test_load_cache_missing_file(tmp_path):
    """Test load_cache raises CacheReadError for missing cache file."""
    cache_file = tmp_path / "missing.json"
    category = Category("cat1", "desc1", _dummy_matcher, prune=True)

    with pytest.raises(CacheReadError):
        load_cache(cache_file, {"categories": ["cat1"]}, {"cat1": category})


def test_load_cache_invalid_json(tmp_path):
    """Test load_cache raises CacheReadError for invalid JSON."""
    cache_file = tmp_path / "invalid.json"
    cache_file.write_text("invalid json {")
    category = Category("cat1", "desc1", _dummy_matcher, prune=True)

    with pytest.raises(CacheReadError):
        load_cache(cache_file, {"categories": ["cat1"]}, {"cat1": category})


def test_load_cache_wrong_version(tmp_path):
    """Test load_cache raises CacheValidationError for wrong version."""
    cache_file = tmp_path / "cache.json"
    payload = {
        "version": CACHE_VERSION - 1,
        "scan_params": {"categories": ["cat1"]},
        "candidates": [],
    }
    cache_file.write_text(json.dumps(payload))
    category = Category("cat1", "desc1", _dummy_matcher, prune=True)

    with pytest.raises(CacheValidationError):
        load_cache(cache_file, {"categories": ["cat1"]}, {"cat1": category})


def test_load_cache_wrong_scan_params(tmp_path):
    """Test load_cache raises CacheValidationError for mismatched scan params."""
    cache_file = tmp_path / "cache.json"
    payload = {
        "version": CACHE_VERSION,
        "scan_params": {"categories": ["cat2"]},
        "candidates": [],
    }
    cache_file.write_text(json.dumps(payload))
    category = Category("cat1", "desc1", _dummy_matcher, prune=True)

    with pytest.raises(CacheValidationError):
        load_cache(cache_file, {"categories": ["cat1"]}, {"cat1": category})


def test_load_cache_valid(tmp_path):
    """Test load_cache with valid cache."""
    cache_file = tmp_path / "cache.json"
    category = Category("cat1", "desc1", _dummy_matcher, prune=True)
    scan_params = {"categories": ["cat1"]}

    payload = {
        "version": CACHE_VERSION,
        "scan_params": scan_params,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rowcount": 100,
        "max_rowid": 500,
        "db_mtime_ns": 123456789,
        "candidates": [
            {
                "path": "/tmp/test",
                "category": "cat1",
                "size_bytes": 1024,
                "mtime": 1234567890,
            }
        ],
    }
    cache_file.write_text(json.dumps(payload))

    result = load_cache(cache_file, scan_params, {"cat1": category})

    assert result is not None
    candidates, metadata = result
    assert len(candidates) == 1
    assert_equal(candidates[0].path, Path("/tmp/test"))
    assert_equal(candidates[0].category.name, "cat1")
    assert_equal(candidates[0].size_bytes, 1024)
    assert_equal(metadata["rowcount"], 100)


def test_load_cache_unknown_category(tmp_path):
    """Test load_cache raises CacheValidationError for unknown category."""
    cache_file = tmp_path / "cache.json"
    category = Category("cat1", "desc1", _dummy_matcher, prune=True)
    scan_params = {"categories": ["cat1"]}

    payload = {
        "version": CACHE_VERSION,
        "scan_params": scan_params,
        "candidates": [
            {
                "path": "/tmp/test",
                "category": "unknown",
                "size_bytes": 1024,
            }
        ],
    }
    cache_file.write_text(json.dumps(payload))

    with pytest.raises(CacheValidationError):
        load_cache(cache_file, scan_params, {"cat1": category})


def test_write_cache(tmp_path):
    """Test write_cache creates valid cache file."""
    cache_file = tmp_path / "cache" / "test.json"
    category = Category("cat1", "desc1", _dummy_matcher, prune=True)
    candidate = Candidate(path=Path("/tmp/test"), category=category, size_bytes=1024, mtime=12345)

    mock_db_info = MagicMock()
    mock_db_info.db_path = Path("/tmp/test.db")
    mock_db_info.total_files = 100
    mock_db_info.max_rowid = TEST_MAX_ROWID
    mock_db_info.db_stat.st_mtime_ns = 123456789

    scan_params = {"categories": ["cat1"]}

    write_cache(
        cache_file,
        [candidate],
        scan_params=scan_params,
        base_path=Path("/base"),
        db_info=mock_db_info,
    )

    assert cache_file.exists()
    payload = json.loads(cache_file.read_text())

    assert_equal(payload["version"], CACHE_VERSION)
    assert_equal(payload["rowcount"], 100)
    assert_equal(payload["max_rowid"], 500)
    assert len(payload["candidates"]) == 1
    assert_equal(payload["candidates"][0]["path"], "/tmp/test")
    assert_equal(payload["candidates"][0]["category"], "cat1")


def test_cache_is_valid_true():
    """Test cache_is_valid returns True for valid cache."""
    generated_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    metadata = {
        "generated_at": generated_at.isoformat(),
        "rowcount": 100,
        "max_rowid": 500,
        "db_mtime_ns": 123456789,
    }

    result = cache_is_valid(
        metadata,
        ttl_seconds=60,
        rowcount=100,
        max_rowid=500,
        db_mtime_ns=123456789,
    )

    assert result is True


def test_cache_is_valid_expired():
    """Test cache_is_valid returns False for expired cache."""
    generated_at = datetime.now(timezone.utc) - timedelta(seconds=70)
    metadata = {
        "generated_at": generated_at.isoformat(),
        "rowcount": 100,
        "max_rowid": 500,
        "db_mtime_ns": 123456789,
    }

    result = cache_is_valid(
        metadata,
        ttl_seconds=60,
        rowcount=100,
        max_rowid=500,
        db_mtime_ns=123456789,
    )

    assert result is False


def test_cache_is_valid_db_changed():
    """Test cache_is_valid returns False when DB has changed."""
    generated_at = datetime.now(timezone.utc)
    metadata = {
        "generated_at": generated_at.isoformat(),
        "rowcount": 100,
        "max_rowid": 500,
        "db_mtime_ns": 123456789,
    }

    result = cache_is_valid(
        metadata,
        ttl_seconds=60,
        rowcount=101,  # Different row count
        max_rowid=500,
        db_mtime_ns=123456789,
    )

    assert result is False


def test_cache_is_valid_no_ttl():
    """Test cache_is_valid with TTL disabled (0)."""
    metadata = {
        "generated_at": "2020-01-01T00:00:00+00:00",
        "rowcount": 100,
        "max_rowid": 500,
        "db_mtime_ns": 123456789,
    }

    result = cache_is_valid(
        metadata,
        ttl_seconds=0,
        rowcount=100,
        max_rowid=500,
        db_mtime_ns=123456789,
    )

    assert result is True


def test_cache_is_valid_invalid_timestamp_raises():
    """Test cache_is_valid raises CacheValidationError with invalid timestamp."""
    metadata = {
        "generated_at": "invalid timestamp",
        "rowcount": 100,
        "max_rowid": 500,
        "db_mtime_ns": 123456789,
    }

    with pytest.raises(CacheValidationError) as exc_info:
        cache_is_valid(
            metadata,
            ttl_seconds=60,
            rowcount=100,
            max_rowid=500,
            db_mtime_ns=123456789,
        )

    assert "malformed" in str(exc_info.value)
    assert "generated_at" in str(exc_info.value)
