"""Tests for cost_toolkit/scripts/audit/s3_audit/utils.py"""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.scripts.audit.s3_audit.utils import (
    calculate_monthly_cost,
    format_bytes,
)
from tests.assertions import assert_equal


def test_calculate_monthly_cost_standard():
    """Test calculate_monthly_cost for STANDARD storage."""
    # 1 GB in STANDARD storage at $0.023/GB
    with patch(
        "cost_toolkit.scripts.audit.s3_audit.utils.STORAGE_CLASS_PRICING",
        {"STANDARD": 0.023},
    ):
        cost = calculate_monthly_cost(1024**3, "STANDARD")
        assert_equal(cost, 0.023)


def test_calculate_monthly_cost_unknown_class():
    """Test calculate_monthly_cost falls back to STANDARD for unknown class."""
    with patch(
        "cost_toolkit.scripts.audit.s3_audit.utils.STORAGE_CLASS_PRICING",
        {"STANDARD": 0.023, "GLACIER": 0.004},
    ):
        cost = calculate_monthly_cost(1024**3, "UNKNOWN_CLASS")
        # Should use STANDARD pricing as fallback
        assert_equal(cost, 0.023)


def test_format_bytes_small_values():
    """Test format_bytes for small byte values."""
    assert_equal(format_bytes(100), "100.00 B")
    assert_equal(format_bytes(512), "512.00 B")


def test_format_bytes_kilobytes():
    """Test format_bytes for kilobyte values."""
    with patch("cost_toolkit.scripts.audit.s3_audit.utils.BYTES_PER_KB", 1024):
        assert_equal(format_bytes(1024), "1.00 KB")
        assert_equal(format_bytes(2048), "2.00 KB")


def test_format_bytes_megabytes():
    """Test format_bytes for megabyte values."""
    with patch("cost_toolkit.scripts.audit.s3_audit.utils.BYTES_PER_KB", 1024):
        assert_equal(format_bytes(1024 * 1024), "1.00 MB")
        assert_equal(format_bytes(5 * 1024 * 1024), "5.00 MB")


def test_format_bytes_gigabytes():
    """Test format_bytes for gigabyte values."""
    with patch("cost_toolkit.scripts.audit.s3_audit.utils.BYTES_PER_KB", 1024):
        assert_equal(format_bytes(1024**3), "1.00 GB")
        assert_equal(format_bytes(10 * 1024**3), "10.00 GB")


def test_format_bytes_terabytes():
    """Test format_bytes for terabyte values."""
    with patch("cost_toolkit.scripts.audit.s3_audit.utils.BYTES_PER_KB", 1024):
        assert_equal(format_bytes(1024**4), "1.00 TB")


def test_format_bytes_petabytes():
    """Test format_bytes for petabyte values."""
    with patch("cost_toolkit.scripts.audit.s3_audit.utils.BYTES_PER_KB", 1024):
        assert_equal(format_bytes(1024**5), "1.00 PB")
