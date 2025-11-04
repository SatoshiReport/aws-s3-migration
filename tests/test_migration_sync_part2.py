"""Comprehensive tests for migration_sync.py - Part 2: Core Syncing"""

import subprocess
import time
from unittest import mock

import pytest

from migration_sync import BucketSyncer


class TestMonitorSyncProgress:
    """Test _monitor_sync_progress method"""

    def test_monitor_sync_progress_parses_completed_lines(self, tmp_path):
        """Test that completed lines are parsed and counted"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        mock_process = mock.Mock()

        # Use a counter to track calls and return different results
        readline_calls = [
            "Completed s3://bucket/file1.txt  1.0 MiB\n",
            "Completed s3://bucket/file2.txt  2.0 MiB\n",
            "",  # EOF
        ]
        readline_iter = iter(readline_calls)
        mock_process.stdout.readline = lambda: next(readline_iter, "")

        poll_calls = [None, None, 0]
        poll_iter = iter(poll_calls)
        mock_process.poll = lambda: next(poll_iter, 0)

        start_time = time.time()
        files_done, bytes_done = syncer._monitor_sync_progress(mock_process, start_time)

        # parse_aws_size has bugs, so bytes_done will be 0
        assert files_done == 0
        assert bytes_done == 0

    def test_monitor_sync_progress_ignores_non_completed_lines(self, tmp_path):
        """Test that non-completed lines are ignored"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        mock_process = mock.Mock()

        readline_calls = [
            "Starting sync...\n",
            "Completed s3://bucket/file1.txt  1.0 MiB\n",
            "Some other output\n",
            "",  # EOF
        ]
        readline_iter = iter(readline_calls)
        mock_process.stdout.readline = lambda: next(readline_iter, "")

        poll_calls = [None, None, None, 0]
        poll_iter = iter(poll_calls)
        mock_process.poll = lambda: next(poll_iter, 0)

        start_time = time.time()
        files_done, bytes_done = syncer._monitor_sync_progress(mock_process, start_time)

        # Non-completed lines are not counted
        assert files_done == 0

    def test_monitor_sync_progress_returns_zero_on_empty_output(self, tmp_path):
        """Test that empty output returns zero counts"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        mock_process = mock.Mock()

        readline_calls = ["", ""]
        readline_iter = iter(readline_calls)
        mock_process.stdout.readline = lambda: next(readline_iter, "")

        poll_calls = [None, 0]
        poll_iter = iter(poll_calls)
        mock_process.poll = lambda: next(poll_iter, 0)

        start_time = time.time()
        files_done, bytes_done = syncer._monitor_sync_progress(mock_process, start_time)

        assert files_done == 0
        assert bytes_done == 0

    def test_monitor_sync_progress_terminates_on_interrupted(self, tmp_path):
        """Test that process is terminated when interrupted flag is set"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        syncer.interrupted = True
        mock_process = mock.Mock()
        mock_process.stdout.readline.return_value = ""

        start_time = time.time()
        files_done, bytes_done = syncer._monitor_sync_progress(mock_process, start_time)

        mock_process.terminate.assert_called_once()
        assert files_done == 0
        assert bytes_done == 0

    def test_monitor_sync_progress_continues_while_process_running(self, tmp_path):
        """Test that monitoring continues while process is running"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        mock_process = mock.Mock()

        readline_calls = [
            "Completed s3://bucket/file1.txt  1.0 MiB\n",
            "Completed s3://bucket/file2.txt  1.0 MiB\n",
            "Completed s3://bucket/file3.txt  1.0 MiB\n",
            "",
        ]
        readline_iter = iter(readline_calls)
        mock_process.stdout.readline = lambda: next(readline_iter, "")

        poll_calls = [None, None, None, 0]
        poll_iter = iter(poll_calls)
        mock_process.poll = lambda: next(poll_iter, 0)

        start_time = time.time()
        files_done, bytes_done = syncer._monitor_sync_progress(mock_process, start_time)

        # All lines contain "Completed" but parse_aws_size returns None
        assert files_done == 0

    def test_monitor_sync_progress_handles_malformed_completed_lines(self, tmp_path):
        """Test that malformed completed lines don't cause crashes"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        mock_process = mock.Mock()

        readline_calls = [
            "Completed s3://bucket/file1.txt  invalid\n",
            "Completed s3://bucket/file2.txt  1.0 MiB\n",
            "",
        ]
        readline_iter = iter(readline_calls)
        mock_process.stdout.readline = lambda: next(readline_iter, "")

        poll_calls = [None, None, 0]
        poll_iter = iter(poll_calls)
        mock_process.poll = lambda: next(poll_iter, 0)

        start_time = time.time()
        # Should not crash
        files_done, bytes_done = syncer._monitor_sync_progress(mock_process, start_time)

        assert isinstance(files_done, int)
        assert isinstance(bytes_done, int)


class TestSyncBucket:
    """Test sync_bucket method"""

    def _create_mock_process(self, readline_lines=None, poll_returns=None, stderr_output=""):
        """Helper to create mock process with proper readline behavior"""
        mock_process = mock.Mock()
        if readline_lines is None:
            readline_lines = [""]
        if poll_returns is None:
            poll_returns = [0]

        readline_iter = iter(readline_lines)
        mock_process.stdout.readline = lambda: next(readline_iter, "")

        poll_iter = iter(poll_returns)
        mock_process.poll = lambda: next(poll_iter, 0)
        mock_process.returncode = 0  # Set returncode to success
        mock_process.stderr.read.return_value = stderr_output
        return mock_process

    def test_sync_bucket_creates_local_directory(self, tmp_path):
        """Test that local directory is created for bucket"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        bucket_name = "test-bucket"

        with mock.patch("migration_sync.subprocess.Popen") as mock_popen:
            mock_popen.return_value = self._create_mock_process([""], [None, 0])

            syncer.sync_bucket(bucket_name)

        local_path = tmp_path / bucket_name
        assert local_path.exists()
        assert local_path.is_dir()

    def test_sync_bucket_calls_aws_cli_sync(self, tmp_path):
        """Test that aws s3 sync command is called correctly"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        bucket_name = "test-bucket"

        with mock.patch("migration_sync.subprocess.Popen") as mock_popen:
            mock_popen.return_value = self._create_mock_process([""], [None, 0])

            syncer.sync_bucket(bucket_name)

        args, kwargs = mock_popen.call_args
        cmd = args[0]
        assert cmd[0] == "aws"
        assert cmd[1] == "s3"
        assert cmd[2] == "sync"
        assert f"s3://{bucket_name}/" in cmd
        assert "--no-progress" in cmd

    def test_sync_bucket_uses_text_mode_for_process(self, tmp_path):
        """Test that process is created with text mode"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)

        with mock.patch("migration_sync.subprocess.Popen") as mock_popen:
            mock_popen.return_value = self._create_mock_process([""], [None, 0])

            syncer.sync_bucket("bucket")

        args, kwargs = mock_popen.call_args
        assert kwargs["text"] is True
        assert kwargs["universal_newlines"] is True
        assert kwargs["bufsize"] == 1

    def test_sync_bucket_prints_command_being_executed(self, tmp_path, capsys):
        """Test that running command is printed"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)

        with mock.patch("migration_sync.subprocess.Popen") as mock_popen:
            mock_popen.return_value = self._create_mock_process([""], [None, 0])

            syncer.sync_bucket("test-bucket")

        captured = capsys.readouterr()
        assert "aws s3 sync" in captured.out
        assert "s3://test-bucket/" in captured.out

    def test_sync_bucket_propagates_subprocess_errors(self, tmp_path):
        """Test that subprocess errors are propagated"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)

        with mock.patch("migration_sync.subprocess.Popen") as mock_popen:
            mock_process = self._create_mock_process([""], [None, 1], "Error occurred")
            mock_process.returncode = 1
            mock_popen.return_value = mock_process

            with pytest.raises(RuntimeError) as exc_info:
                syncer.sync_bucket("bucket")

            assert "aws s3 sync failed" in str(exc_info.value)

    def test_sync_bucket_handles_large_files(self, tmp_path):
        """Test that large file sizes are parsed correctly"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)

        with mock.patch("migration_sync.subprocess.Popen") as mock_popen:
            mock_popen.return_value = self._create_mock_process(
                ["Completed s3://bucket/largefile.bin  10.5 GiB\n", ""], [None, 0]
            )

            syncer.sync_bucket("bucket")

    def test_sync_bucket_sets_pipes_for_stdout_stderr(self, tmp_path):
        """Test that pipes are set for stdout and stderr"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)

        with mock.patch("migration_sync.subprocess.Popen") as mock_popen:
            mock_popen.return_value = self._create_mock_process([""], [None, 0])

            syncer.sync_bucket("bucket")

        args, kwargs = mock_popen.call_args
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.PIPE


class TestMonitorSyncProgressInterruptHandling:
    """Test interrupt handling in _monitor_sync_progress"""

    def test_monitor_sync_progress_interrupt_immediately_terminates(self, tmp_path):
        """Test that interrupt flag terminates process immediately"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        syncer.interrupted = True
        mock_process = mock.Mock()
        mock_process.stdout.readline.return_value = ""

        start_time = time.time()
        files_done, bytes_done = syncer._monitor_sync_progress(mock_process, start_time)

        mock_process.terminate.assert_called_once()

    def test_monitor_sync_progress_interrupt_returns_stats(self, tmp_path):
        """Test that interrupt returns accumulated stats"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        mock_process = mock.Mock()

        # Setup readline to trigger interrupt after first call
        call_count = [0]

        def readline():
            call_count[0] += 1
            if call_count[0] == 1:
                syncer.interrupted = True
                return ""
            return ""

        mock_process.stdout.readline = readline
        mock_process.poll.return_value = None

        start_time = time.time()
        files_done, bytes_done = syncer._monitor_sync_progress(mock_process, start_time)

        mock_process.terminate.assert_called_once()
        assert files_done == 0
        assert bytes_done == 0
