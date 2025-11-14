"""Comprehensive tests for aws_stopped_instance_cleanup.py - helper functions."""

from __future__ import annotations

from unittest.mock import patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup import (
    _analyze_instances,
    _get_stopped_instances,
    _print_instance_details,
    _print_termination_summary,
    _terminate_all_instances,
    get_instance_details,
)


class TestGetInstanceDetails:
    """Tests for get_instance_details function."""

    def test_get_instance_details_success(self):
        """Test successful retrieval of instance details."""
        mock_instance = {
            "Tags": [{"Key": "Name", "Value": "test-instance"}],
            "InstanceType": "t2.micro",
            "State": {"Name": "stopped"},
            "VpcId": "vpc-123",
            "SubnetId": "subnet-456",
            "PrivateIpAddress": "10.0.0.1",
            "PublicIpAddress": "1.2.3.4",
            "LaunchTime": "2024-01-01",
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {
                        "VolumeId": "vol-123",
                        "DeleteOnTermination": True,
                    },
                }
            ],
            "SecurityGroups": [{"GroupId": "sg-123"}],
            "NetworkInterfaces": [{"NetworkInterfaceId": "eni-123"}],
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.describe_instance",
            return_value=mock_instance,
        ):
            result = get_instance_details("us-east-1", "i-123", "key", "secret")
        assert result is not None
        assert result["instance_id"] == "i-123"
        assert result["name"] == "test-instance"
        assert result["instance_type"] == "t2.micro"
        assert result["state"] == "stopped"
        assert len(result["volumes"]) == 1
        assert result["volumes"][0]["volume_id"] == "vol-123"

    def test_get_instance_details_no_name_tag(self):
        """Test instance without Name tag."""
        mock_instance = {
            "Tags": [],
            "InstanceType": "t2.small",
            "State": {"Name": "running"},
            "BlockDeviceMappings": [],
            "SecurityGroups": [],
            "NetworkInterfaces": [],
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.describe_instance",
            return_value=mock_instance,
        ):
            result = get_instance_details("us-east-1", "i-123", "key", "secret")
        assert result["name"] == "No Name"

    def test_get_instance_details_error(self, capsys):
        """Test error when retrieving instance details."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.describe_instance"
        ) as mock_describe:
            mock_describe.side_effect = ClientError(
                {"Error": {"Code": "InvalidInstanceID.NotFound"}}, "describe_instances"
            )
            result = get_instance_details("us-east-1", "i-notfound", "key", "secret")
        assert result is None
        captured = capsys.readouterr()
        assert "Error getting instance details" in captured.out

    def test_get_instance_details_multiple_volumes(self):
        """Test instance with multiple volumes."""
        mock_instance = {
            "Tags": [{"Key": "Name", "Value": "multi-volume"}],
            "InstanceType": "m5.large",
            "State": {"Name": "stopped"},
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {"VolumeId": "vol-1", "DeleteOnTermination": True},
                },
                {
                    "DeviceName": "/dev/sdb",
                    "Ebs": {"VolumeId": "vol-2", "DeleteOnTermination": False},
                },
            ],
            "SecurityGroups": [],
            "NetworkInterfaces": [],
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.describe_instance",
            return_value=mock_instance,
        ):
            result = get_instance_details("us-east-1", "i-123", "key", "secret")
        assert len(result["volumes"]) == 2
        assert result["volumes"][0]["delete_on_termination"] is True
        assert result["volumes"][1]["delete_on_termination"] is False


def test_get_stopped_instances_returns_list_of_instances():
    """Test that function returns expected list."""
    instances = _get_stopped_instances()

    assert isinstance(instances, list)
    assert len(instances) > 0
    for instance in instances:
        assert "region" in instance
        assert "instance_id" in instance
        assert "type" in instance


def test_print_instance_details_print_details_with_volumes(capsys):
    """Test printing instance details with volumes."""
    details = {
        "name": "test-instance",
        "instance_type": "t2.micro",
        "state": "stopped",
        "vpc_id": "vpc-123",
        "launch_time": "2024-01-01",
        "volumes": [
            {
                "volume_id": "vol-1",
                "device_name": "/dev/sda1",
                "delete_on_termination": True,
            },
            {
                "volume_id": "vol-2",
                "device_name": "/dev/sdb",
                "delete_on_termination": False,
            },
        ],
        "network_interfaces": ["eni-1", "eni-2"],
    }

    _print_instance_details(details)

    captured = capsys.readouterr()
    assert "test-instance" in captured.out
    assert "t2.micro" in captured.out
    assert "stopped" in captured.out
    assert "vol-1" in captured.out
    assert "will be deleted" in captured.out
    assert "vol-2" in captured.out
    assert "will be preserved" in captured.out


class TestAnalyzeInstances:
    """Tests for _analyze_instances function."""

    def test_analyze_multiple_instances(self, capsys):
        """Test analyzing multiple instances."""
        stopped_instances = [
            {"region": "us-east-1", "instance_id": "i-1", "type": "t2.micro"},
            {"region": "us-east-2", "instance_id": "i-2", "type": "t2.small"},
        ]

        mock_details = {
            "instance_id": "i-1",
            "name": "test",
            "instance_type": "t2.micro",
            "state": "stopped",
            "vpc_id": "vpc-123",
            "launch_time": "2024-01-01",
            "volumes": [],
            "network_interfaces": [],
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.get_instance_details",
            return_value=mock_details,
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup._print_instance_details"
            ):
                result = _analyze_instances(stopped_instances, "key", "secret")

        assert len(result) == 2
        captured = capsys.readouterr()
        assert "Analyzing instance" in captured.out

    def test_analyze_instances_with_failures(self):
        """Test analyzing with some failures."""
        stopped_instances = [
            {"region": "us-east-1", "instance_id": "i-1", "type": "t2.micro"},
            {"region": "us-east-2", "instance_id": "i-2", "type": "t2.small"},
        ]

        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.get_instance_details",
            side_effect=[
                {"instance_id": "i-1", "name": "test", "volumes": [], "network_interfaces": []},
                None,
            ],
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup._print_instance_details"
            ):
                result = _analyze_instances(stopped_instances, "key", "secret")

        assert len(result) == 1


class TestTerminateAllInstances:
    """Tests for _terminate_all_instances function."""

    def test_terminate_all_successful(self):
        """Test successful termination of all instances."""
        instance_details = [
            {
                "region": "us-east-1",
                "details": {"instance_id": "i-1", "name": "test-1"},
            },
            {
                "region": "us-east-2",
                "details": {"instance_id": "i-2", "name": "test-2"},
            },
        ]

        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.terminate_instance",
            return_value=True,
        ):
            terminated, failed = _terminate_all_instances(instance_details, "key", "secret")

        assert len(terminated) == 2
        assert len(failed) == 0

    def test_terminate_partial_failures(self):
        """Test termination with some failures."""
        instance_details = [
            {
                "region": "us-east-1",
                "details": {"instance_id": "i-1", "name": "test-1"},
            },
            {
                "region": "us-east-2",
                "details": {"instance_id": "i-2", "name": "test-2"},
            },
        ]

        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.terminate_instance",
            side_effect=[True, False],
        ):
            terminated, failed = _terminate_all_instances(instance_details, "key", "secret")

        assert len(terminated) == 1
        assert len(failed) == 1

    def test_terminate_all_failures(self):
        """Test when all terminations fail."""
        instance_details = [
            {
                "region": "us-east-1",
                "details": {"instance_id": "i-1", "name": "test-1"},
            },
        ]

        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.terminate_instance",
            return_value=False,
        ):
            terminated, failed = _terminate_all_instances(instance_details, "key", "secret")

        assert len(terminated) == 0
        assert len(failed) == 1


class TestPrintTerminationSummary:
    """Tests for _print_termination_summary function."""

    def test_print_summary_all_successful(self, capsys):
        """Test summary with all successful terminations."""
        terminated = [
            {
                "region": "us-east-1",
                "details": {
                    "instance_id": "i-1",
                    "name": "test-1",
                    "instance_type": "t2.micro",
                },
            },
            {
                "region": "us-east-2",
                "details": {
                    "instance_id": "i-2",
                    "name": "test-2",
                    "instance_type": "t2.small",
                },
            },
        ]
        failed = []

        _print_termination_summary(terminated, failed)

        captured = capsys.readouterr()
        assert "INSTANCE TERMINATION SUMMARY" in captured.out
        assert "Successfully terminated: 2" in captured.out
        assert "Failed terminations: 0" in captured.out
        assert "i-1" in captured.out
        assert "i-2" in captured.out

    def test_print_summary_with_failures(self, capsys):
        """Test summary with some failures."""
        terminated = [
            {
                "region": "us-east-1",
                "details": {
                    "instance_id": "i-1",
                    "name": "test-1",
                    "instance_type": "t2.micro",
                },
            },
        ]
        failed = [
            {
                "region": "us-east-2",
                "details": {
                    "instance_id": "i-2",
                    "name": "test-2",
                    "instance_type": "t2.small",
                },
            },
        ]

        _print_termination_summary(terminated, failed)

        captured = capsys.readouterr()
        assert "Successfully terminated: 1" in captured.out
        assert "Failed terminations: 1" in captured.out
        assert "Failed terminations:" in captured.out

    def test_print_summary_no_terminations(self, capsys):
        """Test summary with no terminations."""
        _print_termination_summary([], [])

        captured = capsys.readouterr()
        assert "Successfully terminated: 0" in captured.out
