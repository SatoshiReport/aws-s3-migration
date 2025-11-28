"""Shared helpers for migration_sync tests."""

from __future__ import annotations

from unittest import mock


def create_mock_process(stdout_lines, poll_results, stderr_output: str | None = None):
    """Build a lightweight Popen-like mock for sync tests."""
    process = mock.Mock()

    stdout_iter = iter(stdout_lines)
    process.stdout.readline = mock.Mock(side_effect=lambda: next(stdout_iter, ""))

    poll_iter = iter(poll_results)
    process.poll = mock.Mock(side_effect=lambda: next(poll_iter, 0))

    process.terminate = mock.Mock()

    stderr_payload = "" if stderr_output is None else stderr_output
    process.stderr = mock.Mock()
    process.stderr.read = mock.Mock(return_value=stderr_payload)

    process.returncode = 0
    return process
