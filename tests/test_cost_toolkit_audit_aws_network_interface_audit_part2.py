"""Comprehensive tests for aws_network_interface_audit.py - Part 2: Audit Functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_network_interface_audit import (
    audit_network_interfaces_in_region,
)


class TestAuditNetworkInterfacesInRegionEmpty:  # pylint: disable=too-few-public-methods
    """Tests for audit_network_interfaces_in_region with empty results."""

    def test_audit_region_no_interfaces(self):
        """Test auditing region with no network interfaces."""
        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_network_interfaces.return_value = {"NetworkInterfaces": []}

        with patch(
            "cost_toolkit.scripts.audit.aws_network_interface_audit.boto3.client",
            return_value=mock_ec2_client,
        ):
            result = audit_network_interfaces_in_region("us-east-1", "test-key", "test-secret")

        assert result is None


class TestAuditNetworkInterfacesInRegionUnused:
    """Tests for audit_network_interfaces_in_region with unused interfaces."""

    def test_audit_region_with_unused_interfaces(self):
        """Test auditing region with unused network interfaces."""
        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_network_interfaces.return_value = {
            "NetworkInterfaces": [
                {
                    "NetworkInterfaceId": "eni-unused1",
                    "Status": "available",
                    "VpcId": "vpc-123",
                    "Tags": [{"Key": "Name", "Value": "unused-eni"}],
                },
                {
                    "NetworkInterfaceId": "eni-unused2",
                    "Status": "available",
                },
            ]
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_network_interface_audit.boto3.client",
            return_value=mock_ec2_client,
        ):
            result = audit_network_interfaces_in_region("us-west-2", "test-key", "test-secret")

        assert result is not None
        assert result["region"] == "us-west-2"
        assert result["total_interfaces"] == 2
        assert len(result["unused_interfaces"]) == 2
        assert len(result["attached_interfaces"]) == 0
        assert len(result["interface_details"]) == 2

    def test_audit_region_with_attached_interfaces(self):
        """Test auditing region with attached network interfaces."""
        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_network_interfaces.return_value = {
            "NetworkInterfaces": [
                {
                    "NetworkInterfaceId": "eni-attached1",
                    "Status": "in-use",
                    "Attachment": {
                        "InstanceId": "i-123",
                        "Status": "attached",
                    },
                }
            ]
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_network_interface_audit.boto3.client",
            return_value=mock_ec2_client,
        ):
            result = audit_network_interfaces_in_region("eu-west-1", "test-key", "test-secret")

        assert result is not None
        assert result["total_interfaces"] == 1
        assert len(result["unused_interfaces"]) == 0
        assert len(result["attached_interfaces"]) == 1

    def test_audit_region_with_mixed_interfaces(self):
        """Test auditing region with both unused and attached interfaces."""
        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_network_interfaces.return_value = {
            "NetworkInterfaces": [
                {
                    "NetworkInterfaceId": "eni-available",
                    "Status": "available",
                },
                {
                    "NetworkInterfaceId": "eni-inuse",
                    "Status": "in-use",
                    "Attachment": {"InstanceId": "i-123", "Status": "attached"},
                },
                {
                    "NetworkInterfaceId": "eni-available2",
                    "Status": "available",
                },
            ]
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_network_interface_audit.boto3.client",
            return_value=mock_ec2_client,
        ):
            result = audit_network_interfaces_in_region("us-east-1", "test-key", "test-secret")

        assert result is not None
        assert result["total_interfaces"] == 3
        assert len(result["unused_interfaces"]) == 2
        assert len(result["attached_interfaces"]) == 1


class TestAuditNetworkInterfacesInRegionConfig:
    """Tests for audit_network_interfaces_in_region function configuration."""

    def test_audit_region_client_error(self, capsys):
        """Test handling of ClientError during audit."""
        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_network_interfaces.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "DescribeNetworkInterfaces",
        )

        with patch(
            "cost_toolkit.scripts.audit.aws_network_interface_audit.boto3.client",
            return_value=mock_ec2_client,
        ):
            result = audit_network_interfaces_in_region("ap-south-1", "test-key", "test-secret")

        assert result is None
        captured = capsys.readouterr()
        assert "Error auditing network interfaces in ap-south-1" in captured.out

    def test_audit_region_creates_client_correctly(self):
        """Test that boto3 client is created with correct parameters."""
        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_network_interfaces.return_value = {"NetworkInterfaces": []}

        with patch("cost_toolkit.scripts.audit.aws_network_interface_audit.boto3.client") as mock_boto3:
            mock_boto3.return_value = mock_ec2_client
            audit_network_interfaces_in_region("eu-central-1", "my-access-key", "my-secret-key")

        mock_boto3.assert_called_once_with(
            "ec2",
            region_name="eu-central-1",
            aws_access_key_id="my-access-key",
            aws_secret_access_key="my-secret-key",
        )

    def test_audit_region_interface_details_populated(self):
        """Test that interface_details list is correctly populated."""
        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_network_interfaces.return_value = {
            "NetworkInterfaces": [
                {
                    "NetworkInterfaceId": "eni-123",
                    "Status": "available",
                    "PrivateIpAddress": "10.0.1.5",
                }
            ]
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_network_interface_audit.boto3.client",
            return_value=mock_ec2_client,
        ):
            result = audit_network_interfaces_in_region("us-east-1", "test-key", "test-secret")

        assert len(result["interface_details"]) == 1
        assert result["interface_details"][0]["interface_id"] == "eni-123"
        assert result["interface_details"][0]["private_ip"] == "10.0.1.5"
