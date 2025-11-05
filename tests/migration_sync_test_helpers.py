"""Shared helpers for migration_sync tests."""

from __future__ import annotations

from typing import Iterable, Sequence
from unittest import mock


def create_mock_process(
    readline_lines: Sequence[str] | None = None,
    poll_returns: Sequence[int | None] | None = None,
    stderr_output: str = "",
):
    """Create a mock subprocess.Popen result with programmable output."""
    process = mock.Mock()
    if readline_lines is None:
        readline_lines = [""]
    if poll_returns is None:
        poll_returns = [0]

    readline_iter = iter(readline_lines)
    process.stdout.readline = lambda: next(readline_iter, "")

    poll_iter: Iterable[int | None] = iter(poll_returns)
    process.poll = lambda: next(poll_iter, 0)
    process.returncode = 0
    process.stderr.read.return_value = stderr_output
    return process
