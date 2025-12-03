"""Shared helpers for EC2 instance cleanup tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from botocore.exceptions import ClientError


def build_describe_not_found_client():
    """Return boto3.client mock that raises InvalidInstanceID.NotFound."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.side_effect = ClientError(
        {"Error": {"Code": "InvalidInstanceID.NotFound"}}, "describe_instances"
    )
    return mock_ec2


def build_describe_empty_client():
    """Return boto3.client mock that yields empty reservations."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {"Reservations": []}
    return mock_ec2


INSTANCE_WITH_VOLUMES = {
    "BlockDeviceMappings": [
        {
            "DeviceName": "/dev/xvda",
            "Ebs": {"VolumeId": "vol-123", "DeleteOnTermination": True},
        },
        {
            "DeviceName": "/dev/xvdb",
            "Ebs": {"VolumeId": "vol-456", "DeleteOnTermination": False},
        },
    ]
}


def assert_standard_volumes(volumes):
    """Assert standard volume list shape used in tests."""
    assert len(volumes) == 2
    assert volumes[0]["volume_id"] == "vol-123"
    assert volumes[0]["delete_on_termination"] is True
    assert volumes[1]["volume_id"] == "vol-456"
    assert volumes[1]["delete_on_termination"] is False
