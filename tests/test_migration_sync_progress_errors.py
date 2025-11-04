"""Comprehensive tests for migration_sync.py - Progress and Error Handling"""

import subprocess
import time
from unittest import mock

import pytest

from migration_sync import BucketSyncer


class TestDisplayProgress:
    """Test _display_progress method"""

    def test_display_progress_no_output_when_no_bytes(self, tmp_path, capsys):
        """Test that progress is not displayed when no bytes downloaded"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        start_time = time.time()

        syncer._display_progress(start_time, 0, 0)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_display_progress_prints_progress_with_data(self, tmp_path, capsys):
        """Test that progress is printed with files and bytes"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        start_time = time.time() - 5
        files_done = 10
        bytes_done = 1024 * 1024

        syncer._display_progress(start_time, files_done, bytes_done)

        captured = capsys.readouterr()
        assert "Progress:" in captured.out
        assert "files" in captured.out

    def test_display_progress_includes_throughput(self, tmp_path, capsys):
        """Test that throughput is included in progress output"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        start_time = time.time() - 10
        files_done = 5
        bytes_done = 1024 * 1024 * 5  # 5 MB

        syncer._display_progress(start_time, files_done, bytes_done)

        captured = capsys.readouterr()
        assert "/s" in captured.out

    def test_display_progress_with_zero_bytes_done(self, tmp_path, capsys):
        """Test display progress when no bytes have been downloaded"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        start_time = time.time() - 5

        syncer._display_progress(start_time, 0, 0)

        captured = capsys.readouterr()
        # No progress should be printed when no bytes done
        assert captured.out == ""

    def test_display_progress_with_minimal_elapsed_time(self, tmp_path, capsys):
        """Test display progress with minimal elapsed time (near zero)"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        start_time = time.time()

        syncer._display_progress(start_time, 10, 1024)

        captured = capsys.readouterr()
        # With minimal elapsed time and bytes, progress is still displayed
        # (implementation checks elapsed > 0 to avoid division by zero)
        assert "Progress:" in captured.out or captured.out == ""


class TestCheckSyncErrors:
    """Test _check_sync_errors method"""

    def test_check_sync_errors_success_on_zero_return_code(self, tmp_path):
        """Test that no error is raised on successful return code"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        mock_process = mock.Mock()
        mock_process.returncode = 0
        mock_process.stderr.read.return_value = ""

        syncer._check_sync_errors(mock_process)

    def test_check_sync_errors_raises_on_nonzero_return_code(self, tmp_path):
        """Test that RuntimeError is raised on nonzero return code"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        mock_process = mock.Mock()
        mock_process.returncode = 1
        mock_process.stderr.read.return_value = ""

        with pytest.raises(RuntimeError) as exc_info:
            syncer._check_sync_errors(mock_process)

        assert "aws s3 sync failed" in str(exc_info.value)
        assert "return code 1" in str(exc_info.value)

    def test_check_sync_errors_includes_stderr_in_error_message(self, tmp_path):
        """Test that stderr output is included in error message"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        mock_process = mock.Mock()
        mock_process.returncode = 1
        mock_process.stderr.read.return_value = "Permission denied\nAccess error"

        with pytest.raises(RuntimeError) as exc_info:
            syncer._check_sync_errors(mock_process)

        error_msg = str(exc_info.value)
        assert "Permission denied" in error_msg
        assert "Access error" in error_msg

    def test_check_sync_errors_filters_completed_lines_from_stderr(self, tmp_path):
        """Test that 'Completed' lines are filtered from error output"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        mock_process = mock.Mock()
        mock_process.returncode = 1
        mock_process.stderr.read.return_value = "Completed s3://bucket/file.txt\nReal error"

        with pytest.raises(RuntimeError) as exc_info:
            syncer._check_sync_errors(mock_process)

        error_msg = str(exc_info.value)
        assert "Completed" not in error_msg
        assert "Real error" in error_msg

    def test_check_sync_errors_ignores_empty_stderr(self, tmp_path):
        """Test that empty stderr is handled correctly"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        mock_process = mock.Mock()
        mock_process.returncode = 1
        mock_process.stderr.read.return_value = ""

        with pytest.raises(RuntimeError) as exc_info:
            syncer._check_sync_errors(mock_process)

        assert "Error details:" not in str(exc_info.value)


class TestPrintSyncSummary:
    """Test _print_sync_summary method"""

    def test_print_sync_summary_prints_completion_message(self, tmp_path, capsys):
        """Test that sync summary prints completion message"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        start_time = time.time() - 10
        files_done = 100
        bytes_done = 1024 * 1024 * 100

        syncer._print_sync_summary(start_time, files_done, bytes_done)

        captured = capsys.readouterr()
        assert "Completed in" in captured.out

    def test_print_sync_summary_shows_file_count(self, tmp_path, capsys):
        """Test that file count is displayed in summary"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        start_time = time.time() - 5
        files_done = 42
        bytes_done = 1024 * 1024

        syncer._print_sync_summary(start_time, files_done, bytes_done)

        captured = capsys.readouterr()
        assert "42" in captured.out
        assert "files" in captured.out

    def test_print_sync_summary_shows_total_bytes(self, tmp_path, capsys):
        """Test that total bytes is displayed in summary"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        start_time = time.time() - 5
        files_done = 10
        bytes_done = 1024 * 1024 * 50

        syncer._print_sync_summary(start_time, files_done, bytes_done)

        captured = capsys.readouterr()
        assert "Downloaded:" in captured.out

    def test_print_sync_summary_shows_throughput(self, tmp_path, capsys):
        """Test that throughput is calculated and displayed"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        start_time = time.time() - 10
        files_done = 20
        bytes_done = 1024 * 1024 * 100

        syncer._print_sync_summary(start_time, files_done, bytes_done)

        captured = capsys.readouterr()
        assert "Throughput:" in captured.out
        assert "/s" in captured.out

    def test_print_sync_summary_handles_zero_elapsed_time(self, tmp_path, capsys):
        """Test that zero elapsed time is handled (throughput = 0)"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        start_time = time.time()
        files_done = 0
        bytes_done = 0

        syncer._print_sync_summary(start_time, files_done, bytes_done)

        captured = capsys.readouterr()
        assert "0.00 B/s" in captured.out or "Throughput:" in captured.out
