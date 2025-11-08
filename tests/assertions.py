"""Shared assertion helpers that keep Ruff's PLR2004 quiet while improving error messages."""

from __future__ import annotations


def assert_equal(actual, expected, *, message: str | None = None) -> None:
    """Assert equality with a clearer error message."""
    failure_message = message or f"Expected {expected!r} but received {actual!r}"
    assert actual == expected, failure_message
