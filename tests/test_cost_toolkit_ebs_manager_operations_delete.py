"""Tests for cost_toolkit/scripts/management/ebs_manager/operations.py - delete operations"""

# pylint: disable=unused-argument

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.management.ebs_manager.operations import delete_ebs_volume
from tests.assertions import assert_equal


# Test delete_ebs_volume
@patch("cost_toolkit.scripts.management.ebs_manager.operations.find_volume_region")
@patch("boto3.client")
def test_delete_ebs_volume_volume_not_found(mock_boto_client, mock_find_region, capsys):
    """Test delete_ebs_volume returns False when volume not found."""
    mock_find_region.return_value = None

    result = delete_ebs_volume("vol-nonexistent")

    assert_equal(result, False)
    captured = capsys.readouterr()
    assert "not found in any region" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.operations.find_volume_region")
@patch("boto3.client")
def test_delete_ebs_volume_describe_error(mock_boto_client, mock_find_region, capsys):
    """Test delete_ebs_volume handles describe_volumes error."""
    mock_find_region.return_value = "us-east-1"

    mock_ec2 = MagicMock()
    mock_ec2.exceptions.ClientError = ClientError
    mock_ec2.describe_volumes.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Not authorized"}}, "DescribeVolumes"
    )
    mock_boto_client.return_value = mock_ec2

    result = delete_ebs_volume("vol-123")

    assert_equal(result, False)
    captured = capsys.readouterr()
    assert "Error retrieving volume" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.operations.find_volume_region")
@patch("boto3.client")
def test_delete_ebs_volume_in_use(mock_boto_client, mock_find_region, capsys):
    """Test delete_ebs_volume refuses to delete in-use volume."""
    mock_find_region.return_value = "us-east-1"

    mock_ec2 = MagicMock()
    mock_ec2.exceptions.ClientError = ClientError
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Size": 50,
                "VolumeType": "gp3",
                "State": "in-use",
                "CreateTime": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "Tags": [],
            }
        ]
    }
    mock_boto_client.return_value = mock_ec2

    result = delete_ebs_volume("vol-123")

    assert_equal(result, False)
    captured = capsys.readouterr()
    assert "currently attached to an instance" in captured.out
    assert "must detach the volume" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.operations.find_volume_region")
@patch("boto3.client")
def test_delete_ebs_volume_cancelled_by_user(mock_boto_client, mock_find_region, capsys):
    """Test delete_ebs_volume cancels when user doesn't confirm."""
    mock_find_region.return_value = "us-east-1"

    mock_ec2 = MagicMock()
    mock_ec2.exceptions.ClientError = ClientError
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Size": 50,
                "VolumeType": "gp3",
                "State": "available",
                "CreateTime": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "Tags": [{"Key": "Name", "Value": "test-volume"}],
            }
        ]
    }
    mock_boto_client.return_value = mock_ec2

    with patch("builtins.input", return_value="NO"):
        result = delete_ebs_volume("vol-123")

    assert_equal(result, False)
    captured = capsys.readouterr()
    assert "Deletion cancelled" in captured.out
    assert "Volume to delete: vol-123" in captured.out
    assert "Region: us-east-1" in captured.out
    assert "Size: 50 GB" in captured.out
    assert "Tags:" in captured.out
    assert "Name: test-volume" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.operations.find_volume_region")
@patch("boto3.client")
def test_delete_ebs_volume_success_with_confirmation(mock_boto_client, mock_find_region, capsys):
    """Test delete_ebs_volume successfully deletes with user confirmation."""
    mock_find_region.return_value = "us-east-1"

    mock_ec2 = MagicMock()
    mock_ec2.exceptions.ClientError = ClientError
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Size": 50,
                "VolumeType": "gp3",
                "State": "available",
                "CreateTime": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "Tags": [],
            }
        ]
    }
    mock_boto_client.return_value = mock_ec2

    with patch("builtins.input", return_value="DELETE"):
        result = delete_ebs_volume("vol-123")

    assert_equal(result, True)
    captured = capsys.readouterr()
    assert "deletion initiated successfully" in captured.out
    mock_ec2.delete_volume.assert_called_once_with(VolumeId="vol-123")


@patch("cost_toolkit.scripts.management.ebs_manager.operations.find_volume_region")
@patch("boto3.client")
def test_delete_ebs_volume_success_force(mock_boto_client, mock_find_region, capsys):
    """Test delete_ebs_volume successfully deletes with force flag."""
    mock_find_region.return_value = "us-east-1"

    mock_ec2 = MagicMock()
    mock_ec2.exceptions.ClientError = ClientError
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Size": 50,
                "VolumeType": "gp3",
                "State": "available",
                "CreateTime": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "Tags": [{"Key": "Environment", "Value": "dev"}],
            }
        ]
    }
    mock_boto_client.return_value = mock_ec2

    result = delete_ebs_volume("vol-123", force=True)

    assert_equal(result, True)
    captured = capsys.readouterr()
    assert "deletion initiated successfully" in captured.out
    assert "WARNING: This action cannot be undone!" not in captured.out
    mock_ec2.delete_volume.assert_called_once_with(VolumeId="vol-123")


@patch("cost_toolkit.scripts.management.ebs_manager.operations.find_volume_region")
@patch("boto3.client")
def test_delete_ebs_volume_deletion_error(mock_boto_client, mock_find_region, capsys):
    """Test delete_ebs_volume handles deletion error."""
    mock_find_region.return_value = "us-east-1"

    mock_ec2 = MagicMock()
    mock_ec2.exceptions.ClientError = ClientError
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Size": 50,
                "VolumeType": "gp3",
                "State": "available",
                "CreateTime": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "Tags": [],
            }
        ]
    }
    mock_ec2.delete_volume.side_effect = ClientError(
        {"Error": {"Code": "VolumeInUse", "Message": "Volume is in use"}}, "DeleteVolume"
    )
    mock_boto_client.return_value = mock_ec2

    result = delete_ebs_volume("vol-123", force=True)

    assert_equal(result, False)
    captured = capsys.readouterr()
    assert "Error deleting volume" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.operations.find_volume_region")
@patch("boto3.client")
def test_delete_ebs_volume_no_tags(mock_boto_client, mock_find_region, capsys):
    """Test delete_ebs_volume handles volume without tags."""
    mock_find_region.return_value = "us-east-1"

    mock_ec2 = MagicMock()
    mock_ec2.exceptions.ClientError = ClientError
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Size": 50,
                "VolumeType": "gp3",
                "State": "available",
                "CreateTime": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            }
        ]
    }
    mock_boto_client.return_value = mock_ec2

    result = delete_ebs_volume("vol-123", force=True)

    assert_equal(result, True)
    captured = capsys.readouterr()
    assert "Tags:" not in captured.out
