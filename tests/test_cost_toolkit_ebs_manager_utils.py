"""Tests for cost_toolkit/scripts/management/ebs_manager/utils.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.management.ebs_manager.utils import (
    find_volume_region,
    get_all_aws_regions,
    get_instance_name,
    get_volume_tags,
)
from tests.assertions import assert_equal


@patch("boto3.client")
def test_get_all_aws_regions(mock_boto_client):
    """Test get_all_aws_regions returns list of regions."""
    mock_ec2 = MagicMock()
    mock_boto_client.return_value = mock_ec2
    mock_ec2.describe_regions.return_value = {
        "Regions": [
            {"RegionName": "us-east-1"},
            {"RegionName": "us-west-2"},
            {"RegionName": "eu-west-1"},
        ]
    }

    result = get_all_aws_regions()

    assert_equal(result, ["us-east-1", "us-west-2", "eu-west-1"])
    mock_boto_client.assert_called_once_with("ec2", region_name="us-east-1")
    mock_ec2.describe_regions.assert_called_once()


@patch("cost_toolkit.scripts.management.ebs_manager.utils.get_all_aws_regions")
@patch("boto3.client")
def test_find_volume_region_found(mock_boto_client, mock_get_regions):
    """Test find_volume_region finds volume in second region."""
    mock_get_regions.return_value = ["us-east-1", "us-west-2", "eu-west-1"]

    # First region: volume not found
    mock_ec2_1 = MagicMock()
    mock_ec2_1.describe_volumes.side_effect = ClientError(
        {"Error": {"Code": "InvalidVolume.NotFound"}}, "DescribeVolumes"
    )

    # Second region: volume found
    mock_ec2_2 = MagicMock()
    mock_ec2_2.describe_volumes.return_value = {"Volumes": [{"VolumeId": "vol-1234567890abcdef0"}]}

    mock_boto_client.side_effect = [mock_ec2_1, mock_ec2_2]

    result = find_volume_region("vol-1234567890abcdef0")

    assert_equal(result, "us-west-2")
    assert_equal(mock_boto_client.call_count, 2)


@patch("cost_toolkit.scripts.management.ebs_manager.utils.get_all_aws_regions")
@patch("boto3.client")
def test_find_volume_region_not_found(mock_boto_client, mock_get_regions):
    """Test find_volume_region returns None when volume not found."""
    mock_get_regions.return_value = ["us-east-1", "us-west-2"]

    mock_ec2 = MagicMock()
    mock_ec2.describe_volumes.side_effect = ClientError(
        {"Error": {"Code": "InvalidVolume.NotFound"}}, "DescribeVolumes"
    )

    mock_boto_client.return_value = mock_ec2

    result = find_volume_region("vol-nonexistent")

    assert result is None
    assert_equal(mock_boto_client.call_count, 2)


@patch("cost_toolkit.scripts.management.ebs_manager.utils._get_instance_name_with_client")
@patch("boto3.client")
def test_get_instance_name(mock_boto_client, mock_get_name):
    """Test get_instance_name returns instance name."""
    mock_ec2 = MagicMock()
    mock_boto_client.return_value = mock_ec2
    mock_get_name.return_value = "test-instance"

    result = get_instance_name("i-1234567890abcdef0", "us-east-1")

    assert_equal(result, "test-instance")
    mock_boto_client.assert_called_once_with("ec2", region_name="us-east-1")
    mock_get_name.assert_called_once_with(mock_ec2, "i-1234567890abcdef0")


@patch("cost_toolkit.scripts.management.ebs_manager.utils._get_instance_name_with_client")
@patch("boto3.client")
def test_get_instance_name_converts_unknown_to_no_name(mock_boto_client, mock_get_name):
    """Test get_instance_name converts 'Unknown' to 'No Name'."""
    mock_ec2 = MagicMock()
    mock_boto_client.return_value = mock_ec2
    mock_get_name.return_value = "Unknown"

    result = get_instance_name("i-1234567890abcdef0", "us-east-1")

    assert_equal(result, "No Name")


def test_get_volume_tags():
    """Test get_volume_tags extracts tags from volume."""
    volume = {
        "VolumeId": "vol-1234567890abcdef0",
        "Tags": [
            {"Key": "Name", "Value": "test-volume"},
            {"Key": "Environment", "Value": "production"},
        ],
    }

    result = get_volume_tags(volume)

    assert_equal(result, {"Name": "test-volume", "Environment": "production"})


def test_get_volume_tags_no_tags():
    """Test get_volume_tags returns empty dict when no tags."""
    volume = {"VolumeId": "vol-1234567890abcdef0"}

    result = get_volume_tags(volume)

    assert_equal(result, {})
