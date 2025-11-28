"""Tests for cleanup_temp_artifacts/core_scanner.py data classes and utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from cleanup_temp_artifacts.categories import Category  # pylint: disable=no-name-in-module
from cleanup_temp_artifacts.core_scanner import (  # pylint: disable=no-name-in-module
    Candidate,
    CandidateLoadError,
    CandidateLoadResult,
    _filter_candidates_by_size,
    iter_relevant_dirs,
)
from migration_utils import ProgressTracker
from tests.assertions import assert_equal


def _dummy_matcher(path: Path, is_dir: bool) -> bool:  # pylint: disable=unused-argument
    """Dummy matcher that always returns True."""
    return True


def test_candidate_dataclass():
    """Test Candidate dataclass creation."""
    category = Category("test-cat", "Test category", _dummy_matcher)
    candidate = Candidate(
        path=Path("/tmp/test"),
        category=category,
        size_bytes=1024,
        mtime=1234567890.0,
    )

    assert_equal(candidate.path, Path("/tmp/test"))
    assert candidate.category is category
    assert_equal(candidate.size_bytes, 1024)
    assert_equal(candidate.mtime, 1234567890.0)


def test_candidate_iso_mtime():
    """Test Candidate.iso_mtime property."""
    category = Category("test-cat", "Test category", _dummy_matcher)
    mtime = 1234567890.0
    candidate = Candidate(
        path=Path("/tmp/test"),
        category=category,
        size_bytes=1024,
        mtime=mtime,
    )

    iso_time = candidate.iso_mtime
    expected = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    assert_equal(iso_time, expected)
    assert "T" in iso_time
    assert "+00:00" in iso_time or "Z" in iso_time


def test_candidate_load_result_dataclass():
    """Test CandidateLoadResult dataclass creation."""
    category = Category("test-cat", "Test category", _dummy_matcher)
    candidate = Candidate(Path("/tmp"), category, 100, 123.0)

    result = CandidateLoadResult(
        candidates=[candidate],
        cache_path=Path("/cache.json"),
        cache_used=True,
        total_files=50,
        max_rowid=100,
    )

    assert len(result.candidates) == 1
    assert_equal(result.cache_path, Path("/cache.json"))
    assert result.cache_used is True
    assert_equal(result.total_files, 50)
    assert_equal(result.max_rowid, 100)


def test_candidate_load_error():
    """Test CandidateLoadError exception."""
    error = CandidateLoadError("Database query failed")
    assert isinstance(error, RuntimeError)
    assert_equal(str(error), "Database query failed")


def test_iter_relevant_dirs_basic(tmp_path):
    """Test iter_relevant_dirs yields ancestor directories."""
    base = tmp_path / "base"
    base.mkdir()

    file_path = base / "dir1" / "dir2" / "file.txt"
    dirs = list(iter_relevant_dirs(file_path, base))

    assert_equal(len(dirs), 2)
    assert Path(base / "dir1" / "dir2") in dirs
    assert Path(base / "dir1") in dirs


def test_iter_relevant_dirs_excludes_base(tmp_path):
    """Test iter_relevant_dirs excludes base_path itself."""
    base = tmp_path / "base"
    base.mkdir()

    file_path = base / "file.txt"
    dirs = list(iter_relevant_dirs(file_path, base))

    assert_equal(len(dirs), 0)
    assert base not in dirs


def test_iter_relevant_dirs_outside_base(tmp_path):
    """Test iter_relevant_dirs raises PathOutsideBaseError for file outside base_path."""
    from cleanup_temp_artifacts.core_scanner import PathOutsideBaseError

    base = tmp_path / "base"
    base.mkdir()

    file_path = tmp_path / "other" / "file.txt"
    with pytest.raises(PathOutsideBaseError):
        list(iter_relevant_dirs(file_path, base))


def test_iter_relevant_dirs_deep_hierarchy(tmp_path):
    """Test iter_relevant_dirs with deep directory hierarchy."""
    base = tmp_path / "base"
    base.mkdir()

    file_path = base / "a" / "b" / "c" / "d" / "file.txt"
    dirs = list(iter_relevant_dirs(file_path, base))

    assert_equal(len(dirs), 4)
    assert Path(base / "a" / "b" / "c" / "d") in dirs
    assert Path(base / "a" / "b" / "c") in dirs
    assert Path(base / "a" / "b") in dirs
    assert Path(base / "a") in dirs


def test_iter_relevant_dirs_traversal_to_parent_of_base(tmp_path):
    """Test iter_relevant_dirs stops at base_path even when continuing parent traversal."""
    base = tmp_path / "base"
    base.mkdir()
    (base / "subdir").mkdir()

    file_path = base / "subdir" / "file.txt"
    dirs = list(iter_relevant_dirs(file_path, base))

    assert_equal(len(dirs), 1)
    assert Path(base / "subdir") in dirs
    assert base not in dirs
    assert tmp_path not in dirs


def test_filter_candidates_by_size():
    """Test _filter_candidates_by_size with minimum size."""
    category = Category("cat", "Category", _dummy_matcher)

    candidates = {
        Path("/tmp/a"): Candidate(Path("/tmp/a"), category, 100, 123.0),
        Path("/tmp/b"): Candidate(Path("/tmp/b"), category, 1000, 124.0),
        Path("/tmp/c"): Candidate(Path("/tmp/c"), category, 5000, 125.0),
    }

    result = _filter_candidates_by_size(candidates, min_size_bytes=500)

    assert_equal(len(result), 2)
    paths = [c.path for c in result]
    assert Path("/tmp/b") in paths
    assert Path("/tmp/c") in paths


def test_filter_candidates_by_size_no_minimum():
    """Test _filter_candidates_by_size with no minimum."""
    category = Category("cat", "Category", _dummy_matcher)

    candidates = {
        Path("/tmp/a"): Candidate(Path("/tmp/a"), category, 100, 123.0),
        Path("/tmp/b"): Candidate(Path("/tmp/b"), category, 1000, 124.0),
    }

    result = _filter_candidates_by_size(candidates, min_size_bytes=None)

    assert_equal(len(result), 2)


def test_filter_candidates_by_size_raises_on_none_sizes():
    """Test _filter_candidates_by_size raises MissingSizeError for None size values."""
    from cleanup_temp_artifacts.core_scanner import (
        MissingSizeError,  # pylint: disable=no-name-in-module
    )

    category = Category("cat", "Category", _dummy_matcher)

    candidates = {
        Path("/tmp/a"): Candidate(Path("/tmp/a"), category, None, 123.0),
        Path("/tmp/b"): Candidate(Path("/tmp/b"), category, 1000, 124.0),
    }

    with pytest.raises(MissingSizeError) as exc_info:
        _filter_candidates_by_size(candidates, min_size_bytes=500)

    assert "/tmp/a" in str(exc_info.value)
    assert "no size information" in str(exc_info.value)


def test_progress_tracker_initialization():
    """Test ProgressTracker initialization."""
    tracker = ProgressTracker(total=100, label="Testing")

    assert_equal(tracker.total, 100)
    assert_equal(tracker.label, "Testing")
    assert tracker.start > 0
    assert tracker.last_update > 0  # Uses last_update instead of last_print


def test_progress_tracker_finish(capsys):
    """Test ProgressTracker finish method."""
    tracker = ProgressTracker(total=100, label="Testing")

    tracker.finish()
    captured = capsys.readouterr()
    assert "\n" in captured.out
