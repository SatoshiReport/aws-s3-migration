"""Tests for instance termination helper functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_instance_termination import (
    _check_and_print_volumes,
    _extract_instance_name,
    _extract_volumes,
    _print_instance_info,
    get_instance_details,
    get_volume_details,
)


def test_extract_instance_name_combined():
    """Test extracting instance name from tags in various scenarios."""

    instance = {
        "Tags": [
            {"Key": "Name", "Value": "my-instance"},
            {"Key": "Environment", "Value": "prod"},
        ]
    }
    name = _extract_instance_name(instance)
    assert name == "my-instance"

    instance = {"Tags": []}
    name = _extract_instance_name(instance)
    assert name == "Unnamed"

    instance = {"Tags": [{"Key": "Environment", "Value": "dev"}]}
    name = _extract_instance_name(instance)
    assert name == "Unnamed"


class TestExtractVolumes:
    """Test volume extraction from instance block device mappings."""

    def test_extract_volumes_with_ebs(self):
        """Test extracting volumes with EBS mappings."""
        instance = {
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {
                        "VolumeId": "vol-123",
                        "DeleteOnTermination": True,
                    },
                },
                {
                    "DeviceName": "/dev/sdb",
                    "Ebs": {
                        "VolumeId": "vol-456",
                        "DeleteOnTermination": False,
                    },
                },
            ]
        }
        volumes = _extract_volumes(instance)
        assert len(volumes) == 2
        assert volumes[0]["volume_id"] == "vol-123"
        assert volumes[0]["delete_on_termination"] is True
        assert volumes[1]["volume_id"] == "vol-456"
        assert volumes[1]["delete_on_termination"] is False

    def test_extract_volumes_no_ebs(self):
        """Test extracting volumes when no EBS volumes present."""
        instance = {"BlockDeviceMappings": [{"DeviceName": "/dev/sda1"}]}
        volumes = _extract_volumes(instance)
        assert not volumes


def test_get_instance_details_combined(capsys):
    """Test getting instance details in various scenarios."""

    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-123",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                            "State": {"Name": "running"},
                            "InstanceType": "t2.micro",
                            "LaunchTime": "2024-01-01",
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "BlockDeviceMappings": [],
                        }
                    ]
                }
            ]
        }
        mock_client.return_value = mock_ec2
        result = get_instance_details("i-123", "us-east-1")
        assert result is not None
        assert result["instance_id"] == "i-123"
        assert result["name"] == "test-instance"
        assert result["state"] == "running"
        assert result["region"] == "us-east-1"

    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.side_effect = ClientError(
            {"Error": {"Code": "InvalidInstanceID.NotFound"}}, "describe_instances"
        )
        mock_client.return_value = mock_ec2
        result = get_instance_details("i-notfound", "us-east-1")
        assert result is None
        captured = capsys.readouterr()
        assert "Error getting instance details" in captured.out

    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {"Reservations": []}
        mock_client.return_value = mock_ec2
        result = get_instance_details("i-123", "us-east-1")
        assert result is None


def test_get_volume_details_combined(capsys):
    """Test getting volume details in various scenarios."""

    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_volumes.return_value = {
            "Volumes": [
                {
                    "VolumeId": "vol-123",
                    "Tags": [{"Key": "Name", "Value": "test-volume"}],
                    "Size": 100,
                    "VolumeType": "gp3",
                    "State": "available",
                    "Encrypted": True,
                }
            ]
        }
        mock_client.return_value = mock_ec2
        result = get_volume_details("vol-123", "us-east-1")
        assert result is not None
        assert result["volume_id"] == "vol-123"
        assert result["name"] == "test-volume"
        assert result["size"] == 100
        assert result["encrypted"] is True

    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_volumes.return_value = {
            "Volumes": [
                {
                    "VolumeId": "vol-123",
                    "Tags": [],
                    "Size": 50,
                    "VolumeType": "gp2",
                    "State": "in-use",
                    "Encrypted": False,
                }
            ]
        }
        mock_client.return_value = mock_ec2
        result = get_volume_details("vol-123", "us-east-1")
        assert result["name"] == "Unnamed"

    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_volumes.side_effect = ClientError(
            {"Error": {"Code": "InvalidVolume.NotFound"}}, "describe_volumes"
        )
        mock_client.return_value = mock_ec2
        result = get_volume_details("vol-notfound", "us-east-1")
        assert result is None
        captured = capsys.readouterr()
        assert "Error getting volume details" in captured.out


def test_print_instance_info_print_instance_info(capsys):
    """Test printing instance information to console."""
    instance_info = {
        "instance_id": "i-123",
        "name": "test-instance",
        "instance_type": "t2.micro",
        "state": "running",
        "launch_time": "2024-01-01",
    }
    _print_instance_info(instance_info, "us-east-1")
    captured = capsys.readouterr()
    assert "i-123" in captured.out
    assert "test-instance" in captured.out
    assert "t2.micro" in captured.out
    assert "us-east-1" in captured.out


class TestCheckAndPrintVolumes:
    """Test checking and printing volume information."""

    def test_check_volumes_delete_on_termination(self, capsys):
        """Test checking volumes with delete on termination enabled."""
        instance_info = {
            "volumes": [
                {
                    "volume_id": "vol-123",
                    "device": "/dev/sda1",
                    "delete_on_termination": True,
                }
            ]
        }
        with patch(
            "cost_toolkit.scripts.cleanup.aws_instance_termination.get_volume_details"
        ) as mock_get:
            mock_get.return_value = {
                "volume_id": "vol-123",
                "name": "root",
                "size": 100,
            }
            volumes_to_delete = _check_and_print_volumes(instance_info, "us-east-1")
            assert not volumes_to_delete
            captured = capsys.readouterr()
            assert "automatically deleted" in captured.out

    def test_check_volumes_manual_deletion_needed(self, capsys):
        """Test checking volumes that require manual deletion."""
        instance_info = {
            "volumes": [
                {
                    "volume_id": "vol-456",
                    "device": "/dev/sdb",
                    "delete_on_termination": False,
                }
            ]
        }
        with patch(
            "cost_toolkit.scripts.cleanup.aws_instance_termination.get_volume_details"
        ) as mock_get:
            mock_get.return_value = {
                "volume_id": "vol-456",
                "name": "data",
                "size": 200,
            }
            volumes_to_delete = _check_and_print_volumes(instance_info, "us-east-1")
            assert volumes_to_delete == ["vol-456"]
            captured = capsys.readouterr()
            assert "manual deletion needed" in captured.out
