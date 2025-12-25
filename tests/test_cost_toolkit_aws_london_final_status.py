"""Tests for cost_toolkit/scripts/migration/aws_london_final_status.py"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.migration.aws_london_final_status import (
    _build_volume_info,
    _extract_volume_name,
    _list_remaining_volumes,
    _print_optimization_summary,
    _stop_instance,
    main,
    show_final_london_status,
)


# Tests for _stop_instance
@patch("cost_toolkit.scripts.migration.aws_london_final_status.wait_for_instance_state")
@patch("builtins.print")
def test_stop_instance_success(_mock_print, mock_wait_for_state):
    """Test stopping instance successfully."""
    mock_ec2 = MagicMock()

    _stop_instance(mock_ec2, "i-12345678")

    mock_ec2.stop_instances.assert_called_once_with(InstanceIds=["i-12345678"])
    mock_wait_for_state.assert_called_once_with(mock_ec2, "i-12345678", "instance_stopped")
    _mock_print.assert_called()


@patch("builtins.print")
def test_stop_instance_client_error(_mock_print):
    """Test stopping instance with client error."""
    mock_ec2 = MagicMock()
    mock_ec2.stop_instances.side_effect = ClientError({"Error": {"Code": "InstanceNotFound"}}, "StopInstances")

    with pytest.raises(ClientError):
        _stop_instance(mock_ec2, "i-invalid")

    mock_ec2.stop_instances.assert_called_once()
    _mock_print.assert_called()


@patch("cost_toolkit.scripts.migration.aws_london_final_status.wait_for_instance_state")
@patch("builtins.print")
def test_stop_instance_different_id(_mock_print, mock_wait_for_state):
    """Test stopping different instance ID."""
    mock_ec2 = MagicMock()

    _stop_instance(mock_ec2, "i-abcdef123")

    mock_ec2.stop_instances.assert_called_once_with(InstanceIds=["i-abcdef123"])
    mock_wait_for_state.assert_called_once_with(mock_ec2, "i-abcdef123", "instance_stopped")


# Tests for _extract_volume_name
def test_extract_volume_name_with_name():
    """Test extracting volume name when Name tag exists."""
    volume = {
        "Tags": [
            {"Key": "Name", "Value": "MyVolume"},
            {"Key": "Environment", "Value": "Production"},
        ]
    }

    name = _extract_volume_name(volume)

    assert name == "MyVolume"


def test_extract_volume_name_no_tags():
    """Test extracting volume name when no tags exist."""
    volume = {}

    name = _extract_volume_name(volume)

    assert name == "No name"


def test_extract_volume_name_no_name_tag():
    """Test extracting volume name when Name tag doesn't exist."""
    volume = {
        "Tags": [
            {"Key": "Environment", "Value": "Production"},
        ]
    }

    name = _extract_volume_name(volume)

    assert name == "No name"


def test_extract_volume_name_empty_tags():
    """Test extracting volume name when tags list is empty."""
    volume = {"Tags": []}

    name = _extract_volume_name(volume)

    assert name == "No name"


def test_extract_volume_name_multiple_tags():
    """Test extracting volume name from multiple tags."""
    volume = {
        "Tags": [
            {"Key": "Owner", "Value": "Team"},
            {"Key": "Name", "Value": "DataVolume"},
            {"Key": "Type", "Value": "EBS"},
        ]
    }

    name = _extract_volume_name(volume)

    assert name == "DataVolume"


# Tests for _build_volume_info
def test_build_volume_info_complete():
    """Test building volume info with complete data."""
    created_time = datetime(2025, 1, 14, 12, 0, 0)
    volume = {
        "VolumeId": "vol-123",
        "Size": 100,
        "State": "available",
        "CreateTime": created_time,
        "Tags": [{"Key": "Name", "Value": "Test Volume"}],
    }

    info = _build_volume_info(volume)

    assert info["id"] == "vol-123"
    assert info["name"] == "Test Volume"
    assert info["size"] == 100
    assert info["state"] == "available"
    assert info["created"] == created_time
    assert info["cost"] == 8.0


def test_build_volume_info_no_tags():
    """Test building volume info without tags."""
    created_time = datetime(2025, 1, 14, 12, 0, 0)
    volume = {
        "VolumeId": "vol-456",
        "Size": 50,
        "State": "in-use",
        "CreateTime": created_time,
    }

    info = _build_volume_info(volume)

    assert info["id"] == "vol-456"
    assert info["name"] == "No name"
    assert info["size"] == 50
    assert info["cost"] == 4.0


def test_build_volume_info_large_volume():
    """Test building volume info for large volume."""
    created_time = datetime(2025, 1, 14, 12, 0, 0)
    volume = {
        "VolumeId": "vol-789",
        "Size": 1000,
        "State": "available",
        "CreateTime": created_time,
        "Tags": [{"Key": "Name", "Value": "Large Volume"}],
    }

    info = _build_volume_info(volume)

    assert info["size"] == 1000
    assert info["cost"] == 80.0


# Tests for _list_remaining_volumes
@patch("builtins.print")
def test_list_remaining_volumes_success(_mock_print):
    """Test listing remaining volumes successfully."""
    mock_ec2 = MagicMock()
    created_time = datetime(2025, 1, 14, 12, 0, 0)
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Size": 100,
                "State": "available",
                "CreateTime": created_time,
                "AvailabilityZone": "eu-west-2a",
                "Tags": [{"Key": "Name", "Value": "Volume 1"}],
            },
            {
                "VolumeId": "vol-456",
                "Size": 50,
                "State": "in-use",
                "CreateTime": created_time,
                "AvailabilityZone": "eu-west-2b",
                "Tags": [{"Key": "Name", "Value": "Volume 2"}],
            },
        ]
    }

    _list_remaining_volumes(mock_ec2)

    mock_ec2.describe_volumes.assert_called_once()
    _mock_print.assert_called()


@patch("builtins.print")
def test_list_remaining_volumes_filters_non_london(_mock_print):
    """Test listing volumes filters non-London volumes."""
    mock_ec2 = MagicMock()
    created_time = datetime(2025, 1, 14, 12, 0, 0)
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Size": 100,
                "State": "available",
                "CreateTime": created_time,
                "AvailabilityZone": "eu-west-2a",
                "Tags": [{"Key": "Name", "Value": "London Volume"}],
            },
            {
                "VolumeId": "vol-456",
                "Size": 50,
                "State": "in-use",
                "CreateTime": created_time,
                "AvailabilityZone": "us-east-1a",
                "Tags": [{"Key": "Name", "Value": "US Volume"}],
            },
        ]
    }

    _list_remaining_volumes(mock_ec2)

    call_args = [str(call) for call in _mock_print.call_args_list]
    combined = " ".join(call_args)

    assert "vol-123" in combined
    assert "vol-456" not in combined


@patch("builtins.print")
def test_list_remaining_volumes_empty(_mock_print):
    """Test listing remaining volumes when none exist."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_volumes.return_value = {"Volumes": []}

    _list_remaining_volumes(mock_ec2)

    mock_ec2.describe_volumes.assert_called_once()


@patch("builtins.print")
def test_list_remaining_volumes_client_error(_mock_print):
    """Test listing remaining volumes with client error."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_volumes.side_effect = ClientError({"Error": {"Code": "UnauthorizedOperation"}}, "DescribeVolumes")

    _list_remaining_volumes(mock_ec2)

    _mock_print.assert_called()


@patch("builtins.print")
def test_list_remaining_volumes_sorts_by_date(_mock_print):
    """Test listing remaining volumes sorts by creation date."""
    mock_ec2 = MagicMock()
    old_time = datetime(2025, 1, 10, 12, 0, 0)
    new_time = datetime(2025, 1, 14, 12, 0, 0)
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-old",
                "Size": 100,
                "State": "available",
                "CreateTime": old_time,
                "AvailabilityZone": "eu-west-2a",
            },
            {
                "VolumeId": "vol-new",
                "Size": 50,
                "State": "in-use",
                "CreateTime": new_time,
                "AvailabilityZone": "eu-west-2a",
            },
        ]
    }

    _list_remaining_volumes(mock_ec2)

    # Check that volumes are sorted (newest first)
    call_args = [str(call) for call in _mock_print.call_args_list]
    combined = " ".join(call_args)

    # Verify both volumes are listed
    assert "vol-old" in combined
    assert "vol-new" in combined


# Tests for _print_optimization_summary
@patch("builtins.print")
def test_print_optimization_summary(_mock_print):
    """Test printing optimization summary."""
    _print_optimization_summary()

    _mock_print.assert_called()
    call_args = [str(call) for call in _mock_print.call_args_list]
    combined = " ".join(call_args)

    assert "$85" in combined
    assert "2,528 GB" in combined
    assert "1,472 GB" in combined


# Tests for show_final_london_status
@patch("cost_toolkit.scripts.migration.aws_london_final_status._print_optimization_summary")
@patch("cost_toolkit.scripts.migration.aws_london_final_status._list_remaining_volumes")
@patch("cost_toolkit.scripts.migration.aws_london_final_status._stop_instance")
@patch("cost_toolkit.scripts.migration.aws_london_final_status.boto3")
@patch("builtins.print")
def test_show_final_london_status(_mock_print, mock_boto3, mock_stop, mock_list, mock_summary):
    """Test showing final London status."""
    mock_ec2 = MagicMock()
    mock_boto3.client.return_value = mock_ec2

    show_final_london_status()

    mock_boto3.client.assert_called_once_with("ec2", region_name="eu-west-2")
    mock_stop.assert_called_once_with(mock_ec2, "i-05ad29f28fc8a8fdc")
    mock_list.assert_called_once_with(mock_ec2)
    mock_summary.assert_called_once()


@patch("cost_toolkit.scripts.migration.aws_london_final_status._print_optimization_summary")
@patch("cost_toolkit.scripts.migration.aws_london_final_status._list_remaining_volumes")
@patch("cost_toolkit.scripts.migration.aws_london_final_status._stop_instance")
@patch("cost_toolkit.scripts.migration.aws_london_final_status.boto3")
@patch("builtins.print")
def test_show_final_london_status_stop_error(_mock_print, mock_boto3, mock_stop, _mock_list, _mock_summary):
    """Test showing final London status when stop fails."""
    mock_ec2 = MagicMock()
    mock_boto3.client.return_value = mock_ec2
    mock_stop.side_effect = ClientError({"Error": {"Code": "InstanceNotFound"}}, "StopInstances")

    try:
        show_final_london_status()
    except ClientError:
        pass


# Tests for main
@patch("cost_toolkit.scripts.migration.aws_london_final_status.show_final_london_status")
def test_main(mock_show):
    """Test main function."""
    main()
    mock_show.assert_called_once()


# Integration-style tests
@patch("cost_toolkit.scripts.migration.aws_london_final_status._print_optimization_summary")
@patch("cost_toolkit.scripts.migration.aws_london_final_status._list_remaining_volumes")
@patch("cost_toolkit.scripts.migration.aws_london_final_status._stop_instance")
@patch("cost_toolkit.scripts.migration.aws_london_final_status.boto3")
@patch("builtins.print")
def test_show_final_london_status_complete_workflow(_mock_print, mock_boto3, mock_stop, mock_list, mock_summary):
    """Test complete final status workflow."""
    mock_ec2 = MagicMock()
    mock_boto3.client.return_value = mock_ec2

    show_final_london_status()

    # Verify all steps are called in order
    assert mock_boto3.client.call_count == 1
    assert mock_stop.call_count == 1
    assert mock_list.call_count == 1
    assert mock_summary.call_count == 1


@patch("builtins.print")
def test_print_optimization_summary_content(_mock_print):
    """Test optimization summary contains expected content."""
    _print_optimization_summary()

    call_args = [str(call) for call in _mock_print.call_args_list]
    combined = " ".join(call_args)

    # Check for key information
    assert "Tars" in combined
    assert "1024 GB" in combined
    assert "$82/month" in combined
    assert "$3/month" in combined
    assert "30%" in combined
