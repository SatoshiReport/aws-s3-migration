"""Tests for cost_toolkit/scripts/audit/aws_instance_connection_info.py module - Part 3."""

# pylint: disable=too-few-public-methods

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.audit.aws_instance_connection_info import (
    get_instance_connection_info,
    main,
)
from tests.assertions import assert_equal


class TestMainPublicConnectivity:
    """Test suite for main function - public connectivity cases."""

    def test_main_with_public_connectivity(self, capsys):
        """Test main function with instance having public connectivity."""
        mock_instance_info = {
            "instance_id": "i-00c39b1ba0eba3e2d",
            "public_ip": "54.1.2.3",
            "public_dns": "ec2-54-1-2-3.compute-1.amazonaws.com",
            "private_ip": "10.0.1.100",
            "private_dns": "ip-10-0-1-100.ec2.internal",
            "has_internet_access": True,
            "state": "running",
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_instance_connection_info.get_instance_connection_info",
            return_value=mock_instance_info,
        ):
            main()

        captured = capsys.readouterr()
        assert "AWS Instance Connection Information" in captured.out
        assert "SUMMARY" in captured.out
        assert "Instance has public connectivity" in captured.out
        assert "Primary connection: ec2-54-1-2-3.compute-1.amazonaws.com" in captured.out
        assert "IP address: 54.1.2.3" in captured.out

    def test_main_without_public_connectivity(self, capsys):
        """Test main function with instance without public connectivity."""
        mock_instance_info = {
            "instance_id": "i-00c39b1ba0eba3e2d",
            "public_ip": None,
            "public_dns": None,
            "private_ip": "10.0.1.100",
            "private_dns": "ip-10-0-1-100.ec2.internal",
            "has_internet_access": False,
            "state": "running",
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_instance_connection_info.get_instance_connection_info",
            return_value=mock_instance_info,
        ):
            main()

        captured = capsys.readouterr()
        assert "SUMMARY" in captured.out
        assert "Instance has no public connectivity" in captured.out
        assert "Use AWS Systems Manager Session Manager for access" in captured.out
        assert (
            "aws ssm start-session --target i-00c39b1ba0eba3e2d --region us-east-2" in captured.out
        )

    def test_main_with_public_dns_only(self, capsys):
        """Test main function with public DNS but no IP."""
        mock_instance_info = {
            "instance_id": "i-00c39b1ba0eba3e2d",
            "public_ip": None,
            "public_dns": "ec2-test.amazonaws.com",
            "private_ip": "10.0.1.100",
            "private_dns": "ip-10-0-1-100.ec2.internal",
            "has_internet_access": True,
            "state": "running",
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_instance_connection_info.get_instance_connection_info",
            return_value=mock_instance_info,
        ):
            main()

        captured = capsys.readouterr()
        assert "Instance has public connectivity" in captured.out
        assert "Primary connection: ec2-test.amazonaws.com" in captured.out

    def test_main_with_public_ip_only(self, capsys):
        """Test main function with public IP but no DNS."""
        mock_instance_info = {
            "instance_id": "i-00c39b1ba0eba3e2d",
            "public_ip": "54.5.6.7",
            "public_dns": None,
            "private_ip": "10.0.1.100",
            "private_dns": "ip-10-0-1-100.ec2.internal",
            "has_internet_access": True,
            "state": "running",
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_instance_connection_info.get_instance_connection_info",
            return_value=mock_instance_info,
        ):
            main()

        captured = capsys.readouterr()
        assert "Instance has public connectivity" in captured.out
        assert "IP address: 54.5.6.7" in captured.out


class TestMainEdgeCases:
    """Test suite for main function - edge cases."""

    def test_main_get_instance_connection_info_returns_none(self, capsys):
        """Test main function when get_instance_connection_info returns None."""
        with patch(
            "cost_toolkit.scripts.audit.aws_instance_connection_info.get_instance_connection_info",
            return_value=None,
        ):
            main()

        captured = capsys.readouterr()
        assert "AWS Instance Connection Information" in captured.out
        assert "SUMMARY" not in captured.out

    def test_main_header_displayed(self, capsys):
        """Test main function displays proper header."""
        with patch(
            "cost_toolkit.scripts.audit.aws_instance_connection_info.get_instance_connection_info",
            return_value=None,
        ):
            main()

        captured = capsys.readouterr()
        assert "AWS Instance Connection Information" in captured.out
        assert "=" * 80 in captured.out


class TestGetInstanceConnectionInfoPartialData:
    """Test suite for get_instance_connection_info - partial data cases."""

    def test_get_instance_connection_info_partial_network_data(self):
        """Test get_instance_connection_info with partial network data."""
        mock_instance = {
            "InstanceId": "i-partial",
            "InstanceType": "t3.micro",
            "State": {"Name": "running"},
            "LaunchTime": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            "VpcId": "vpc-123",
            "SubnetId": "subnet-123",
            "SecurityGroups": [],
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
            result = get_instance_connection_info("i-partial", "us-east-1")

        assert result is not None
        assert_equal(result["public_ip"], None)
        assert_equal(result["private_ip"], None)

    def test_get_instance_connection_info_different_regions(self):
        """Test get_instance_connection_info with various AWS regions."""
        mock_instance = {
            "InstanceId": "i-region-test",
            "InstanceType": "t2.micro",
            "State": {"Name": "running"},
            "LaunchTime": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            "VpcId": "vpc-eu",
            "SubnetId": "subnet-eu",
            "SecurityGroups": [],
        }

        mock_ec2 = MagicMock()
        mock_ec2.describe_subnets.return_value = {"Subnets": [{}]}
        mock_ec2.describe_route_tables.return_value = {"RouteTables": []}

        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.return_value = {"InstanceInformationList": []}

        regions = ["eu-west-1", "ap-southeast-1", "us-west-2", "ca-central-1"]
        for region in regions:
            with (
                patch(
                    "cost_toolkit.scripts.audit.aws_instance_connection_info.get_instance_info",
                    return_value=mock_instance,
                ),
                patch("boto3.client") as mock_boto_client,
            ):
                mock_boto_client.side_effect = [mock_ec2, mock_ssm]
                result = get_instance_connection_info("i-region-test", region)

            assert result is not None
            assert_equal(result["instance_id"], "i-region-test")


class TestGetInstanceConnectionInfoSecurityGroups:
    """Test suite for get_instance_connection_info - security group cases."""

    def test_get_instance_connection_info_multiple_security_groups(self, capsys):
        """Test get_instance_connection_info with multiple security groups."""
        mock_instance = {
            "InstanceId": "i-multisg",
            "InstanceType": "t2.micro",
            "State": {"Name": "running"},
            "LaunchTime": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            "VpcId": "vpc-123",
            "SubnetId": "subnet-123",
            "SecurityGroups": [
                {"GroupId": "sg-1", "GroupName": "web"},
                {"GroupId": "sg-2", "GroupName": "app"},
                {"GroupId": "sg-3", "GroupName": "db"},
            ],
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
            get_instance_connection_info("i-multisg", "us-east-1")

        captured = capsys.readouterr()
        assert "sg-1 (web)" in captured.out
        assert "sg-2 (app)" in captured.out
        assert "sg-3 (db)" in captured.out
