"""Tests for cost_toolkit/common/s3_utils.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cost_toolkit.common.s3_utils import create_s3_bucket_with_region


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
