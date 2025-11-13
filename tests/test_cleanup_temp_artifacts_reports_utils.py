"""Tests for cleanup_temp_artifacts/reports.py utility functions."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from cleanup_temp_artifacts.categories import Category
from cleanup_temp_artifacts.core_scanner import Candidate
from cleanup_temp_artifacts.reports import (
    BYTES_PER_GIB,
    BYTES_PER_KIB,
    BYTES_PER_MIB,
    BYTES_PER_TIB,
    order_candidates,
    parse_size,
    print_candidates_report,
    write_reports,
)
from tests.assertions import assert_equal


def make_candidate(
    path: str | Path,
    category_name: str = "test-category",
    size_bytes: int | None = 1024,
    mtime: float = 1234567890.0,
) -> Candidate:
    """Helper to create a Candidate for testing."""
    category = Category(
        name=category_name,
        description="Test category",
        matcher=lambda p, is_dir: True,
        prune=True,
    )
    return Candidate(
        path=Path(path),
        category=category,
        size_bytes=size_bytes,
        mtime=mtime,
    )


class TestParseSize:
    """Test parse_size function with various size units."""

    def test_parse_bytes_no_suffix(self):
        """Test parsing plain byte values without suffix."""
        assert_equal(parse_size("100"), 100)
        assert_equal(parse_size("0"), 0)
        assert_equal(parse_size("999"), 999)

    def test_parse_bytes_with_whitespace(self):
        """Test parsing with leading/trailing whitespace."""
        assert_equal(parse_size("  100  "), 100)
        assert_equal(parse_size("\t50\n"), 50)

    def test_parse_kilobytes(self):
        """Test parsing kilobyte values."""
        assert_equal(parse_size("1K"), BYTES_PER_KIB)
        assert_equal(parse_size("10K"), 10 * BYTES_PER_KIB)
        assert_equal(parse_size("0.5K"), int(0.5 * BYTES_PER_KIB))

    def test_parse_megabytes(self):
        """Test parsing megabyte values."""
        assert_equal(parse_size("1M"), BYTES_PER_MIB)
        assert_equal(parse_size("10M"), 10 * BYTES_PER_MIB)
        assert_equal(parse_size("2.5M"), int(2.5 * BYTES_PER_MIB))

    def test_parse_gigabytes(self):
        """Test parsing gigabyte values."""
        assert_equal(parse_size("1G"), BYTES_PER_GIB)
        assert_equal(parse_size("5G"), 5 * BYTES_PER_GIB)
        assert_equal(parse_size("1.5G"), int(1.5 * BYTES_PER_GIB))

    def test_parse_terabytes(self):
        """Test parsing terabyte values."""
        assert_equal(parse_size("1T"), BYTES_PER_TIB)
        assert_equal(parse_size("2T"), 2 * BYTES_PER_TIB)
        assert_equal(parse_size("0.1T"), int(0.1 * BYTES_PER_TIB))

    def test_parse_case_insensitive(self):
        """Test parsing is case-insensitive for suffixes."""
        assert_equal(parse_size("10k"), 10 * BYTES_PER_KIB)
        assert_equal(parse_size("10m"), 10 * BYTES_PER_MIB)
        assert_equal(parse_size("10g"), 10 * BYTES_PER_GIB)
        assert_equal(parse_size("10t"), 10 * BYTES_PER_TIB)

    def test_parse_fractional_values(self):
        """Test parsing fractional size values."""
        assert_equal(parse_size("0.5K"), 512)
        assert_equal(parse_size("1.5M"), int(1.5 * BYTES_PER_MIB))
        assert_equal(parse_size("2.25G"), int(2.25 * BYTES_PER_GIB))

    def test_parse_invalid_format(self):
        """Test parsing invalid format raises ValueError."""
        with pytest.raises(ValueError):
            parse_size("invalid")
        with pytest.raises(ValueError):
            parse_size("10X")
        with pytest.raises(ValueError):
            parse_size("")


class TestOrderCandidates:
    """Test order_candidates function for sorting."""

    def test_order_by_size_descending(self):
        """Test ordering candidates by size (largest first)."""
        candidates = [
            make_candidate("/tmp/small", "cat1", 100),
            make_candidate("/tmp/large", "cat1", 1000),
            make_candidate("/tmp/medium", "cat1", 500),
        ]

        result = order_candidates(candidates, order="size")

        assert_equal(result[0].size_bytes, 1000)
        assert_equal(result[1].size_bytes, 500)
        assert_equal(result[2].size_bytes, 100)

    def test_order_by_size_with_none(self):
        """Test ordering by size handles None values."""
        candidates = [
            make_candidate("/tmp/a", "cat1", 100),
            make_candidate("/tmp/b", "cat1", None),
            make_candidate("/tmp/c", "cat1", 500),
        ]

        result = order_candidates(candidates, order="size")

        assert_equal(result[0].size_bytes, 500)
        assert_equal(result[1].size_bytes, 100)
        assert_equal(result[2].size_bytes, None)

    def test_order_by_path(self):
        """Test ordering candidates by path alphabetically."""
        candidates = [
            make_candidate("/tmp/zebra", "cat1", 100),
            make_candidate("/tmp/alpha", "cat1", 200),
            make_candidate("/tmp/beta", "cat1", 300),
        ]

        result = order_candidates(candidates, order="path")

        assert_equal(str(result[0].path), "/tmp/alpha")
        assert_equal(str(result[1].path), "/tmp/beta")
        assert_equal(str(result[2].path), "/tmp/zebra")

    def test_order_default_is_path(self):
        """Test ordering defaults to path when order is not 'size'."""
        candidates = [
            make_candidate("/tmp/z", "cat1", 100),
            make_candidate("/tmp/a", "cat1", 200),
        ]

        result = order_candidates(candidates, order="unknown")

        assert_equal(str(result[0].path), "/tmp/a")
        assert_equal(str(result[1].path), "/tmp/z")


class TestWriteReports:
    """Test write_reports function for JSON and CSV output."""

    def test_write_json_report(self):
        """Test writing JSON report file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "report.json"
            candidates = [
                make_candidate("/tmp/test1", "cat1", 1024, 1234567890.0),
                make_candidate("/tmp/test2", "cat2", 2048, 1234567891.0),
            ]

            write_reports(candidates, json_path=json_path, csv_path=None)

            assert json_path.exists()
            data = json.loads(json_path.read_text())

            assert_equal(len(data), 2)
            assert_equal(data[0]["path"], "/tmp/test1")
            assert_equal(data[0]["category"], "cat1")
            assert_equal(data[0]["size_bytes"], 1024)
            assert_equal(data[0]["size_human"], "1.0KB")
            assert "mtime" in data[0]

    def test_write_csv_report(self):
        """Test writing CSV report file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "report.csv"
            candidates = [
                make_candidate("/tmp/test1", "cat1", 1024, 1234567890.0),
                make_candidate("/tmp/test2", "cat2", 2048, 1234567891.0),
            ]

            write_reports(candidates, json_path=None, csv_path=csv_path)

            assert csv_path.exists()
            with csv_path.open("r") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)

            assert_equal(len(rows), 2)
            assert_equal(rows[0]["path"], "/tmp/test1")
            assert_equal(rows[0]["category"], "cat1")
            assert_equal(rows[0]["size_bytes"], "1024")
            assert_equal(rows[0]["size_human"], "1.0KB")

    def test_write_both_reports(self):
        """Test writing both JSON and CSV reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "report.json"
            csv_path = Path(tmpdir) / "report.csv"
            candidates = [make_candidate("/tmp/test", "cat1", 1024)]

            write_reports(candidates, json_path=json_path, csv_path=csv_path)

            assert json_path.exists()
            assert csv_path.exists()

    def test_write_no_reports(self):
        """Test write_reports with no output paths."""
        candidates = [make_candidate("/tmp/test", "cat1", 1024)]
        write_reports(candidates, json_path=None, csv_path=None)

    def test_write_creates_parent_directories(self):
        """Test write_reports creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "subdir1" / "subdir2" / "report.json"
            csv_path = Path(tmpdir) / "other" / "report.csv"
            candidates = [make_candidate("/tmp/test", "cat1", 1024)]

            write_reports(candidates, json_path=json_path, csv_path=csv_path)

            assert json_path.exists()
            assert csv_path.exists()

    def test_write_empty_candidates(self):
        """Test write_reports with empty candidate list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "report.json"
            write_reports([], json_path=json_path, csv_path=None)

            assert json_path.exists()
            data = json.loads(json_path.read_text())
            assert_equal(data, [])

    def test_write_none_size_candidate(self):
        """Test write_reports handles None size correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "report.json"
            candidates = [make_candidate("/tmp/test", "cat1", None)]

            write_reports(candidates, json_path=json_path, csv_path=None)

            data = json.loads(json_path.read_text())
            assert data[0]["size_bytes"] is None
            assert_equal(data[0]["size_human"], "n/a")


class TestPrintCandidatesReportExtended:
    """Extended tests for print_candidates_report function."""

    def test_print_report_includes_summary(self):
        """Test report includes per-category summary."""
        candidates = [
            make_candidate("/tmp/a", "cat1", 1024),
            make_candidate("/tmp/b", "cat1", 2048),
            make_candidate("/tmp/c", "cat2", 4096),
        ]
        base_path = Path("/tmp")

        with patch("builtins.print") as mock_print:
            print_candidates_report(candidates, candidates, base_path)

        # Check summary section was printed
        calls = [str(call) for call in mock_print.call_args_list]
        summary_found = any("Per-category totals" in str(call) for call in calls)
        assert summary_found

    def test_print_report_formats_sizes(self):
        """Test report formats sizes correctly."""
        candidates = [make_candidate("/tmp/test", "cat1", 1024)]
        base_path = Path("/tmp")

        with patch("builtins.print") as mock_print:
            print_candidates_report(candidates, candidates, base_path)

        # Check that size formatting appears in output
        calls = [str(call) for call in mock_print.call_args_list]
        size_found = any("1.0KB" in str(call) for call in calls)
        assert size_found

    def test_print_report_shows_mtime(self):
        """Test report shows modification time."""
        candidates = [make_candidate("/tmp/test", "cat1", 1024, 1234567890.0)]
        base_path = Path("/tmp")

        with patch("builtins.print") as mock_print:
            print_candidates_report(candidates, candidates, base_path)

        # Check that mtime appears in output
        calls = [str(call) for call in mock_print.call_args_list]
        mtime_found = any("mtime" in str(call) for call in calls)
        assert mtime_found
