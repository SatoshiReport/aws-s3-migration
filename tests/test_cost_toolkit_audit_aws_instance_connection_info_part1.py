"""Tests for cost_toolkit/scripts/audit/aws_instance_connection_info.py module - Part 1."""

# pylint: disable=too-few-public-methods

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from cost_toolkit.scripts.audit.aws_instance_connection_info import (
    _check_internet_gateway,
    _check_subnet_configuration,
    _print_connection_options,
    _print_instance_basic_info,
    _print_network_info,
)
from tests.assertions import assert_equal


class TestPrintInstanceBasicInfo:
    """Test suite for _print_instance_basic_info function."""

    def test_print_instance_basic_info_complete_data(self, capsys):
        """Test _print_instance_basic_info with complete instance data."""
        instance = {
            "InstanceId": "i-1234567890abcdef0",
            "InstanceType": "t2.micro",
            "State": {"Name": "running"},
            "LaunchTime": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        }

        _print_instance_basic_info(instance)

        captured = capsys.readouterr()
        assert "Instance ID: i-1234567890abcdef0" in captured.out
        assert "Instance Type: t2.micro" in captured.out
        assert "State: running" in captured.out
        assert "Launch Time: 2024-01-15 10:30:00+00:00" in captured.out

    def test_print_instance_basic_info_stopped_instance(self, capsys):
        """Test _print_instance_basic_info with stopped instance."""
        instance = {
            "InstanceId": "i-stopped123",
            "InstanceType": "t3.large",
            "State": {"Name": "stopped"},
            "LaunchTime": datetime(2024, 2, 1, 8, 0, 0, tzinfo=timezone.utc),
        }

        _print_instance_basic_info(instance)

        captured = capsys.readouterr()
        assert "Instance ID: i-stopped123" in captured.out
        assert "Instance Type: t3.large" in captured.out
        assert "State: stopped" in captured.out

    def test_print_instance_basic_info_different_instance_type(self, capsys):
        """Test _print_instance_basic_info with different instance type."""
        instance = {
            "InstanceId": "i-abcdef123",
            "InstanceType": "m5.xlarge",
            "State": {"Name": "running"},
            "LaunchTime": datetime(2024, 3, 10, 14, 45, 0, tzinfo=timezone.utc),
        }

        _print_instance_basic_info(instance)

        captured = capsys.readouterr()
        assert "Instance Type: m5.xlarge" in captured.out


class TestPrintNetworkInfo:
    """Test suite for _print_network_info function."""

    @staticmethod
    def _create_instance_with_public_ip():
        """Create mock instance data with public IP for testing."""
        return {
            "PublicIpAddress": "54.123.45.67",
            "PublicDnsName": "ec2-54-123-45-67.compute-1.amazonaws.com",
            "PrivateIpAddress": "10.0.1.100",
            "PrivateDnsName": "ip-10-0-1-100.ec2.internal",
            "VpcId": "vpc-abc123",
            "SubnetId": "subnet-def456",
            "SecurityGroups": [
                {"GroupId": "sg-123456", "GroupName": "default"},
                {"GroupId": "sg-789012", "GroupName": "web-server"},
            ],
        }

    @staticmethod
    def _assert_network_info_output(output):
        """Assert network information output contains expected fields."""
        assert "NETWORK INFORMATION:" in output
        assert "Public IP: 54.123.45.67" in output
        assert "Public DNS: ec2-54-123-45-67.compute-1.amazonaws.com" in output
        assert "Private IP: 10.0.1.100" in output
        assert "Private DNS: ip-10-0-1-100.ec2.internal" in output
        assert "VPC ID: vpc-abc123" in output
        assert "Subnet ID: subnet-def456" in output

    @staticmethod
    def _assert_security_groups_output(output):
        """Assert security groups output contains expected data."""
        assert "SECURITY GROUPS:" in output
        assert "sg-123456 (default)" in output
        assert "sg-789012 (web-server)" in output

    def test_print_network_info_with_public_ip(self, capsys):
        """Test _print_network_info with public IP address."""
        instance = self._create_instance_with_public_ip()
        _print_network_info(instance)
        captured = capsys.readouterr()
        self._assert_network_info_output(captured.out)
        self._assert_security_groups_output(captured.out)

    def test_print_network_info_no_public_ip(self, capsys):
        """Test _print_network_info without public IP address."""
        instance = {
            "PrivateIpAddress": "10.0.2.50",
            "PrivateDnsName": "ip-10-0-2-50.ec2.internal",
            "VpcId": "vpc-xyz789",
            "SubnetId": "subnet-abc123",
            "SecurityGroups": [{"GroupId": "sg-private", "GroupName": "private-sg"}],
        }

        _print_network_info(instance)

        captured = capsys.readouterr()
        assert "Public IP: None" in captured.out
        assert "Public DNS: None" in captured.out
        assert "Private IP: 10.0.2.50" in captured.out

    def test_print_network_info_no_security_groups(self, capsys):
        """Test _print_network_info with empty security groups."""
        instance = {
            "PrivateIpAddress": "10.0.3.10",
            "VpcId": "vpc-test",
            "SubnetId": "subnet-test",
            "SecurityGroups": [],
        }

        _print_network_info(instance)

        captured = capsys.readouterr()
        assert "SECURITY GROUPS:" in captured.out

    def test_print_network_info_no_private_dns(self, capsys):
        """Test _print_network_info without private DNS name."""
        instance = {
            "PublicIpAddress": "54.1.2.3",
            "PrivateIpAddress": "10.0.1.5",
            "VpcId": "vpc-123",
            "SubnetId": "subnet-456",
            "SecurityGroups": [],
        }

        _print_network_info(instance)

        captured = capsys.readouterr()
        assert "Private IP: 10.0.1.5" in captured.out


class TestCheckInternetGateway:
    """Test suite for _check_internet_gateway function."""

    def test_check_internet_gateway_with_igw(self):
        """Test _check_internet_gateway with internet gateway route."""
        route_tables = [
            {
                "Routes": [
                    {"DestinationCidrBlock": "10.0.0.0/16", "GatewayId": "local"},
                    {"DestinationCidrBlock": "0.0.0.0/0", "GatewayId": "igw-abc123"},
                ]
            }
        ]

        has_igw, gateway_id = _check_internet_gateway(route_tables)

        assert_equal(has_igw, True)
        assert_equal(gateway_id, "igw-abc123")

    def test_check_internet_gateway_no_igw(self):
        """Test _check_internet_gateway without internet gateway."""
        route_tables = [{"Routes": [{"DestinationCidrBlock": "10.0.0.0/16", "GatewayId": "local"}]}]

        has_igw, gateway_id = _check_internet_gateway(route_tables)

        assert_equal(has_igw, False)
        assert_equal(gateway_id, None)

    def test_check_internet_gateway_nat_gateway(self):
        """Test _check_internet_gateway with NAT gateway (not IGW)."""
        route_tables = [
            {
                "Routes": [
                    {"DestinationCidrBlock": "10.0.0.0/16", "GatewayId": "local"},
                    {"DestinationCidrBlock": "0.0.0.0/0", "NatGatewayId": "nat-abc123"},
                ]
            }
        ]

        has_igw, gateway_id = _check_internet_gateway(route_tables)

        assert_equal(has_igw, False)
        assert_equal(gateway_id, None)

    def test_check_internet_gateway_empty_routes(self):
        """Test _check_internet_gateway with empty routes."""
        route_tables = [{"Routes": []}]

        has_igw, gateway_id = _check_internet_gateway(route_tables)

        assert_equal(has_igw, False)
        assert_equal(gateway_id, None)

    def test_check_internet_gateway_multiple_route_tables(self):
        """Test _check_internet_gateway with multiple route tables."""
        route_tables = [
            {"Routes": [{"DestinationCidrBlock": "10.0.0.0/16", "GatewayId": "local"}]},
            {"Routes": [{"DestinationCidrBlock": "0.0.0.0/0", "GatewayId": "igw-xyz789"}]},
        ]

        has_igw, gateway_id = _check_internet_gateway(route_tables)

        assert_equal(has_igw, True)
        assert_equal(gateway_id, "igw-xyz789")

    def test_check_internet_gateway_missing_gateway_id(self):
        """Test _check_internet_gateway with missing GatewayId."""
        route_tables = [{"Routes": [{"DestinationCidrBlock": "0.0.0.0/0"}]}]

        has_igw, gateway_id = _check_internet_gateway(route_tables)

        assert_equal(has_igw, False)
        assert_equal(gateway_id, None)


class TestCheckSubnetConfiguration:
    """Test suite for _check_subnet_configuration function."""

    def test_check_subnet_configuration_with_internet_route(self, capsys):
        """Test _check_subnet_configuration with internet route."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_subnets.return_value = {"Subnets": [{"MapPublicIpOnLaunch": True}]}
        mock_ec2.describe_route_tables.return_value = {
            "RouteTables": [{"Routes": [{"DestinationCidrBlock": "0.0.0.0/0", "GatewayId": "igw-123"}]}]
        }

        result = _check_subnet_configuration(mock_ec2, "subnet-abc123")

        assert_equal(result, True)
        captured = capsys.readouterr()
        assert "SUBNET CONFIGURATION:" in captured.out
        assert "auto-assigns public IP: True" in captured.out
        assert "Internet route via: igw-123" in captured.out

    def test_check_subnet_configuration_no_internet_route(self, capsys):
        """Test _check_subnet_configuration without internet route."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_subnets.return_value = {"Subnets": [{"MapPublicIpOnLaunch": False}]}
        mock_ec2.describe_route_tables.return_value = {"RouteTables": [{"Routes": [{"DestinationCidrBlock": "10.0.0.0/16"}]}]}

        result = _check_subnet_configuration(mock_ec2, "subnet-xyz789")

        assert_equal(result, False)
        captured = capsys.readouterr()
        assert "auto-assigns public IP: False" in captured.out
        assert "Internet route: None found" in captured.out

    def test_check_subnet_configuration_no_route_tables(self, capsys):
        """Test _check_subnet_configuration with no route tables."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_subnets.return_value = {"Subnets": [{}]}
        mock_ec2.describe_route_tables.return_value = {"RouteTables": []}

        result = _check_subnet_configuration(mock_ec2, "subnet-test")

        assert_equal(result, False)
        captured = capsys.readouterr()
        assert "Internet route: None found" in captured.out

    def test_check_subnet_configuration_auto_assign_public_ip(self, capsys):
        """Test _check_subnet_configuration with auto-assign public IP enabled."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_subnets.return_value = {"Subnets": [{"MapPublicIpOnLaunch": True}]}
        mock_ec2.describe_route_tables.return_value = {"RouteTables": []}

        _check_subnet_configuration(mock_ec2, "subnet-auto")

        captured = capsys.readouterr()
        assert "auto-assigns public IP: True" in captured.out


class TestPrintConnectionOptions:
    """Test suite for _print_connection_options function."""

    def test_print_connection_options_with_public_access(self, capsys):
        """Test _print_connection_options with public IP and DNS."""
        _print_connection_options(
            "i-test123",
            "us-east-1",
            "54.1.2.3",
            "ec2-54-1-2-3.compute-1.amazonaws.com",
        )

        captured = capsys.readouterr()
        assert "CONNECTION OPTIONS:" in captured.out
        assert "Direct Internet Connection:" in captured.out
        assert "ssh -i your-key.pem ec2-user@54.1.2.3" in captured.out
        assert "ssh -i your-key.pem ec2-user@ec2-54-1-2-3.compute-1.amazonaws.com" in captured.out

    def test_print_connection_options_dns_no_ip(self, capsys):
        """Test _print_connection_options with DNS but no IP."""
        _print_connection_options("i-test456", "us-west-2", None, "ec2-test.compute-1.amazonaws.com")

        captured = capsys.readouterr()
        assert "Public DNS available but no public IP:" in captured.out
        assert "ssh -i your-key.pem ec2-user@ec2-test.compute-1.amazonaws.com" in captured.out
        assert "This may not work without a public IP" in captured.out

    def test_print_connection_options_no_public_access(self, capsys):
        """Test _print_connection_options without public access."""
        _print_connection_options("i-private789", "eu-west-1", None, None)

        captured = capsys.readouterr()
        assert "No direct internet connection available" in captured.out
        assert "Alternative connection methods:" in captured.out
        assert "AWS Systems Manager Session Manager:" in captured.out
        assert "aws ssm start-session --target i-private789 --region eu-west-1" in captured.out
        assert "VPN or Direct Connect to VPC" in captured.out
        assert "Bastion host in the same VPC" in captured.out
        assert "Re-assign a public IP (will cost $3.60/month)" in captured.out

    def test_print_connection_options_ip_no_dns(self, capsys):
        """Test _print_connection_options with IP but no DNS."""
        _print_connection_options("i-test999", "ap-southeast-1", "52.1.2.3", None)

        captured = capsys.readouterr()
        assert "No direct internet connection available" in captured.out

    def test_print_connection_options_empty_strings(self, capsys):
        """Test _print_connection_options with empty strings."""
        _print_connection_options("i-empty", "us-east-1", "", "")

        captured = capsys.readouterr()
        assert "No direct internet connection available" in captured.out
