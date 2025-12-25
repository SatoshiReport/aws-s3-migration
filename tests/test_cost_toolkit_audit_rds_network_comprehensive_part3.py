"""Comprehensive tests for aws_rds_network_interface_audit.py - Part 3."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_rds_network_interface_audit import (
    _scan_region_resources,
    get_network_interfaces_in_region,
)


class TestGetNetworkInterfacesInRegion:
    """Tests for get_network_interfaces_in_region function."""

    def test_get_rds_network_interfaces(self):
        """Test getting RDS network interfaces."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_network_interfaces.return_value = {
                "NetworkInterfaces": [
                    {
                        "NetworkInterfaceId": "eni-123",
                        "VpcId": "vpc-123",
                        "SubnetId": "subnet-123",
                        "PrivateIpAddress": "10.0.1.10",
                        "Status": "in-use",
                        "Description": "RDSNetworkInterface",
                    }
                ]
            }
            mock_client.return_value = mock_ec2

            interfaces = get_network_interfaces_in_region("us-east-1", "test-key", "test-secret")

        assert len(interfaces) == 1
        assert interfaces[0]["NetworkInterfaceId"] == "eni-123"

    def test_get_network_interfaces_none_found(self):
        """Test when no RDS network interfaces found."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_network_interfaces.return_value = {"NetworkInterfaces": []}
            mock_client.return_value = mock_ec2

            interfaces = get_network_interfaces_in_region("us-west-2", "test-key", "test-secret")

        assert len(interfaces) == 0

    def test_get_network_interfaces_client_error(self, capsys):
        """Test error handling when getting interfaces fails."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_network_interfaces.side_effect = ClientError(
                {"Error": {"Code": "UnauthorizedOperation"}}, "describe_network_interfaces"
            )
            mock_client.return_value = mock_ec2

            interfaces = get_network_interfaces_in_region("eu-west-1", "test-key", "test-secret")

        assert len(interfaces) == 0
        captured = capsys.readouterr()
        assert "Error getting network interfaces in eu-west-1" in captured.out


def test_scan_region_resources_scan_resources(capsys):
    """Test scanning region resources."""
    with patch("cost_toolkit.scripts.audit.aws_rds_network_interface_audit.audit_rds_instances_in_region") as mock_audit:
        with patch("cost_toolkit.scripts.audit.aws_rds_network_interface_audit." "get_network_interfaces_in_region") as mock_interfaces:
            mock_audit.return_value = {
                "region": "us-east-1",
                "instances": [],
                "clusters": [],
                "total_instances": 0,
                "total_clusters": 0,
            }
            mock_interfaces.return_value = [
                {
                    "NetworkInterfaceId": "eni-123",
                    "VpcId": "vpc-123",
                    "SubnetId": "subnet-123",
                    "PrivateIpAddress": "10.0.1.10",
                    "Status": "available",
                    "Description": "RDSNetworkInterface",
                    "Association": {"PublicIp": "1.2.3.4"},
                }
            ]

            rds_data, rds_interfaces, interface_info = _scan_region_resources("us-east-1", "test-key", "test-secret")

    assert rds_data is not None
    assert len(rds_interfaces) == 1
    assert len(interface_info) == 1
    assert interface_info[0]["region"] == "us-east-1"
    assert interface_info[0]["interface_id"] == "eni-123"
    assert interface_info[0]["public_ip"] == "1.2.3.4"
    captured = capsys.readouterr()
    assert "Checking region: us-east-1" in captured.out
