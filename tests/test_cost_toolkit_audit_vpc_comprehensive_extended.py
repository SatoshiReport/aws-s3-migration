"""Extended comprehensive tests for aws_comprehensive_vpc_audit.py - Part 1."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_comprehensive_vpc_audit import (
    _collect_vpc_endpoints,
    _print_unused_resources,
    _print_vpc_details,
    audit_vpc_resources_in_region,
)


class TestCollectVpcEndpoints:
    """Tests for _collect_vpc_endpoints function."""

    def test_collect_vpc_endpoints(self):
        """Test collecting VPC endpoints."""
        mock_client = MagicMock()
        mock_client.describe_vpc_endpoints.return_value = {
            "VpcEndpoints": [
                {
                    "VpcEndpointId": "vpce-123",
                    "ServiceName": "com.amazonaws.us-east-1.s3",
                    "VpcId": "vpc-123",
                    "State": "available",
                    "VpcEndpointType": "Gateway",
                },
                {
                    "VpcEndpointId": "vpce-456",
                    "ServiceName": "com.amazonaws.us-east-1.ec2",
                    "VpcId": "vpc-456",
                    "State": "available",
                    "VpcEndpointType": "Interface",
                },
            ]
        }

        endpoints = _collect_vpc_endpoints(mock_client)

        assert len(endpoints) == 2
        assert endpoints[0]["endpoint_id"] == "vpce-123"
        assert endpoints[0]["service_name"] == "com.amazonaws.us-east-1.s3"
        assert endpoints[0]["endpoint_type"] == "Gateway"
        assert endpoints[1]["endpoint_type"] == "Interface"

    def test_collect_vpc_endpoints_empty(self):
        """Test collecting when no VPC endpoints exist."""
        mock_client = MagicMock()
        mock_client.describe_vpc_endpoints.return_value = {"VpcEndpoints": []}

        endpoints = _collect_vpc_endpoints(mock_client)

        assert len(endpoints) == 0


class TestAuditVpcResourcesInRegion:
    """Tests for audit_vpc_resources_in_region function."""

    def test_audit_region_with_resources(self):
        """Test auditing region with VPC resources."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_vpcs.return_value = {
                "Vpcs": [
                    {
                        "VpcId": "vpc-123",
                        "CidrBlock": "10.0.0.0/16",
                        "State": "available",
                        "IsDefault": False,
                        "Tags": [{"Key": "Name", "Value": "test-vpc"}],
                    }
                ]
            }
            mock_ec2.describe_instances.return_value = {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-123",
                                "VpcId": "vpc-123",
                                "State": {"Name": "running"},
                                "Tags": [],
                            }
                        ]
                    }
                ]
            }
            mock_ec2.describe_subnets.return_value = {"Subnets": []}
            mock_ec2.describe_security_groups.return_value = {"SecurityGroups": []}
            mock_ec2.describe_route_tables.return_value = {"RouteTables": []}
            mock_ec2.describe_internet_gateways.return_value = {"InternetGateways": []}
            mock_ec2.describe_nat_gateways.return_value = {"NatGateways": []}
            mock_ec2.describe_network_interfaces.return_value = {"NetworkInterfaces": []}
            mock_ec2.describe_vpc_endpoints.return_value = {"VpcEndpoints": []}

            mock_client.return_value = mock_ec2

            result = audit_vpc_resources_in_region("us-east-1", "test-key", "test-secret")

        assert result is not None
        assert result["region"] == "us-east-1"
        assert len(result["vpcs"]) == 1
        assert result["vpcs"][0]["vpc_id"] == "vpc-123"
        assert result["vpcs"][0]["name"] == "test-vpc"
        assert result["vpcs"][0]["instance_count"] == 1

    def test_audit_region_no_vpcs(self):
        """Test auditing region with no VPCs."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_vpcs.return_value = {"Vpcs": []}
            mock_client.return_value = mock_ec2

            result = audit_vpc_resources_in_region("us-west-2", "test-key", "test-secret")

        assert result is None

    def test_audit_region_client_error(self, capsys):
        """Test error handling when auditing region."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_vpcs.side_effect = ClientError(
                {"Error": {"Code": "UnauthorizedOperation"}}, "describe_vpcs"
            )
            mock_client.return_value = mock_ec2

            result = audit_vpc_resources_in_region("eu-west-1", "test-key", "test-secret")

        assert result is None
        captured = capsys.readouterr()
        assert "Error auditing region eu-west-1" in captured.out


class TestPrintVpcDetails:
    """Tests for _print_vpc_details function."""

    def test_print_vpc_with_instances(self, capsys):
        """Test printing VPC details with instances."""
        vpc = {
            "vpc_id": "vpc-123",
            "name": "test-vpc",
            "cidr": "10.0.0.0/16",
            "is_default": False,
            "instance_count": 2,
            "instances": [
                {"instance_id": "i-123", "name": "web-server", "state": "running"},
                {"instance_id": "i-456", "name": "db-server", "state": "stopped"},
            ],
            "subnets": [{"subnet_id": "subnet-123"}],
            "security_groups": [{"group_id": "sg-123"}],
            "route_tables": [{"route_table_id": "rtb-123"}],
            "internet_gateways": [{"gateway_id": "igw-123"}],
            "nat_gateways": [],
        }

        _print_vpc_details(vpc)

        captured = capsys.readouterr()
        assert "VPC: vpc-123 (test-vpc)" in captured.out
        assert "CIDR: 10.0.0.0/16" in captured.out
        assert "Default VPC: False" in captured.out
        assert "Active instances: 2" in captured.out
        assert "i-123 (web-server) - running" in captured.out
        assert "i-456 (db-server) - stopped" in captured.out
        assert "Subnets: 1" in captured.out
        assert "Security Groups: 1" in captured.out

    def test_print_vpc_no_instances(self, capsys):
        """Test printing VPC details without instances."""
        vpc = {
            "vpc_id": "vpc-456",
            "name": "empty-vpc",
            "cidr": "172.16.0.0/16",
            "is_default": True,
            "instance_count": 0,
            "instances": [],
            "subnets": [],
            "security_groups": [],
            "route_tables": [],
            "internet_gateways": [],
            "nat_gateways": [],
        }

        _print_vpc_details(vpc)

        captured = capsys.readouterr()
        assert "VPC: vpc-456 (empty-vpc)" in captured.out
        assert "Default VPC: True" in captured.out
        assert "Active instances: 0" in captured.out


class TestPrintUnusedResources:
    """Tests for _print_unused_resources function."""

    def test_print_unused_security_groups(self, capsys):
        """Test printing unused security groups."""
        region_data = {
            "unused_security_groups": [
                {"group_id": "sg-123", "name": "unused-sg", "vpc_id": "vpc-123"},
                {"group_id": "sg-456", "name": "old-sg", "vpc_id": "vpc-456"},
            ],
            "unused_network_interfaces": [],
            "vpc_endpoints": [],
        }

        _print_unused_resources(region_data)

        captured = capsys.readouterr()
        assert "Unused Security Groups" in captured.out
        assert "sg-123 (unused-sg) in VPC vpc-123" in captured.out
        assert "sg-456 (old-sg) in VPC vpc-456" in captured.out

    def test_print_unused_network_interfaces(self, capsys):
        """Test printing unused network interfaces."""
        region_data = {
            "unused_security_groups": [],
            "unused_network_interfaces": [
                {
                    "interface_id": "eni-123",
                    "name": "orphaned-eni",
                    "private_ip": "10.0.1.5",
                }
            ],
            "vpc_endpoints": [],
        }

        _print_unused_resources(region_data)

        captured = capsys.readouterr()
        assert "Unused Network Interfaces" in captured.out
        assert "eni-123 (orphaned-eni) - 10.0.1.5" in captured.out

    def test_print_vpc_endpoints(self, capsys):
        """Test printing VPC endpoints."""
        region_data = {
            "unused_security_groups": [],
            "unused_network_interfaces": [],
            "vpc_endpoints": [
                {
                    "endpoint_id": "vpce-123",
                    "service_name": "com.amazonaws.us-east-1.s3",
                    "state": "available",
                }
            ],
        }

        _print_unused_resources(region_data)

        captured = capsys.readouterr()
        assert "VPC Endpoints" in captured.out
        assert "vpce-123 - com.amazonaws.us-east-1.s3 (available)" in captured.out
