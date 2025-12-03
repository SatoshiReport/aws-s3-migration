"""Tests for cost_toolkit/common/s3_utils.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cost_toolkit.common.s3_utils import create_s3_bucket_with_region, get_bucket_region


@patch("cost_toolkit.common.s3_utils.logging.info")
def test_create_s3_bucket_with_region_us_east_1(mock_log_info):
    """Test create_s3_bucket_with_region for us-east-1 (no LocationConstraint)."""
    mock_s3 = MagicMock()

    create_s3_bucket_with_region(mock_s3, "test-bucket", "us-east-1")

    mock_s3.create_bucket.assert_called_once_with(Bucket="test-bucket")
    mock_log_info.assert_called_once()


@patch("cost_toolkit.common.s3_utils.logging.info")
def test_create_s3_bucket_with_region_other_region(mock_log_info):
    """Test create_s3_bucket_with_region for non-us-east-1 region."""
    mock_s3 = MagicMock()

    create_s3_bucket_with_region(mock_s3, "test-bucket", "eu-west-1")

    mock_s3.create_bucket.assert_called_once_with(
        Bucket="test-bucket",
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )
    mock_log_info.assert_called_once()


def test_get_bucket_region_requires_name():
    """get_bucket_region should reject empty bucket names."""
    with pytest.raises(ValueError):
        get_bucket_region("")


def test_get_bucket_region_respects_custom_getter_and_quiet():
    """get_bucket_region uses provided getter and bypasses verbose output when disabled."""
    captured_prints = []

    def location_getter(name):
        captured_prints.append(name)
        return "us-west-1"

    region = get_bucket_region("custom-bucket", verbose=False, location_getter=location_getter)

    assert region == "us-west-1"
    assert captured_prints == ["custom-bucket"]
