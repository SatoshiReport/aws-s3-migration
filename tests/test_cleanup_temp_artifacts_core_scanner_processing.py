"""Tests for cleanup_temp_artifacts/core_scanner.py progress tracking and processing."""

from __future__ import annotations

import logging
import time
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from cleanup_temp_artifacts.categories import Category  # pylint: disable=no-name-in-module
from cleanup_temp_artifacts.core_scanner import (  # pylint: disable=no-name-in-module
    MatcherError,
    _process_parent_directory,
    match_category,
)
from migration_utils import ProgressTracker
from tests.assertions import assert_equal


def _dummy_matcher(path: Path, is_dir: bool) -> bool:  # pylint: disable=unused-argument
    """Dummy matcher that always returns True."""
    return True


def _never_matcher(path: Path, is_dir: bool) -> bool:  # pylint: disable=unused-argument
    """Dummy matcher that always returns False."""
    return False


def _pycache_matcher(path: Path, is_dir: bool) -> bool:
    """Match __pycache__ directories."""
    return is_dir and path.name == "__pycache__"


def test_progress_tracker_update(capsys):
    """Test ProgressTracker update method at completion."""
    # The update method only prints when interval has elapsed or at completion
    tracker = ProgressTracker(total=100, label="Testing", update_interval=0.5)

    # Force immediate print by reaching completion
    tracker.update(100)
    captured = capsys.readouterr()
    assert "Testing:" in captured.out
    assert "100" in captured.out


def test_progress_tracker_update_zero_total(capsys):
    """Test ProgressTracker with zero total at completion."""
    tracker = ProgressTracker(total=0, label="Testing", update_interval=0.5)

    # When total is 0, update at 0 triggers the completion condition
    tracker.update(0)
    captured = capsys.readouterr()
    assert "Testing:" in captured.out


def test_progress_tracker_update_rate_limiting():
    """Test ProgressTracker rate limits updates."""
    tracker = ProgressTracker(total=100, label="Testing", update_interval=0.5)

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        # First update at completion will print
        tracker.update(100)
        output_count = mock_stdout.getvalue().count("Testing:")
        assert_equal(output_count, 1)


def test_progress_tracker_update_completion(capsys):
    """Test ProgressTracker always updates at completion."""
    tracker = ProgressTracker(total=100, label="Testing")

    tracker.update(100)
    captured = capsys.readouterr()
    assert "Testing:" in captured.out
    assert "100" in captured.out
    assert "100.0%" in captured.out


def test_match_category_first_match():
    """Test match_category returns first matching category."""
    cat1 = Category("cat1", "Category 1", _never_matcher, prune=True)
    cat2 = Category("cat2", "Category 2", _pycache_matcher, prune=True)
    cat3 = Category("cat3", "Category 3", _dummy_matcher, prune=True)

    categories = [cat1, cat2, cat3]
    result = match_category(Path("/tmp/__pycache__"), True, categories)

    assert result is cat2


def test_match_category_no_match():
    """Test match_category returns None when no category matches."""
    cat1 = Category("cat1", "Category 1", _never_matcher, prune=True)
    cat2 = Category("cat2", "Category 2", _never_matcher, prune=True)

    categories = [cat1, cat2]
    result = match_category(Path("/tmp/other"), True, categories)

    assert result is None


def test_match_category_exception_handling():
    """Test match_category raises MatcherError on matcher exceptions."""

    def failing_matcher(path: Path, is_dir: bool) -> bool:
        raise ValueError("Matcher failed")

    cat1 = Category("cat1", "Category 1", failing_matcher, prune=True)
    cat2 = Category("cat2", "Category 2", _dummy_matcher, prune=True)

    categories = [cat1, cat2]

    with pytest.raises(MatcherError) as exc_info:
        match_category(Path("/tmp/test"), True, categories)

    assert "Matcher cat1 failed" in str(exc_info.value)
    assert "Matcher failed" in str(exc_info.value)


def test_match_category_file_vs_directory():
    """Test match_category respects is_dir parameter."""
    categories = [Category("cat1", "Category 1", _pycache_matcher, prune=True)]

    result_dir = match_category(Path("/tmp/__pycache__"), True, categories)
    result_file = match_category(Path("/tmp/__pycache__"), False, categories)

    assert result_dir is not None
    assert result_file is None


def test_process_parent_directory_new_candidate(tmp_path):
    """Test _process_parent_directory adds new candidate."""
    parent = tmp_path / "__pycache__"
    parent.mkdir()

    candidates = {}
    non_matching = set()
    category = Category("pycache", "Python cache", _pycache_matcher, prune=True)

    _process_parent_directory(
        parent,
        file_size=1024,
        candidates=candidates,
        non_matching=non_matching,
        categories=[category],
        cutoff_ts=None,
    )

    assert len(candidates) == 1
    canonical = parent.resolve()
    assert canonical in candidates
    assert_equal(candidates[canonical].size_bytes, 1024)
    assert_equal(candidates[canonical].category, category)


def test_process_parent_directory_accumulate_size(tmp_path):
    """Test _process_parent_directory accumulates file sizes."""
    parent = tmp_path / "__pycache__"
    parent.mkdir()

    candidates = {}
    non_matching = set()
    category = Category("pycache", "Python cache", _pycache_matcher, prune=True)

    _process_parent_directory(
        parent,
        file_size=1024,
        candidates=candidates,
        non_matching=non_matching,
        categories=[category],
        cutoff_ts=None,
    )

    _process_parent_directory(
        parent,
        file_size=512,
        candidates=candidates,
        non_matching=non_matching,
        categories=[category],
        cutoff_ts=None,
    )

    canonical = parent.resolve()
    assert_equal(candidates[canonical].size_bytes, 1536)


def test_process_parent_directory_no_category_match(tmp_path):
    """Test _process_parent_directory with no matching category."""
    parent = tmp_path / "regular"
    parent.mkdir()

    candidates = {}
    non_matching = set()
    category = Category("pycache", "Python cache", _pycache_matcher, prune=True)

    _process_parent_directory(
        parent,
        file_size=1024,
        candidates=candidates,
        non_matching=non_matching,
        categories=[category],
        cutoff_ts=None,
    )

    assert len(candidates) == 0
    assert parent.resolve() in non_matching


def test_process_parent_directory_cutoff_time(tmp_path):
    """Test _process_parent_directory respects cutoff timestamp."""
    parent = tmp_path / "__pycache__"
    parent.mkdir()

    candidates = {}
    non_matching = set()
    category = Category("pycache", "Python cache", _pycache_matcher, prune=True)

    cutoff_ts = time.time() - 1000

    _process_parent_directory(
        parent,
        file_size=1024,
        candidates=candidates,
        non_matching=non_matching,
        categories=[category],
        cutoff_ts=cutoff_ts,
    )

    assert len(candidates) == 0
    assert parent.resolve() in non_matching


def test_process_parent_directory_skips_non_matching_cache(tmp_path):
    """Test _process_parent_directory skips cached non-matching paths."""
    parent = tmp_path / "regular"
    parent.mkdir()

    candidates = {}
    non_matching = {parent.resolve()}
    category = Category("any", "Any category", _dummy_matcher, prune=True)

    _process_parent_directory(
        parent,
        file_size=1024,
        candidates=candidates,
        non_matching=non_matching,
        categories=[category],
        cutoff_ts=None,
    )

    assert len(candidates) == 0


def test_process_parent_directory_stat_error(tmp_path, caplog):
    """Test _process_parent_directory handles stat errors."""
    parent = tmp_path / "nonexistent"

    candidates = {}
    non_matching = set()
    category = Category("any", "Any category", _dummy_matcher, prune=True)

    with caplog.at_level(logging.WARNING):
        _process_parent_directory(
            parent,
            file_size=1024,
            candidates=candidates,
            non_matching=non_matching,
            categories=[category],
            cutoff_ts=None,
        )

    assert len(candidates) == 0
    assert parent.resolve() in non_matching
    assert len(caplog.records) == 1
    assert "Unable to stat" in caplog.text


def test_process_parent_directory_resolve_error():
    """Test _process_parent_directory handles resolve errors."""
    candidates = {}
    non_matching = set()
    category = Category("any", "Any category", _dummy_matcher, prune=True)

    with patch.object(Path, "resolve", side_effect=OSError("Resolve failed")):
        parent = Path("/tmp/test")
        _process_parent_directory(
            parent,
            file_size=1024,
            candidates=candidates,
            non_matching=non_matching,
            categories=[category],
            cutoff_ts=None,
        )

    assert len(candidates) == 0
