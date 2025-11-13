"""Comprehensive tests for aws_instance_termination.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_instance_termination import (
    _check_and_print_volumes,
    _delete_manual_volumes,
    _disable_termination_protection,
    _extract_instance_name,
    _extract_volumes,
    _perform_termination,
    _print_instance_info,
    get_instance_details,
    get_volume_details,
    terminate_instance_safely,
)


class TestExtractInstanceName:
    def test_combined(self, capsys):

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
    def test_extract_volumes_with_ebs(self):
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
        instance = {"BlockDeviceMappings": [{"DeviceName": "/dev/sda1"}]}
        volumes = _extract_volumes(instance)
        assert volumes == []


class TestGetInstanceDetails:
    def test_combined(self, capsys):

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


class TestGetVolumeDetails:
    def test_combined(self, capsys):

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


class TestPrintInstanceInfo:

    def test_print_instance_info(self, capsys):
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
    def test_check_volumes_delete_on_termination(self, capsys):
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
            assert volumes_to_delete == []
            captured = capsys.readouterr()
            assert "automatically deleted" in captured.out

    def test_check_volumes_manual_deletion_needed(self, capsys):
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


class TestDisableTerminationProtection:
    def test_disable_protection_success(self, capsys):
        mock_client = MagicMock()
        _disable_termination_protection(mock_client, "i-123")
        mock_client.modify_instance_attribute.assert_called_once_with(
            InstanceId="i-123", DisableApiTermination={"Value": False}
        )
        captured = capsys.readouterr()
        assert "Disabled termination protection" in captured.out

    def test_disable_protection_error(self, capsys):
        mock_client = MagicMock()
        mock_client.modify_instance_attribute.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "modify_instance_attribute"
        )
        _disable_termination_protection(mock_client, "i-123")
        captured = capsys.readouterr()
        assert "Termination protection check" in captured.out


class TestPerformTermination:

    def test_perform_termination_success(self, capsys):
        mock_client = MagicMock()
        mock_client.terminate_instances.return_value = {
            "TerminatingInstances": [
                {
                    "CurrentState": {"Name": "shutting-down"},
                    "PreviousState": {"Name": "running"},
                }
            ]
        }
        _perform_termination(mock_client, "i-123", "test-instance")
        mock_client.terminate_instances.assert_called_once_with(InstanceIds=["i-123"])
        captured = capsys.readouterr()
        assert "Termination initiated successfully" in captured.out
        assert "shutting-down" in captured.out


class TestDeleteManualVolumes:
    def test_combined(self, capsys):

        mock_client = MagicMock()
        with patch(
            "cost_toolkit.scripts.cleanup.aws_instance_termination.get_volume_details"
        ) as mock_get:
            mock_get.return_value = {
                "volume_id": "vol-123",
                "name": "data-volume",
                "size": 100,
            }
            _delete_manual_volumes(mock_client, ["vol-123"], "us-east-1")
            mock_client.delete_volume.assert_called_once_with(VolumeId="vol-123")
            captured = capsys.readouterr()
            assert "deletion initiated" in captured.out

        mock_client = MagicMock()
        mock_client.delete_volume.side_effect = ClientError(
            {"Error": {"Code": "InvalidVolume.NotFound"}}, "delete_volume"
        )
        with patch(
            "cost_toolkit.scripts.cleanup.aws_instance_termination.get_volume_details"
        ) as mock_get:
            mock_get.return_value = {
                "volume_id": "vol-123",
                "name": "data-volume",
                "size": 100,
            }
            _delete_manual_volumes(mock_client, ["vol-123"], "us-east-1")
            captured = capsys.readouterr()
            assert "Error deleting volume" in captured.out

        mock_client = MagicMock()
        _delete_manual_volumes(mock_client, [], "us-east-1")
        mock_client.delete_volume.assert_not_called()


class TestTerminateInstanceSafely:
    def test_terminate_success(self):
        with patch("boto3.client") as mock_client:
            with patch(
                "cost_toolkit.scripts.cleanup.aws_instance_termination.get_instance_details"
            ) as mock_get:
                with patch("time.sleep"):
                    mock_ec2 = MagicMock()
                    mock_client.return_value = mock_ec2
                    instance_info = {
                        "instance_id": "i-123",
                        "name": "test",
                        "state": "running",
                        "instance_type": "t2.micro",
                        "launch_time": "2024-01-01",
                        "availability_zone": "us-east-1a",
                        "volumes": [],
                        "region": "us-east-1",
                    }
                    mock_get.side_effect = [
                        instance_info,
                        {**instance_info, "state": "shutting-down"},
                    ]
                    mock_ec2.terminate_instances.return_value = {
                        "TerminatingInstances": [
                            {
                                "CurrentState": {"Name": "shutting-down"},
                                "PreviousState": {"Name": "running"},
                            }
                        ]
                    }
                    result = terminate_instance_safely("i-123", "us-east-1")
                    assert result is True

    def test_already_terminated(self, capsys):
        with patch("boto3.client"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_instance_termination.get_instance_details"
            ) as mock_get:
                instance_info = {
                    "instance_id": "i-123",
                    "name": "test",
                    "state": "terminated",
                    "instance_type": "t2.micro",
                    "launch_time": "2024-01-01",
                    "availability_zone": "us-east-1a",
                    "volumes": [],
                    "region": "us-east-1",
                }
                mock_get.return_value = instance_info
                result = terminate_instance_safely("i-123", "us-east-1")
                assert result is True
                captured = capsys.readouterr()
                assert "already terminated" in captured.out

    def test_instance_not_found(self):
        with patch("boto3.client"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_instance_termination.get_instance_details",
                return_value=None,
            ):
                result = terminate_instance_safely("i-notfound", "us-east-1")
                assert result is False

    def test_termination_error(self, capsys):
        with patch("boto3.client") as mock_client:
            with patch(
                "cost_toolkit.scripts.cleanup.aws_instance_termination.get_instance_details"
            ) as mock_get:
                mock_ec2 = MagicMock()
                mock_ec2.terminate_instances.side_effect = ClientError(
                    {"Error": {"Code": "ServiceError"}}, "terminate_instances"
                )
                mock_client.return_value = mock_ec2
                instance_info = {
                    "instance_id": "i-123",
                    "name": "test",
                    "state": "running",
                    "instance_type": "t2.micro",
                    "launch_time": "2024-01-01",
                    "availability_zone": "us-east-1a",
                    "volumes": [],
                    "region": "us-east-1",
                }
                mock_get.return_value = instance_info
                result = terminate_instance_safely("i-123", "us-east-1")
                assert result is False
                captured = capsys.readouterr()
                assert "Error terminating instance" in captured.out
