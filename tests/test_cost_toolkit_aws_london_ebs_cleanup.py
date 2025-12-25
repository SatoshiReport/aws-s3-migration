"""Tests for cost_toolkit/scripts/migration/aws_london_ebs_cleanup.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.migration.aws_london_ebs_cleanup import (
    _delete_volumes,
    _detach_volume,
    _print_cleanup_summary,
    _print_volumes_to_delete,
    _show_remaining_volumes,
    cleanup_london_ebs_volumes,
    main,
)


# Tests for _print_volumes_to_delete
@patch("builtins.print")
def test_print_volumes_to_delete(_mock_print):
    """Test printing volumes to delete."""
    volumes = [
        {
            "id": "vol-123",
            "name": "Test Volume 1",
            "size": "100 GB",
            "reason": "Duplicate",
            "savings": "$8/month",
        },
        {
            "id": "vol-456",
            "name": "Test Volume 2",
            "size": "50 GB",
            "reason": "Unattached",
            "savings": "$4/month",
        },
    ]

    total = _print_volumes_to_delete(volumes)

    assert total == 12
    _mock_print.assert_called()


@patch("builtins.print")
def test_print_volumes_to_delete_empty(_mock_print):
    """Test printing empty volumes list."""
    volumes = []

    total = _print_volumes_to_delete(volumes)

    assert total == 0


@patch("builtins.print")
def test_print_volumes_to_delete_single(_mock_print):
    """Test printing single volume."""
    volumes = [
        {
            "id": "vol-789",
            "name": "Single Volume",
            "size": "200 GB",
            "reason": "Old",
            "savings": "$16/month",
        },
    ]

    total = _print_volumes_to_delete(volumes)

    assert total == 16


# Tests for _detach_volume
@patch("builtins.print")
def test_detach_volume_attached(_mock_print):
    """Test detaching an attached volume."""
    mock_ec2 = MagicMock()
    mock_waiter = MagicMock()
    mock_ec2.get_waiter.return_value = mock_waiter
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Attachments": [
                    {
                        "InstanceId": "i-123",
                        "Device": "/dev/sdf",
                    }
                ],
            }
        ]
    }

    _detach_volume(mock_ec2, "vol-123")

    mock_ec2.detach_volume.assert_called_once_with(
        VolumeId="vol-123",
        InstanceId="i-123",
        Device="/dev/sdf",
        Force=True,
    )
    mock_waiter.wait.assert_called_once_with(VolumeIds=["vol-123"])


@patch("builtins.print")
def test_detach_volume_not_attached(_mock_print):
    """Test detaching a volume that's not attached."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Attachments": [],
            }
        ]
    }

    _detach_volume(mock_ec2, "vol-123")

    mock_ec2.detach_volume.assert_not_called()


@patch("builtins.print")
def test_detach_volume_multiple_attachments(_mock_print):
    """Test detaching a volume with the first attachment."""
    mock_ec2 = MagicMock()
    mock_waiter = MagicMock()
    mock_ec2.get_waiter.return_value = mock_waiter
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Attachments": [
                    {
                        "InstanceId": "i-123",
                        "Device": "/dev/sdf",
                    },
                    {
                        "InstanceId": "i-456",
                        "Device": "/dev/sdg",
                    },
                ],
            }
        ]
    }

    _detach_volume(mock_ec2, "vol-123")

    mock_ec2.detach_volume.assert_called_once_with(
        VolumeId="vol-123",
        InstanceId="i-123",
        Device="/dev/sdf",
        Force=True,
    )


# Tests for _delete_volumes
@patch("builtins.print")
def test_delete_volumes_success(_mock_print):
    """Test successful volume deletion."""
    mock_ec2 = MagicMock()
    volumes = [
        {"id": "vol-123", "name": "Vol 1", "size": "100 GB", "savings": "$8/month"},
        {"id": "vol-456", "name": "Vol 2", "size": "50 GB", "savings": "$4/month"},
    ]

    deleted, failed = _delete_volumes(mock_ec2, volumes)

    assert len(deleted) == 2
    assert len(failed) == 0
    assert mock_ec2.delete_volume.call_count == 2


@patch("builtins.print")
def test_delete_volumes_with_failures(_mock_print):
    """Test volume deletion with some failures."""
    mock_ec2 = MagicMock()
    mock_ec2.delete_volume.side_effect = [
        None,
        ClientError({"Error": {"Code": "VolumeInUse"}}, "DeleteVolume"),
    ]
    volumes = [
        {"id": "vol-123", "name": "Vol 1", "size": "100 GB", "savings": "$8/month"},
        {"id": "vol-456", "name": "Vol 2", "size": "50 GB", "savings": "$4/month"},
    ]

    deleted, failed = _delete_volumes(mock_ec2, volumes)

    assert len(deleted) == 1
    assert len(failed) == 1
    assert failed[0]["volume"]["id"] == "vol-456"


@patch("builtins.print")
def test_delete_volumes_all_fail(_mock_print):
    """Test volume deletion when all fail."""
    mock_ec2 = MagicMock()
    mock_ec2.delete_volume.side_effect = ClientError({"Error": {"Code": "UnauthorizedOperation"}}, "DeleteVolume")
    volumes = [
        {"id": "vol-123", "name": "Vol 1", "size": "100 GB", "savings": "$8/month"},
    ]

    deleted, failed = _delete_volumes(mock_ec2, volumes)

    assert len(deleted) == 0
    assert len(failed) == 1


@patch("builtins.print")
def test_delete_volumes_empty_list(_mock_print):
    """Test deleting empty volume list."""
    mock_ec2 = MagicMock()
    volumes = []

    deleted, failed = _delete_volumes(mock_ec2, volumes)

    assert len(deleted) == 0
    assert len(failed) == 0
    mock_ec2.delete_volume.assert_not_called()


# Tests for _print_cleanup_summary
@patch("builtins.print")
def test_print_cleanup_summary_with_deletions(_mock_print):
    """Test printing cleanup summary with deleted volumes."""
    deleted = [
        {"id": "vol-123", "name": "Vol 1", "size": "100 GB", "savings": "$8/month"},
        {"id": "vol-456", "name": "Vol 2", "size": "50 GB", "savings": "$4/month"},
    ]
    failed = []

    savings = _print_cleanup_summary(deleted, failed)

    assert savings == 12
    _mock_print.assert_called()


@patch("builtins.print")
def test_print_cleanup_summary_with_failures(_mock_print):
    """Test printing cleanup summary with failures."""
    deleted = [
        {"id": "vol-123", "name": "Vol 1", "size": "100 GB", "savings": "$8/month"},
    ]
    failed = [
        {
            "volume": {"id": "vol-456", "name": "Vol 2"},
            "error": "VolumeInUse",
        }
    ]

    savings = _print_cleanup_summary(deleted, failed)

    assert savings == 8
    _mock_print.assert_called()


@patch("builtins.print")
def test_print_cleanup_summary_no_deletions(_mock_print):
    """Test printing cleanup summary with no deletions."""
    deleted = []
    failed = [
        {
            "volume": {"id": "vol-456", "name": "Vol 2"},
            "error": "UnauthorizedOperation",
        }
    ]

    savings = _print_cleanup_summary(deleted, failed)

    assert savings == 0
    _mock_print.assert_called()


@patch("builtins.print")
def test_print_cleanup_summary_empty(_mock_print):
    """Test printing cleanup summary with no deletions or failures."""
    deleted = []
    failed = []

    savings = _print_cleanup_summary(deleted, failed)

    assert savings == 0


# Tests for _show_remaining_volumes
@patch("builtins.print")
def test_show_remaining_volumes(_mock_print):
    """Test showing remaining volumes."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Size": 100,
                "State": "available",
                "Tags": [{"Key": "Name", "Value": "Test Volume"}],
            },
            {
                "VolumeId": "vol-456",
                "Size": 50,
                "State": "in-use",
                "Tags": [{"Key": "Name", "Value": "Another Volume"}],
            },
        ]
    }

    _show_remaining_volumes(mock_ec2)

    mock_ec2.describe_volumes.assert_called_once()
    _mock_print.assert_called()


@patch("builtins.print")
def test_show_remaining_volumes_no_tags(_mock_print):
    """Test showing remaining volumes without tags."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-123",
                "Size": 100,
                "State": "available",
            }
        ]
    }

    _show_remaining_volumes(mock_ec2)

    mock_ec2.describe_volumes.assert_called_once()


@patch("builtins.print")
def test_show_remaining_volumes_client_error(_mock_print):
    """Test showing remaining volumes with client error."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_volumes.side_effect = ClientError({"Error": {"Code": "UnauthorizedOperation"}}, "DescribeVolumes")

    _show_remaining_volumes(mock_ec2)

    _mock_print.assert_called()


@patch("builtins.print")
def test_show_remaining_volumes_empty(_mock_print):
    """Test showing remaining volumes when none exist."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_volumes.return_value = {"Volumes": []}

    _show_remaining_volumes(mock_ec2)

    mock_ec2.describe_volumes.assert_called_once()


# Tests for cleanup_london_ebs_volumes
def test_cleanup_london_ebs_volumes_success():
    """Test successful EBS cleanup."""
    with (
        patch("builtins.print"),
        patch("cost_toolkit.scripts.migration.aws_london_ebs_cleanup.aws_utils.setup_aws_credentials") as mock_setup,
        patch("cost_toolkit.scripts.migration.aws_london_ebs_cleanup.boto3") as mock_boto3,
        patch("cost_toolkit.scripts.migration.aws_london_ebs_cleanup._print_volumes_to_delete") as mock_print_vols,
        patch("cost_toolkit.scripts.migration.aws_london_ebs_cleanup._detach_volume") as mock_detach,
        patch("cost_toolkit.scripts.migration.aws_london_ebs_cleanup._delete_volumes") as mock_delete,
        patch("cost_toolkit.scripts.migration.aws_london_ebs_cleanup._print_cleanup_summary") as mock_summary,
        patch("cost_toolkit.scripts.migration.aws_london_ebs_cleanup._show_remaining_volumes") as mock_show,
    ):

        mock_ec2 = MagicMock()
        mock_boto3.client.return_value = mock_ec2
        mock_print_vols.return_value = 85
        mock_delete.return_value = ([], [])
        mock_summary.return_value = 85

        cleanup_london_ebs_volumes()

        mock_setup.assert_called_once()
        mock_detach.assert_called_once()
        mock_delete.assert_called_once()
        mock_summary.assert_called_once()
        mock_show.assert_called_once()


@patch("cost_toolkit.scripts.migration.aws_london_ebs_cleanup._detach_volume")
@patch("cost_toolkit.scripts.migration.aws_london_ebs_cleanup._print_volumes_to_delete")
@patch("cost_toolkit.scripts.migration.aws_london_ebs_cleanup.boto3")
@patch("builtins.print")
def test_cleanup_london_ebs_volumes_detach_error(_mock_print, mock_boto3, mock_print_vols, mock_detach):
    """Test EBS cleanup with detach error."""
    mock_ec2 = MagicMock()
    mock_boto3.client.return_value = mock_ec2
    mock_print_vols.return_value = 85
    mock_detach.side_effect = ClientError({"Error": {"Code": "VolumeInUse"}}, "DetachVolume")

    cleanup_london_ebs_volumes()

    mock_detach.assert_called_once()


# Tests for main
@patch("cost_toolkit.scripts.migration.aws_london_ebs_cleanup.cleanup_london_ebs_volumes")
def test_main(mock_cleanup):
    """Test main function."""
    main()
    mock_cleanup.assert_called_once()
