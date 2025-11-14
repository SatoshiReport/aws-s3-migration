"""Comprehensive tests for aws_kms_audit.py - Part 2."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_kms_audit import (
    _audit_region_kms_keys,
    _check_customer_gateways,
    _check_vpn_connections,
    _check_vpn_gateways,
    _check_vpn_resources,
    audit_kms_keys,
    main,
)


class TestAuditRegionKmsKeys:
    """Tests for _audit_region_kms_keys function."""

    def test_audit_region_with_keys(self, capsys):
        """Test auditing region with customer keys."""
        with patch("boto3.client") as mock_client:
            mock_kms = MagicMock()
            mock_client.return_value = mock_kms
            mock_kms.list_keys.return_value = {"Keys": [{"KeyId": "key-1"}, {"KeyId": "key-2"}]}
            mock_kms.describe_key.return_value = {
                "KeyMetadata": {
                    "KeyManager": "CUSTOMER",
                    "Description": "Test",
                    "KeyState": "Enabled",
                    "CreationDate": "2024-01-01",
                }
            }
            mock_kms.list_aliases.return_value = {"Aliases": []}
            mock_kms.list_grants.return_value = {"Grants": []}

            region_keys, region_cost = _audit_region_kms_keys("us-east-1")

            assert region_keys == 2
            assert region_cost == 2
            captured = capsys.readouterr()
            assert "Region: us-east-1" in captured.out

    def test_audit_region_no_keys(self):
        """Test auditing region with no keys."""
        with patch("boto3.client") as mock_client:
            mock_kms = MagicMock()
            mock_client.return_value = mock_kms
            mock_kms.list_keys.return_value = {"Keys": []}

            region_keys, region_cost = _audit_region_kms_keys("us-west-1")

            assert region_keys == 0
            assert region_cost == 0


class TestAuditRegionKmsKeysPart2:
    """Tests for _audit_region_kms_keys function - Part 2."""

    def test_audit_region_error(self, capsys):
        """Test auditing region with error."""
        with patch("boto3.client") as mock_client:
            mock_kms = MagicMock()
            mock_client.return_value = mock_kms
            mock_kms.list_keys.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "list_keys"
            )

            region_keys, region_cost = _audit_region_kms_keys("eu-west-1")

            assert region_keys == 0
            assert region_cost == 0
            captured = capsys.readouterr()
            assert "Error accessing region" in captured.out

    def test_audit_region_unavailable(self):
        """Test auditing unavailable region."""
        with patch("boto3.client") as mock_client:
            mock_kms = MagicMock()
            mock_client.return_value = mock_kms
            mock_kms.list_keys.side_effect = ClientError(
                {"Error": {"Code": "Region not available"}}, "list_keys"
            )

            region_keys, region_cost = _audit_region_kms_keys("ap-south-1")

            assert region_keys == 0
            assert region_cost == 0


class TestCheckVpnConnections:
    """Tests for _check_vpn_connections function."""

    def test_check_vpn_with_connections(self, capsys):
        """Test checking VPN connections when they exist."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_vpn_connections.return_value = {
            "VpnConnections": [
                {
                    "VpnConnectionId": "vpn-123",
                    "State": "available",
                    "Type": "ipsec.1",
                }
            ]
        }

        _check_vpn_connections(mock_ec2, "us-east-1")

        captured = capsys.readouterr()
        assert "VPN Connections found" in captured.out
        assert "vpn-123" in captured.out

    def test_check_vpn_no_connections(self, capsys):
        """Test checking VPN connections when none exist."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_vpn_connections.return_value = {"VpnConnections": []}

        _check_vpn_connections(mock_ec2, "us-east-1")

        captured = capsys.readouterr()
        assert "VPN Connections" not in captured.out


class TestCheckCustomerGateways:
    """Tests for _check_customer_gateways function."""

    def test_check_gateways_with_gateways(self, capsys):
        """Test checking customer gateways when they exist."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_customer_gateways.return_value = {
            "CustomerGateways": [
                {
                    "CustomerGatewayId": "cgw-123",
                    "State": "available",
                    "Type": "ipsec.1",
                }
            ]
        }

        _check_customer_gateways(mock_ec2, "us-east-1")

        captured = capsys.readouterr()
        assert "Customer Gateways found" in captured.out
        assert "cgw-123" in captured.out

    def test_check_gateways_no_gateways(self, capsys):
        """Test checking customer gateways when none exist."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_customer_gateways.return_value = {"CustomerGateways": []}

        _check_customer_gateways(mock_ec2, "us-east-1")

        captured = capsys.readouterr()
        assert "Customer Gateways" not in captured.out


class TestCheckVpnGateways:
    """Tests for _check_vpn_gateways function."""

    def test_check_vpn_gateways_with_gateways(self, capsys):
        """Test checking VPN gateways when they exist."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_vpn_gateways.return_value = {
            "VpnGateways": [
                {
                    "VpnGatewayId": "vgw-123",
                    "State": "available",
                    "Type": "ipsec.1",
                }
            ]
        }

        _check_vpn_gateways(mock_ec2, "us-east-1")

        captured = capsys.readouterr()
        assert "VPN Gateways found" in captured.out
        assert "vgw-123" in captured.out

    def test_check_vpn_gateways_no_gateways(self, capsys):
        """Test checking VPN gateways when none exist."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_vpn_gateways.return_value = {"VpnGateways": []}

        _check_vpn_gateways(mock_ec2, "us-east-1")

        captured = capsys.readouterr()
        assert "VPN Gateways" not in captured.out


class TestCheckVpnResources:
    """Tests for _check_vpn_resources function."""

    def test_check_vpn_resources_success(self):
        """Test checking VPN resources successfully."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_vpn_connections.return_value = {"VpnConnections": []}
            mock_ec2.describe_customer_gateways.return_value = {"CustomerGateways": []}
            mock_ec2.describe_vpn_gateways.return_value = {"VpnGateways": []}

            _check_vpn_resources("us-east-1")

            mock_ec2.describe_vpn_connections.assert_called_once()

    def test_check_vpn_resources_error(self, capsys):
        """Test error handling when checking VPN resources."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_vpn_connections.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "describe_vpn_connections"
            )

            _check_vpn_resources("us-east-1")

            captured = capsys.readouterr()
            assert "Error checking VPN resources" in captured.out


class TestAuditKmsKeys:
    """Tests for audit_kms_keys function."""

    def test_audit_kms_keys_success(self, capsys):
        """Test full KMS audit."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_kms = MagicMock()

            def client_factory(service, **_kwargs):
                if service == "ec2":
                    return mock_ec2
                return mock_kms

            mock_client.side_effect = client_factory

            mock_ec2.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}
            mock_kms.list_keys.return_value = {"Keys": []}
            mock_ec2.describe_vpn_connections.return_value = {"VpnConnections": []}
            mock_ec2.describe_customer_gateways.return_value = {"CustomerGateways": []}
            mock_ec2.describe_vpn_gateways.return_value = {"VpnGateways": []}

            audit_kms_keys()

            captured = capsys.readouterr()
            assert "AWS KMS Key Usage Audit" in captured.out
            assert "SUMMARY:" in captured.out
            assert "CHECKING FOR VPN-RELATED KMS USAGE:" in captured.out

    def test_audit_kms_keys_multiple_regions(self, capsys):
        """Test KMS audit across multiple regions."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_kms = MagicMock()

            def client_factory(service, **_kwargs):
                if service == "ec2":
                    return mock_ec2
                return mock_kms

            mock_client.side_effect = client_factory

            mock_ec2.describe_regions.return_value = {
                "Regions": [{"RegionName": "us-east-1"}, {"RegionName": "eu-west-2"}]
            }
            mock_kms.list_keys.return_value = {"Keys": []}
            mock_ec2.describe_vpn_connections.return_value = {"VpnConnections": []}
            mock_ec2.describe_customer_gateways.return_value = {"CustomerGateways": []}
            mock_ec2.describe_vpn_gateways.return_value = {"VpnGateways": []}

            audit_kms_keys()

            captured = capsys.readouterr()
            assert "SUMMARY:" in captured.out


class TestMain:
    """Tests for main function."""

    def test_main_calls_audit(self):
        """Test main function calls audit."""
        with patch("cost_toolkit.scripts.audit.aws_kms_audit.audit_kms_keys") as mock_audit:
            main()

            mock_audit.assert_called_once()

    def test_main_completes_successfully(self):
        """Test main function completes without errors."""
        with patch("cost_toolkit.scripts.audit.aws_kms_audit.audit_kms_keys"):
            main()
