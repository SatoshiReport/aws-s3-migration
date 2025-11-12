"""Tests for find_compressible/reporting.py module."""

from __future__ import annotations

from collections import Counter
from unittest.mock import patch

from find_compressible.analysis import CandidateFile
from find_compressible.reporting import (
    CompressionStats,
    _process_single_compression,
    _report_single_candidate,
    print_compression_summary,
    print_scan_summary,
    report_and_compress_candidates,
)
from tests.assertions import assert_equal


def test_compression_stats_defaults():
    """Test CompressionStats default values."""
    stats = CompressionStats()
    assert_equal(stats.compressed_files, 0)
    assert_equal(stats.compression_failures, 0)
    assert_equal(stats.total_original_space, 0)
    assert_equal(stats.total_compressed_space, 0)


def test_process_single_compression_success(tmp_path):
    """Test _process_single_compression with successful compression."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    candidate = CandidateFile(
        bucket="test-bucket",
        key="test.txt",
        size_bytes=test_file.stat().st_size,
        path=test_file,
    )

    compressed_file = tmp_path / "test.txt.xz"
    compressed_file.write_bytes(b"compressed")

    with (
        patch("find_compressible.reporting.compress_with_xz", return_value=compressed_file),
        patch("find_compressible.reporting.verify_compressed_file"),
    ):
        success, compressed_size, error = _process_single_compression(candidate)

    assert success is True
    assert compressed_size > 0
    assert error is None


def test_process_single_compression_failure(tmp_path):
    """Test _process_single_compression with compression failure."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    candidate = CandidateFile(
        bucket="test-bucket",
        key="test.txt",
        size_bytes=test_file.stat().st_size,
        path=test_file,
    )

    with patch(
        "find_compressible.reporting.compress_with_xz",
        side_effect=RuntimeError("Compression failed"),
    ):
        success, compressed_size, error = _process_single_compression(candidate)

    assert success is False
    assert compressed_size == 0
    assert error is not None


def test_report_single_candidate_without_compression(tmp_path, capsys):
    """Test _report_single_candidate without compression."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    candidate = CandidateFile(
        bucket="test-bucket",
        key="test.txt",
        size_bytes=1024,
        path=test_file,
    )

    stats: Counter = Counter()
    compression_stats = CompressionStats()
    reported_extensions: set[str] = set()

    _report_single_candidate(
        candidate,
        idx=1,
        index_width=2,
        compress_enabled=False,
        compression_stats=compression_stats,
        stats=stats,
        reported_extensions=reported_extensions,
    )

    captured = capsys.readouterr().out
    assert "test.txt" in captured
    assert "test-bucket" in captured
    assert "txt" in reported_extensions


def test_report_single_candidate_no_extension(tmp_path):
    """Test _report_single_candidate with file without extension."""
    test_file = tmp_path / "README"
    test_file.write_text("test content")
    candidate = CandidateFile(
        bucket="test-bucket",
        key="README",
        size_bytes=1024,
        path=test_file,
    )

    stats: Counter = Counter()
    compression_stats = CompressionStats()
    reported_extensions: set[str] = set()

    _report_single_candidate(
        candidate,
        idx=1,
        index_width=2,
        compress_enabled=False,
        compression_stats=compression_stats,
        stats=stats,
        reported_extensions=reported_extensions,
    )

    assert stats["skipped_no_extension"] == 1
    assert len(reported_extensions) == 0


def test_report_single_candidate_with_compression_success(tmp_path, capsys):
    """Test _report_single_candidate with successful compression."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    original_size = test_file.stat().st_size
    candidate = CandidateFile(
        bucket="test-bucket",
        key="test.txt",
        size_bytes=original_size,
        path=test_file,
    )

    compressed_file = tmp_path / "test.txt.xz"
    compressed_file.write_bytes(b"compressed")

    stats: Counter = Counter()
    compression_stats = CompressionStats()
    reported_extensions: set[str] = set()

    with (
        patch("find_compressible.reporting.compress_with_xz", return_value=compressed_file),
        patch("find_compressible.reporting.verify_compressed_file"),
    ):
        _report_single_candidate(
            candidate,
            idx=1,
            index_width=2,
            compress_enabled=True,
            compression_stats=compression_stats,
            stats=stats,
            reported_extensions=reported_extensions,
        )

    assert compression_stats.compressed_files == 1
    assert compression_stats.total_original_space == original_size
    captured = capsys.readouterr().out
    assert "Compressed to" in captured


def test_report_single_candidate_with_compression_failure(tmp_path, capsys):
    """Test _report_single_candidate with compression failure."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    candidate = CandidateFile(
        bucket="test-bucket",
        key="test.txt",
        size_bytes=test_file.stat().st_size,
        path=test_file,
    )

    stats: Counter = Counter()
    compression_stats = CompressionStats()
    reported_extensions: set[str] = set()

    with patch("find_compressible.reporting.compress_with_xz", side_effect=RuntimeError("Failed")):
        _report_single_candidate(
            candidate,
            idx=1,
            index_width=2,
            compress_enabled=True,
            compression_stats=compression_stats,
            stats=stats,
            reported_extensions=reported_extensions,
        )

    assert compression_stats.compression_failures == 1
    captured = capsys.readouterr().err
    assert "Compression failed" in captured


def test_report_and_compress_candidates_empty():
    """Test report_and_compress_candidates with empty list."""
    stats: Counter = Counter()
    result = report_and_compress_candidates([], compress_enabled=False, stats=stats)
    compressed_files, failures, orig_space, comp_space, extensions = result
    assert compressed_files == 0
    assert failures == 0
    assert orig_space == 0
    assert comp_space == 0
    assert len(extensions) == 0


def test_report_and_compress_candidates_without_compression(tmp_path):
    """Test report_and_compress_candidates without compression."""
    test_file1 = tmp_path / "test1.txt"
    test_file1.write_text("content1")
    test_file2 = tmp_path / "test2.log"
    test_file2.write_text("content2")

    candidates = [
        CandidateFile("bucket1", "test1.txt", test_file1.stat().st_size, test_file1),
        CandidateFile("bucket2", "test2.log", test_file2.stat().st_size, test_file2),
    ]

    stats: Counter = Counter()
    result = report_and_compress_candidates(candidates, compress_enabled=False, stats=stats)
    compressed_files, failures, _orig_space, _comp_space, extensions = result

    assert compressed_files == 0
    assert failures == 0
    assert "txt" in extensions
    assert "log" in extensions


def test_print_scan_summary(tmp_path, capsys):
    """Test print_scan_summary output."""
    base_path = tmp_path / "base"
    db_path = tmp_path / "test.db"
    stats: Counter = Counter()
    stats["rows_examined"] = 100
    stats["candidates_found"] = 10
    stats["missing_local_files"] = 5
    stats["skipped_image"] = 20
    stats["skipped_video"] = 15
    stats["skipped_compressed"] = 10
    stats["skipped_already_xz"] = 2
    stats["skipped_invalid_path"] = 1
    stats["skipped_non_file"] = 3
    stats["skipped_now_below_threshold"] = 4
    stats["skipped_numeric_extension"] = 6
    stats["skipped_no_extension"] = 7

    reported_extensions = {"txt", "log", "csv"}

    print_scan_summary(
        base_path,
        db_path,
        stats,
        total_reported=10,
        total_bytes=1024 * 1024 * 1024,
        reported_extensions=reported_extensions,
    )

    captured = capsys.readouterr().out
    assert "Scan summary" in captured
    assert "100" in captured  # rows examined
    assert "10" in captured  # candidates
    assert "csv, log, txt" in captured  # sorted extensions


def test_print_scan_summary_no_extensions(tmp_path, capsys):
    """Test print_scan_summary with no extensions."""
    base_path = tmp_path / "base"
    db_path = tmp_path / "test.db"
    stats: Counter = Counter()

    print_scan_summary(
        base_path,
        db_path,
        stats,
        total_reported=0,
        total_bytes=0,
        reported_extensions=set(),
    )

    captured = capsys.readouterr().out
    assert "(none)" in captured


def test_print_compression_summary(capsys):
    """Test print_compression_summary output."""
    print_compression_summary(
        compressed_files=10,
        total_original_space=1024 * 1024 * 1024,  # 1 GiB
        total_compressed_space=512 * 1024 * 1024,  # 512 MiB
        compression_failures=2,
    )

    captured = capsys.readouterr().out
    assert "Compression summary" in captured
    assert "10" in captured  # files compressed
    assert "50.00%" in captured  # reduction percentage
    assert "2" in captured  # failures


def test_print_compression_summary_no_original_space(capsys):
    """Test print_compression_summary with zero original space."""
    print_compression_summary(
        compressed_files=0,
        total_original_space=0,
        total_compressed_space=0,
        compression_failures=0,
    )

    captured = capsys.readouterr().out
    assert "Compression summary" in captured
    assert "0.00%" in captured  # No division by zero
