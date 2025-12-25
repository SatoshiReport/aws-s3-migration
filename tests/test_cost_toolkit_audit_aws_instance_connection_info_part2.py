"""Tests for cost_toolkit/scripts/audit/aws_instance_connection_info.py module - Part 2."""

# pylint: disable=too-few-public-methods

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_instance_connection_info import (
    _check_ssm_availability,
    get_instance_connection_info,
)
from tests.assertions import assert_equal
from tests.aws_instance_connection_test_utils import (
    build_instance_connection_mocks,
    run_connection_info_with_clients,
)


class TestCheckSsmAvailability:
    """Test suite for _check_ssm_availability function."""

    def test_check_ssm_availability_agent_online(self, capsys):
        """Test _check_ssm_availability with SSM agent online."""
        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.return_value = {
            "InstanceInformationList": [
                {
                    "PingStatus": "Online",
                    "LastPingDateTime": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                    "PlatformType": "Linux",
                    "PlatformVersion": "Amazon Linux 2",
                }
            ]
        }

        with patch("boto3.client", return_value=mock_ssm):
            _check_ssm_availability("i-ssm123", "us-east-1")

        captured = capsys.readouterr()
        assert "AWS SYSTEMS MANAGER:" in captured.out
        assert "SSM Agent Status: Online" in captured.out
        assert "Last Ping: 2024-01-15 10:00:00+00:00" in captured.out
        assert "Platform: Linux Amazon Linux 2" in captured.out
        assert "aws ssm start-session --target i-ssm123 --region us-east-1" in captured.out

    def test_check_ssm_availability_agent_offline(self, capsys):
        """Test _check_ssm_availability with SSM agent offline."""
        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.return_value = {"InstanceInformationList": []}

        with patch("boto3.client", return_value=mock_ssm):
            _check_ssm_availability("i-noagent", "us-west-2")

        captured = capsys.readouterr()
        assert "AWS SYSTEMS MANAGER:" in captured.out
        assert "SSM Agent not responding or not installed" in captured.out

    def test_check_ssm_availability_client_error(self, capsys):
        """Test _check_ssm_availability with ClientError."""
        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "DescribeInstanceInformation",
        )

        with patch("boto3.client", return_value=mock_ssm):
            _check_ssm_availability("i-error", "eu-central-1")

        captured = capsys.readouterr()
        assert "AWS SYSTEMS MANAGER:" in captured.out
        assert "Could not check SSM status:" in captured.out

    def test_check_ssm_availability_windows_platform(self, capsys):
        """Test _check_ssm_availability with Windows platform."""
        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.return_value = {
            "InstanceInformationList": [
                {
                    "PingStatus": "Online",
                    "LastPingDateTime": datetime(2024, 2, 1, 12, 30, 0, tzinfo=timezone.utc),
                    "PlatformType": "Windows",
                    "PlatformVersion": "Windows Server 2019",
                }
            ]
        }

        with patch("boto3.client", return_value=mock_ssm):
            _check_ssm_availability("i-windows", "us-east-2")

        captured = capsys.readouterr()
        assert "Platform: Windows Windows Server 2019" in captured.out


class TestGetInstanceConnectionInfoComplete:
    """Test suite for get_instance_connection_info - complete instance data."""

    def test_get_instance_connection_info_complete(self, capsys):
        """Test get_instance_connection_info with complete instance data."""
        mock_instance = {
            "InstanceId": "i-complete",
            "InstanceType": "t2.micro",
            "State": {"Name": "running"},
            "LaunchTime": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            "PublicIpAddress": "54.1.2.3",
            "PublicDnsName": "ec2-54-1-2-3.compute-1.amazonaws.com",
            "PrivateIpAddress": "10.0.1.10",
            "PrivateDnsName": "ip-10-0-1-10.ec2.internal",
            "VpcId": "vpc-123",
            "SubnetId": "subnet-456",
            "SecurityGroups": [{"GroupId": "sg-123", "GroupName": "default"}],
            "Tags": [
                {"Key": "Name", "Value": "test-instance"},
                {"Key": "Environment", "Value": "production"},
            ],
        }

        mock_ec2 = MagicMock()
        mock_ec2.describe_subnets.return_value = {"Subnets": [{"MapPublicIpOnLaunch": True}]}
        mock_ec2.describe_route_tables.return_value = {
            "RouteTables": [{"Routes": [{"DestinationCidrBlock": "0.0.0.0/0", "GatewayId": "igw-123"}]}]
        }

        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.return_value = {
            "InstanceInformationList": [
                {
                    "PingStatus": "Online",
                    "LastPingDateTime": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                    "PlatformType": "Linux",
                    "PlatformVersion": "Amazon Linux 2",
                }
            ]
        }

        with (
            patch(
                "cost_toolkit.scripts.audit.aws_instance_connection_info.get_instance_info",
                return_value=mock_instance,
            ),
            patch("boto3.client") as mock_boto_client,
        ):
            mock_boto_client.side_effect = [mock_ec2, mock_ssm]
            result = get_instance_connection_info("i-complete", "us-east-1")

        assert_equal(result["instance_id"], "i-complete")
        assert_equal(result["public_ip"], "54.1.2.3")
        assert_equal(result["public_dns"], "ec2-54-1-2-3.compute-1.amazonaws.com")
        assert_equal(result["private_ip"], "10.0.1.10")
        assert_equal(result["private_dns"], "ip-10-0-1-10.ec2.internal")
        assert_equal(result["has_internet_access"], True)
        assert_equal(result["state"], "running")

        captured = capsys.readouterr()
        assert "Getting connection info for instance i-complete" in captured.out
        assert "INSTANCE TAGS:" in captured.out
        assert "Name: test-instance" in captured.out
        assert "Environment: production" in captured.out


class TestGetInstanceConnectionInfoPrivate:
    """Test suite for get_instance_connection_info - private instances."""

    def test_get_instance_connection_info_no_public_access(self):
        """Test get_instance_connection_info without public access."""
        mock_instance, mock_ec2, mock_ssm = build_instance_connection_mocks()
        mock_instance.update(
            {
                "InstanceId": "i-private",
                "InstanceType": "t2.small",
                "State": {"Name": "running"},
                "LaunchTime": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "PrivateIpAddress": "10.0.2.20",
                "PrivateDnsName": "ip-10-0-2-20.ec2.internal",
                "VpcId": "vpc-private",
                "SubnetId": "subnet-private",
            }
        )

        with (
            patch(
                "cost_toolkit.scripts.audit.aws_instance_connection_info.get_instance_info",
                return_value=mock_instance,
            ),
            patch("boto3.client") as mock_boto_client,
        ):
            mock_boto_client.side_effect = [mock_ec2, mock_ssm]
            result = get_instance_connection_info("i-private", "us-west-2")

        assert_equal(result["instance_id"], "i-private")
        assert_equal(result["public_ip"], None)
        assert_equal(result["public_dns"], None)
        assert_equal(result["has_internet_access"], False)


class TestGetInstanceConnectionInfoTags:
    """Test suite for get_instance_connection_info function - tag handling."""

    def test_get_instance_connection_info_client_error(self, capsys):
        """Test get_instance_connection_info with ClientError."""
        error_response = {"Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Not found"}}
        with patch(
            "cost_toolkit.scripts.audit.aws_instance_connection_info.get_instance_info",
            side_effect=ClientError(error_response, "DescribeInstances"),
        ):
            result = get_instance_connection_info("i-notfound", "us-east-1")

        assert_equal(result, None)
        captured = capsys.readouterr()
        assert "Error getting instance info:" in captured.out

    def test_get_instance_connection_info_no_tags(self, capsys):
        """Test get_instance_connection_info with instance without tags."""
        mock_instance = {
            "InstanceId": "i-notags",
            "InstanceType": "t2.nano",
            "State": {"Name": "stopped"},
            "LaunchTime": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            "PrivateIpAddress": "10.0.3.30",
            "VpcId": "vpc-test",
            "SubnetId": "subnet-test",
            "SecurityGroups": [],
        }

        _, mock_ec2, mock_ssm = build_instance_connection_mocks()

        result = run_connection_info_with_clients(mock_instance, mock_ec2, mock_ssm, "i-notags", "ap-south-1")

        assert_equal(result["instance_id"], "i-notags")
        assert_equal(result["state"], "stopped")

        captured = capsys.readouterr()
        assert "INSTANCE TAGS:" not in captured.out

    def test_get_instance_connection_info_empty_tags(self, capsys):
        """Test get_instance_connection_info with empty tags list."""
        mock_instance = {
            "InstanceId": "i-emptytags",
            "InstanceType": "t2.micro",
            "State": {"Name": "running"},
            "LaunchTime": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            "PrivateIpAddress": "10.0.4.40",
            "VpcId": "vpc-test",
            "SubnetId": "subnet-test",
            "SecurityGroups": [],
            "Tags": [],
        }

        mock_ec2 = MagicMock()
        mock_ec2.describe_subnets.return_value = {"Subnets": [{}]}
        mock_ec2.describe_route_tables.return_value = {"RouteTables": []}

        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.return_value = {"InstanceInformationList": []}

        with (
            patch(
                "cost_toolkit.scripts.audit.aws_instance_connection_info.get_instance_info",
                return_value=mock_instance,
            ),
            patch("boto3.client") as mock_boto_client,
        ):
            mock_boto_client.side_effect = [mock_ec2, mock_ssm]
            get_instance_connection_info("i-emptytags", "us-east-1")

        captured = capsys.readouterr()
        assert "INSTANCE TAGS:" not in captured.out
