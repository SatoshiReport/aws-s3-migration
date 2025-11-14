"""Comprehensive tests for aws_comprehensive_vpc_audit.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cost_toolkit.scripts.audit.aws_comprehensive_vpc_audit import (
    _collect_unused_network_interfaces,
    _collect_unused_security_groups,
    _collect_vpc_internet_gateways,
    _collect_vpc_nat_gateways,
    _collect_vpc_route_tables,
    _collect_vpc_security_groups,
    _collect_vpc_subnets,
    _get_active_instances,
    get_resource_name,
    load_aws_credentials,
)


class TestLoadAwsCredentials:
    """Tests for load_aws_credentials function."""

    def test_load_credentials_success(self, capsys):
        """Test successful loading of credentials."""
        with patch("os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda x: "test-secret" if "SECRET" in x else "test-key"

            key, secret = load_aws_credentials()

        assert key == "test-key"
        assert secret == "test-secret"
        captured = capsys.readouterr()
        assert "credentials loaded" in captured.out

    def test_load_credentials_missing(self):
        """Test error when credentials missing."""
        with patch("os.getenv", return_value=None):
            with pytest.raises(ValueError, match="credentials not found"):
                load_aws_credentials()


class TestGetResourceName:
    """Tests for get_resource_name function."""

    def test_get_name_from_tags(self):
        """Test extracting name from tags."""
        tags = [
            {"Key": "Name", "Value": "my-resource"},
            {"Key": "Environment", "Value": "prod"},
        ]

        name = get_resource_name(tags)

        assert name == "my-resource"

    def test_get_name_no_name_tag(self):
        """Test when Name tag missing."""
        tags = [{"Key": "Environment", "Value": "dev"}]

        name = get_resource_name(tags)

        assert name == "Unnamed"

    def test_get_name_no_tags(self):
        """Test when no tags provided."""
        name = get_resource_name(None)

        assert name == "Unnamed"


def test_get_active_instances_get_active_instances():
    """Test getting active instances."""
    mock_client = MagicMock()
    mock_client.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-123",
                        "VpcId": "vpc-123",
                        "State": {"Name": "running"},
                        "Tags": [{"Key": "Name", "Value": "web-server"}],
                    }
                ]
            }
        ]
    }

    instances = _get_active_instances(mock_client)

    assert len(instances) == 1
    assert instances[0]["instance_id"] == "i-123"
    assert instances[0]["vpc_id"] == "vpc-123"
    assert instances[0]["state"] == "running"
    assert instances[0]["name"] == "web-server"


def test_collect_vpc_subnets_collect_subnets():
    """Test collecting VPC subnets."""
    mock_client = MagicMock()
    mock_client.describe_subnets.return_value = {
        "Subnets": [
            {
                "SubnetId": "subnet-123",
                "CidrBlock": "10.0.1.0/24",
                "AvailabilityZone": "us-east-1a",
                "AvailableIpAddressCount": 250,
                "Tags": [{"Key": "Name", "Value": "public-subnet"}],
            }
        ]
    }

    subnets = _collect_vpc_subnets(mock_client, "vpc-123")

    assert len(subnets) == 1
    assert subnets[0]["subnet_id"] == "subnet-123"
    assert subnets[0]["cidr"] == "10.0.1.0/24"
    assert subnets[0]["name"] == "public-subnet"


def test_collect_vpc_security_groups_collect_security_groups():
    """Test collecting VPC security groups."""
    mock_client = MagicMock()
    mock_client.describe_security_groups.return_value = {
        "SecurityGroups": [
            {
                "GroupId": "sg-123",
                "GroupName": "default",
                "Description": "Default security group",
            },
            {
                "GroupId": "sg-456",
                "GroupName": "web-sg",
                "Description": "Web server security group",
            },
        ]
    }

    sgs = _collect_vpc_security_groups(mock_client, "vpc-123")

    assert len(sgs) == 2
    assert sgs[0]["is_default"] is True
    assert sgs[1]["is_default"] is False


def test_collect_vpc_route_tables_collect_route_tables():
    """Test collecting VPC route tables."""
    mock_client = MagicMock()
    mock_client.describe_route_tables.return_value = {
        "RouteTables": [
            {
                "RouteTableId": "rtb-123",
                "Associations": [{"Main": True}],
                "Routes": [{"DestinationCidrBlock": "0.0.0.0/0"}],
                "Tags": [{"Key": "Name", "Value": "main-rt"}],
            }
        ]
    }

    route_tables = _collect_vpc_route_tables(mock_client, "vpc-123")

    assert len(route_tables) == 1
    assert route_tables[0]["route_table_id"] == "rtb-123"
    assert route_tables[0]["is_main"] is True
    assert route_tables[0]["routes"] == 1


class TestCollectVpcInternetGateways:
    """Tests for _collect_vpc_internet_gateways function."""

    def test_collect_internet_gateways(self):
        """Test collecting internet gateways."""
        mock_client = MagicMock()
        mock_client.describe_internet_gateways.return_value = {
            "InternetGateways": [
                {
                    "InternetGatewayId": "igw-123",
                    "Attachments": [{"State": "attached", "VpcId": "vpc-123"}],
                    "Tags": [{"Key": "Name", "Value": "main-igw"}],
                }
            ]
        }

        igws = _collect_vpc_internet_gateways(mock_client, "vpc-123")

        assert len(igws) == 1
        assert igws[0]["gateway_id"] == "igw-123"
        assert igws[0]["state"] == "attached"
        assert igws[0]["name"] == "main-igw"

    def test_collect_internet_gateways_detached(self):
        """Test collecting detached internet gateways."""
        mock_client = MagicMock()
        mock_client.describe_internet_gateways.return_value = {
            "InternetGateways": [
                {
                    "InternetGatewayId": "igw-456",
                    "Attachments": [],
                    "Tags": [],
                }
            ]
        }

        igws = _collect_vpc_internet_gateways(mock_client, "vpc-123")

        assert len(igws) == 1
        assert igws[0]["state"] == "detached"


def test_collect_vpc_nat_gateways_collect_nat_gateways():
    """Test collecting NAT gateways."""
    mock_client = MagicMock()
    mock_client.describe_nat_gateways.return_value = {
        "NatGateways": [
            {
                "NatGatewayId": "nat-123",
                "State": "available",
                "SubnetId": "subnet-123",
                "Tags": [{"Key": "Name", "Value": "public-nat"}],
            }
        ]
    }

    nat_gateways = _collect_vpc_nat_gateways(mock_client, "vpc-123")

    assert len(nat_gateways) == 1
    assert nat_gateways[0]["nat_gateway_id"] == "nat-123"
    assert nat_gateways[0]["state"] == "available"
    assert nat_gateways[0]["subnet_id"] == "subnet-123"


def test_collect_unused_security_groups_collect_unused_groups():
    """Test collecting unused security groups."""
    mock_client = MagicMock()
    mock_client.describe_security_groups.return_value = {
        "SecurityGroups": [
            {
                "GroupId": "sg-unused",
                "GroupName": "unused-sg",
                "Description": "Unused security group",
                "VpcId": "vpc-123",
            },
            {
                "GroupId": "sg-default",
                "GroupName": "default",
                "Description": "Default security group",
                "VpcId": "vpc-123",
            },
        ]
    }

    # First call for all SGs, second for checking instances per SG
    mock_client.describe_instances.side_effect = [
        {"Reservations": []},  # No instances for sg-unused
        {"Reservations": []},  # No instances for default (but it's skipped)
    ]

    unused_sgs = _collect_unused_security_groups(mock_client)

    assert len(unused_sgs) == 1
    assert unused_sgs[0]["group_id"] == "sg-unused"


def test_collect_unused_network_interfaces_collect_unused_interfaces():
    """Test collecting unattached network interfaces."""
    mock_client = MagicMock()
    mock_client.describe_network_interfaces.return_value = {
        "NetworkInterfaces": [
            {
                "NetworkInterfaceId": "eni-123",
                "VpcId": "vpc-123",
                "SubnetId": "subnet-123",
                "PrivateIpAddress": "10.0.1.10",
                "TagSet": [{"Key": "Name", "Value": "unused-eni"}],
                # No Attachment
            },
            {
                "NetworkInterfaceId": "eni-456",
                "VpcId": "vpc-123",
                "SubnetId": "subnet-123",
                "PrivateIpAddress": "10.0.1.20",
                "TagSet": [],
                "Attachment": {"InstanceId": "i-123"},
            },
        ]
    }

    unused_enis = _collect_unused_network_interfaces(mock_client)

    assert len(unused_enis) == 1
    assert unused_enis[0]["interface_id"] == "eni-123"
    assert unused_enis[0]["name"] == "unused-eni"
