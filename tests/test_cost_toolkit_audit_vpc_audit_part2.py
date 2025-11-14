"""Comprehensive tests for aws_vpc_audit.py - Part 2 (Error Handling)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_vpc_audit import (
    audit_nat_gateways_in_region,
    main,
)


class TestAuditNatGatewaysInRegion:
    """Tests for audit_nat_gateways_in_region function."""

    def _assert_nat_gateway_success_output(self, capsys):
        """Helper to assert output for successful NAT gateway audit."""
        captured = capsys.readouterr()
        assert "NAT Gateway: nat-123" in captured.out
        assert "State: available" in captured.out
        assert "VPC: vpc-123" in captured.out
        assert "Estimated monthly cost: $32.40" in captured.out
        assert "Tags:" in captured.out
        assert "Name: prod-nat" in captured.out

    def _assert_nat_gateway_result(self, result):
        """Helper to assert NAT gateway result structure."""
        assert len(result) == 1
        assert result[0]["nat_gateway_id"] == "nat-123"
        assert result[0]["state"] == "available"
        assert result[0]["vpc_id"] == "vpc-123"
        assert result[0]["subnet_id"] == "subnet-123"

    def test_audit_nat_gateways_no_gateways(self, capsys):
        """Test when no NAT gateways exist."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_nat_gateways.return_value = {"NatGateways": []}
            result = audit_nat_gateways_in_region("us-east-1")
        assert len(result) == 0
        captured = capsys.readouterr()
        assert "No NAT Gateways found" in captured.out

    def test_audit_nat_gateways_success(self, capsys):
        """Test successful NAT gateway audit."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_nat_gateways.return_value = {
                "NatGateways": [
                    {
                        "NatGatewayId": "nat-123",
                        "State": "available",
                        "VpcId": "vpc-123",
                        "SubnetId": "subnet-123",
                        "CreateTime": "2024-01-01",
                        "Tags": [{"Key": "Name", "Value": "prod-nat"}],
                    }
                ]
            }
            result = audit_nat_gateways_in_region("us-east-1")
        self._assert_nat_gateway_result(result)
        self._assert_nat_gateway_success_output(capsys)

    def test_audit_nat_gateways_no_tags(self, capsys):
        """Test NAT gateway audit without tags."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_nat_gateways.return_value = {
                "NatGateways": [
                    {
                        "NatGatewayId": "nat-456",
                        "State": "pending",
                        "VpcId": "vpc-456",
                        "SubnetId": "subnet-456",
                        "CreateTime": "2024-01-02",
                        "Tags": [],
                    }
                ]
            }
            result = audit_nat_gateways_in_region("us-west-2")
        assert len(result) == 1
        captured = capsys.readouterr()
        assert "Tags:" not in captured.out


class TestAuditNatGatewaysInRegionErrors:
    """Error and advanced scenario tests for audit_nat_gateways_in_region."""

    def test_audit_nat_gateways_client_error(self, capsys):
        """Test error handling during NAT gateway audit."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_nat_gateways.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "describe_nat_gateways"
            )
            result = audit_nat_gateways_in_region("us-east-1")
        assert len(result) == 0
        captured = capsys.readouterr()
        assert "Error auditing NAT Gateways" in captured.out

    def test_audit_nat_gateways_multiple(self):
        """Test auditing multiple NAT gateways."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_nat_gateways.return_value = {
                "NatGateways": [
                    {
                        "NatGatewayId": "nat-123",
                        "State": "available",
                        "VpcId": "vpc-123",
                        "SubnetId": "subnet-123",
                        "CreateTime": "2024-01-01",
                        "Tags": [],
                    },
                    {
                        "NatGatewayId": "nat-456",
                        "State": "deleting",
                        "VpcId": "vpc-456",
                        "SubnetId": "subnet-456",
                        "CreateTime": "2024-01-02",
                        "Tags": [],
                    },
                ]
            }
            result = audit_nat_gateways_in_region("us-east-1")
        assert len(result) == 2


def test_main_integration(capsys):
    """Test main function integration."""
    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_client.return_value = mock_ec2

        mock_ec2.describe_addresses.return_value = {
            "Addresses": [
                {
                    "PublicIp": "54.123.45.67",
                    "AllocationId": "eipalloc-123",
                    "AssociationId": "eipassoc-456",
                    "InstanceId": "i-123",
                    "Domain": "vpc",
                    "Tags": [],
                },
                {
                    "PublicIp": "54.123.45.68",
                    "AllocationId": "eipalloc-456",
                    "Domain": "vpc",
                    "Tags": [],
                },
            ]
        }

        mock_ec2.describe_nat_gateways.return_value = {
            "NatGateways": [
                {
                    "NatGatewayId": "nat-123",
                    "State": "available",
                    "VpcId": "vpc-123",
                    "SubnetId": "subnet-123",
                    "CreateTime": "2024-01-01",
                    "Tags": [],
                }
            ]
        }

        main()

    captured = capsys.readouterr()
    assert "AWS VPC Cost Audit" in captured.out
    assert "OVERALL SUMMARY" in captured.out
    assert "Total Elastic IP addresses found:" in captured.out
    assert "Total NAT Gateways found:" in captured.out
    assert "Elastic IP Breakdown:" in captured.out
    assert "Idle (costing money):" in captured.out
    assert "In use:" in captured.out
    assert "COST OPTIMIZATION OPPORTUNITY:" in captured.out
    assert "RECOMMENDATIONS:" in captured.out
