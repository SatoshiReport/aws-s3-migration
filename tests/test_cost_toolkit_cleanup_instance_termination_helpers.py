"""Tests for instance termination helper operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_instance_termination import (
    _check_and_print_volumes,
    _delete_manual_volumes,
    _disable_termination_protection,
    _extract_instance_name,
    _extract_volumes,
    _perform_termination,
)


class TestDisableTerminationProtection:
    """Test disabling termination protection on instances."""

    def test_disable_protection_success(self, capsys):
        """Test successful disabling of termination protection."""
        mock_client = MagicMock()
        _disable_termination_protection(mock_client, "i-123")
        mock_client.modify_instance_attribute.assert_called_once_with(
            InstanceId="i-123", DisableApiTermination={"Value": False}
        )
        captured = capsys.readouterr()
        assert "Disabled termination protection" in captured.out

    def test_disable_protection_error(self, capsys):
        """Test error handling when disabling termination protection."""
        mock_client = MagicMock()
        mock_client.modify_instance_attribute.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "modify_instance_attribute"
        )
        _disable_termination_protection(mock_client, "i-123")
        captured = capsys.readouterr()
        assert "Termination protection check" in captured.out


def test_perform_termination_perform_termination_success(capsys):
    """Test successful instance termination."""
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


def test_delete_manual_volumes_combined(capsys):
    """Test manual volume deletion in various scenarios."""

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


class TestExtractHelpers:
    """Test helper extraction functions."""

    def test_extract_instance_name_with_name_tag(self):
        """Test extracting instance name when Name tag exists."""
        instance = {
            "Tags": [{"Key": "Name", "Value": "MyInstance"}, {"Key": "Env", "Value": "prod"}]
        }
        name = _extract_instance_name(instance)
        assert name == "MyInstance"

    def test_extract_instance_name_without_name_tag(self):
        """Test extracting instance name when Name tag doesn't exist."""
        instance = {"Tags": [{"Key": "Env", "Value": "prod"}]}
        name = _extract_instance_name(instance)
        assert name == "Unnamed"

    def test_extract_instance_name_no_tags(self):
        """Test extracting instance name when no tags exist."""
        instance = {}
        name = _extract_instance_name(instance)
        assert name == "Unnamed"

    def test_extract_volumes_with_multiple_volumes(self):
        """Test extracting volumes from instance with multiple volumes."""
        instance = {
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {"VolumeId": "vol-123", "DeleteOnTermination": True},
                },
                {
                    "DeviceName": "/dev/sdb",
                    "Ebs": {"VolumeId": "vol-456", "DeleteOnTermination": False},
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
        """Test extracting volumes when no EBS volumes exist."""
        instance = {"BlockDeviceMappings": [{"DeviceName": "/dev/sda1"}]}
        volumes = _extract_volumes(instance)
        assert len(volumes) == 0

    def test_extract_volumes_empty_mappings(self):
        """Test extracting volumes when BlockDeviceMappings is empty."""
        instance = {}
        volumes = _extract_volumes(instance)
        assert len(volumes) == 0


class TestCheckAndPrintVolumes:
    """Test _check_and_print_volumes function."""

    def test_check_and_print_volumes_with_manual_delete(self, capsys):
        """Test volume checking with volumes requiring manual deletion."""
        instance_info = {
            "volumes": [
                {
                    "volume_id": "vol-123",
                    "device": "/dev/sda1",
                    "delete_on_termination": False,
                }
            ]
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_instance_termination.get_volume_details"
        ) as mock_get:
            mock_get.return_value = {
                "volume_id": "vol-123",
                "name": "DataVolume",
                "size": 100,
            }

            volumes_to_delete = _check_and_print_volumes(instance_info, "us-east-1")

            assert len(volumes_to_delete) == 1
            assert "vol-123" in volumes_to_delete

            captured = capsys.readouterr()
            assert "manual deletion needed" in captured.out

    def test_check_and_print_volumes_auto_delete(self, capsys):
        """Test volume checking with volumes that auto-delete."""
        instance_info = {
            "volumes": [
                {
                    "volume_id": "vol-456",
                    "device": "/dev/sda1",
                    "delete_on_termination": True,
                }
            ]
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_instance_termination.get_volume_details"
        ) as mock_get:
            mock_get.return_value = {
                "volume_id": "vol-456",
                "name": "RootVolume",
                "size": 30,
            }

            volumes_to_delete = _check_and_print_volumes(instance_info, "us-east-1")

            assert len(volumes_to_delete) == 0

            captured = capsys.readouterr()
            assert "automatically deleted" in captured.out
