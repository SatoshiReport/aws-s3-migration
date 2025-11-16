"""Tests for cleanup_temp_artifacts/reports.py I/O operations."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from cleanup_temp_artifacts.reports import (  # pylint: disable=no-name-in-module
    delete_paths,
    print_candidates_report,
    summarise,
)
from cost_toolkit.common.format_utils import (
    BYTES_PER_GIB,
    BYTES_PER_KIB,
    BYTES_PER_MIB,
    BYTES_PER_TIB,
    format_bytes,
)
from tests.assertions import assert_equal


class TestFormatSizeBasic:
    """Test format_size function - basic units (bytes, KB, MB)."""

    def test_format_none(self):
        """Test formatting None returns 'n/a'."""
        assert_equal(
            format_bytes(None, decimal_places=1, binary_units=False).replace(" ", ""), "n/a"
        )

    def test_format_bytes(self):
        """Test formatting byte values less than 1KB."""
        assert_equal(format_bytes(0, decimal_places=1, binary_units=False).replace(" ", ""), "0.0B")
        assert_equal(format_bytes(1, decimal_places=1, binary_units=False).replace(" ", ""), "1.0B")
        assert_equal(
            format_bytes(999, decimal_places=1, binary_units=False).replace(" ", ""), "999.0B"
        )
        assert_equal(
            format_bytes(1023, decimal_places=1, binary_units=False).replace(" ", ""), "1023.0B"
        )

    def test_format_kilobytes(self):
        """Test formatting kilobyte values."""
        assert_equal(
            format_bytes(BYTES_PER_KIB, decimal_places=1, binary_units=False).replace(" ", ""),
            "1.0KB",
        )
        assert_equal(
            format_bytes(10 * BYTES_PER_KIB, decimal_places=1, binary_units=False).replace(" ", ""),
            "10.0KB",
        )
        assert_equal(
            format_bytes(int(1.5 * BYTES_PER_KIB), decimal_places=1, binary_units=False).replace(
                " ", ""
            ),
            "1.5KB",
        )

    def test_format_megabytes(self):
        """Test formatting megabyte values."""
        assert_equal(
            format_bytes(BYTES_PER_MIB, decimal_places=1, binary_units=False).replace(" ", ""),
            "1.0MB",
        )
        assert_equal(
            format_bytes(10 * BYTES_PER_MIB, decimal_places=1, binary_units=False).replace(" ", ""),
            "10.0MB",
        )
        assert_equal(
            format_bytes(int(2.5 * BYTES_PER_MIB), decimal_places=1, binary_units=False).replace(
                " ", ""
            ),
            "2.5MB",
        )


class TestFormatSizeLarge:
    """Test format_size function - large units (GB, TB, PB)."""

    def test_format_gigabytes(self):
        """Test formatting gigabyte values."""
        assert_equal(
            format_bytes(BYTES_PER_GIB, decimal_places=1, binary_units=False).replace(" ", ""),
            "1.0GB",
        )
        assert_equal(
            format_bytes(5 * BYTES_PER_GIB, decimal_places=1, binary_units=False).replace(" ", ""),
            "5.0GB",
        )
        assert_equal(
            format_bytes(int(1.5 * BYTES_PER_GIB), decimal_places=1, binary_units=False).replace(
                " ", ""
            ),
            "1.5GB",
        )

    def test_format_terabytes(self):
        """Test formatting terabyte values."""
        assert_equal(
            format_bytes(BYTES_PER_TIB, decimal_places=1, binary_units=False).replace(" ", ""),
            "1.0TB",
        )
        assert_equal(
            format_bytes(2 * BYTES_PER_TIB, decimal_places=1, binary_units=False).replace(" ", ""),
            "2.0TB",
        )

    def test_format_petabytes(self):
        """Test formatting petabyte values."""
        peta = BYTES_PER_TIB * 1024
        assert_equal(
            format_bytes(peta, decimal_places=1, binary_units=False).replace(" ", ""), "1.0PB"
        )
        assert_equal(
            format_bytes(5 * peta, decimal_places=1, binary_units=False).replace(" ", ""), "5.0PB"
        )

    def test_format_very_large_values(self):
        """Test formatting values beyond petabytes."""
        exa = BYTES_PER_TIB * 1024 * 1024
        result = format_bytes(exa, decimal_places=1, binary_units=False).replace(" ", "")
        assert result.endswith("PB")

    def test_format_precision(self):
        """Test formatting maintains one decimal place."""
        assert_equal(
            format_bytes(1536, decimal_places=1, binary_units=False).replace(" ", ""), "1.5KB"
        )
        assert_equal(
            format_bytes(int(2.7 * BYTES_PER_MIB), decimal_places=1, binary_units=False).replace(
                " ", ""
            ),
            "2.7MB",
        )


class TestSummarise:
    """Test summarise function for category aggregation."""

    def test_summarise_empty_list(self):
        """Test summarise with empty candidate list."""
        result = summarise([])
        assert_equal(result, [])

    def test_summarise_single_category(self, make_candidate):
        """Test summarise with single category."""
        candidates = [
            make_candidate("/tmp/a", "cat1", 100),
            make_candidate("/tmp/b", "cat1", 200),
            make_candidate("/tmp/c", "cat1", 300),
        ]
        result = summarise(candidates)
        expected = 600
        assert_equal(len(result), 1)
        assert_equal(result[0], ("cat1", 3, expected))

    def test_summarise_multiple_categories(self, make_candidate):
        """Test summarise with multiple categories."""
        candidates = [
            make_candidate("/tmp/a", "cat1", 100),
            make_candidate("/tmp/b", "cat2", 200),
            make_candidate("/tmp/c", "cat1", 300),
            make_candidate("/tmp/d", "cat3", 400),
        ]
        result = summarise(candidates)

        # Convert to dict for easier testing
        result_dict = {name: (count, size) for name, count, size in result}

        assert_equal(len(result_dict), 3)
        assert_equal(result_dict["cat1"], (2, 400))
        assert_equal(result_dict["cat2"], (1, 200))
        assert_equal(result_dict["cat3"], (1, 400))

    def test_summarise_none_sizes(self, make_candidate):
        """Test summarise handles None sizes correctly."""
        candidates = [
            make_candidate("/tmp/a", "cat1", None),
            make_candidate("/tmp/b", "cat1", 100),
            make_candidate("/tmp/c", "cat1", None),
        ]
        result = summarise(candidates)
        expected = 100
        assert_equal(result[0], ("cat1", 3, expected))

    def test_summarise_sorted_output(self, make_candidate):
        """Test summarise output is sorted by category name."""
        candidates = [
            make_candidate("/tmp/a", "zebra", 100),
            make_candidate("/tmp/b", "alpha", 200),
            make_candidate("/tmp/c", "beta", 300),
        ]
        result = summarise(candidates)
        names = [name for name, _, _ in result]
        assert_equal(names, ["alpha", "beta", "zebra"])


class TestPrintCandidatesReport:
    """Test print_candidates_report function for console output."""

    def test_print_report_basic(self, make_candidate):
        """Test printing basic report."""
        candidates = [
            make_candidate("/tmp/test1", "cat1", 1024),
            make_candidate("/tmp/test2", "cat2", 2048),
        ]
        base_path = Path("/tmp")

        with patch("builtins.print") as mock_print:
            print_candidates_report(candidates, candidates, base_path)

        # Verify print was called
        assert mock_print.call_count > 0

        # Check header was printed
        calls = [str(call) for call in mock_print.call_args_list]
        header_found = any("Identified 2 candidate(s)" in str(call) for call in calls)
        assert header_found

    def test_print_report_with_subset(self, make_candidate):
        """Test printing report with subset of acted_upon candidates."""
        all_candidates = [
            make_candidate("/tmp/test1", "cat1", 1024),
            make_candidate("/tmp/test2", "cat1", 2048),
            make_candidate("/tmp/test3", "cat1", 4096),
        ]
        acted_upon = all_candidates[:2]
        base_path = Path("/tmp")

        with patch("builtins.print") as mock_print:
            print_candidates_report(all_candidates, acted_upon, base_path)

        # Check header shows correct counts
        calls = [str(call) for call in mock_print.call_args_list]
        header_found = any("showing 2" in str(call) for call in calls)
        assert header_found

    def test_print_report_empty(self):
        """Test printing report with no candidates."""
        base_path = Path("/tmp")

        with patch("builtins.print") as mock_print:
            print_candidates_report([], [], base_path)

        # Verify print was called for header
        assert mock_print.call_count > 0


class TestDeletePathsBasic:
    """Test basic delete_paths functionality."""

    def test_delete_single_file(self, make_candidate):
        """Test deleting a single file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            test_file = root / "test.txt"
            test_file.write_text("test content")

            candidates = [make_candidate(test_file, "cat1")]
            errors = delete_paths(candidates, root=root)

            assert_equal(errors, [])
            assert not test_file.exists()

    def test_delete_directory(self, make_candidate):
        """Test deleting a directory tree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            test_dir = root / "testdir"
            test_dir.mkdir()
            (test_dir / "file1.txt").write_text("content")
            (test_dir / "file2.txt").write_text("content")

            candidates = [make_candidate(test_dir, "cat1")]
            errors = delete_paths(candidates, root=root)

            assert_equal(errors, [])
            assert not test_dir.exists()

    def test_delete_multiple_paths(self, make_candidate):
        """Test deleting multiple files and directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            file1 = root / "file1.txt"
            file2 = root / "file2.txt"
            dir1 = root / "dir1"

            file1.write_text("content")
            file2.write_text("content")
            dir1.mkdir()
            (dir1 / "nested.txt").write_text("content")

            candidates = [
                make_candidate(file1, "cat1"),
                make_candidate(file2, "cat1"),
                make_candidate(dir1, "cat1"),
            ]
            errors = delete_paths(candidates, root=root)

            assert_equal(errors, [])
            assert not file1.exists()
            assert not file2.exists()
            assert not dir1.exists()


class TestDeletePathsErrors:
    """Test delete_paths error handling."""

    def test_delete_path_escapes_root(self, make_candidate):
        """Test deletion fails when path escapes root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = (Path(tmpdir) / "subdir").resolve()
            root.mkdir()
            outside_file = Path(tmpdir).resolve() / "outside.txt"
            outside_file.write_text("content")

            candidates = [make_candidate(outside_file, "cat1")]
            errors = delete_paths(candidates, root=root)

            assert_equal(len(errors), 1)
            assert isinstance(errors[0][1], ValueError)
            assert "escapes root" in str(errors[0][1])
            assert outside_file.exists()

    def test_delete_nonexistent_path(self, make_candidate):
        """Test deletion handles nonexistent paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            nonexistent = root / "nonexistent.txt"

            candidates = [make_candidate(nonexistent, "cat1")]
            errors = delete_paths(candidates, root=root)

            assert_equal(len(errors), 1)
            assert isinstance(errors[0][1], (OSError, FileNotFoundError))

    def test_delete_permission_error(self, make_candidate):
        """Test deletion handles permission errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            test_file = root / "readonly.txt"
            test_file.write_text("content")

            candidates = [make_candidate(test_file, "cat1")]

            # Mock unlink to raise PermissionError
            with patch.object(Path, "unlink", side_effect=PermissionError("No permission")):
                errors = delete_paths(candidates, root=root)

            assert_equal(len(errors), 1)
            assert isinstance(errors[0][1], PermissionError)

    def test_delete_directory_with_shutil_error(self, make_candidate):
        """Test deletion handles shutil errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            test_dir = root / "testdir"
            test_dir.mkdir()

            candidates = [make_candidate(test_dir, "cat1")]

            # Mock rmtree to raise shutil.Error
            with patch("shutil.rmtree", side_effect=shutil.Error("Removal failed")):
                errors = delete_paths(candidates, root=root)

            assert_equal(len(errors), 1)
            assert isinstance(errors[0][1], shutil.Error)
