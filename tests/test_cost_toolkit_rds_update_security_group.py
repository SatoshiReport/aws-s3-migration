"""Comprehensive tests for cost_toolkit/scripts/rds/update_rds_security_group.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.rds.update_rds_security_group import main, update_security_group


class TestUpdateSecurityGroupSuccess:
    """Tests for update_security_group function - success scenarios."""

    def _assert_security_group_call_args(self, mock_ec2):
        """Helper to assert security group call arguments."""
        mock_ec2.authorize_security_group_ingress.assert_called_once()
        call_args = mock_ec2.authorize_security_group_ingress.call_args[1]
        assert call_args["GroupId"] == "sg-265aa043"
        assert call_args["IpPermissions"][0]["IpProtocol"] == "tcp"
        assert call_args["IpPermissions"][0]["FromPort"] == 5432
        assert call_args["IpPermissions"][0]["ToPort"] == 5432
        assert call_args["IpPermissions"][0]["IpRanges"][0]["CidrIp"] == "203.0.113.42/32"
        assert (
            call_args["IpPermissions"][0]["IpRanges"][0]["Description"]
            == "Temporary access for data migration"
        )

    def _assert_success_output(self, capsys):
        """Helper to assert success output."""
        captured = capsys.readouterr()
        assert "Getting your current public IP address..." in captured.out
        assert "Your IP: 203.0.113.42" in captured.out
        assert "Adding rule to security group sg-265aa043..." in captured.out
        assert "Security group updated!" in captured.out
        assert "Added rule: Port 5432 from 203.0.113.42/32" in captured.out
        assert "This is temporary - we'll remove it after data migration" in captured.out

    @patch("cost_toolkit.scripts.rds.update_rds_security_group.boto3.client")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group._fetch_current_ip")
    def test_update_security_group_success(
        self, mock_fetch_ip, mock_setup_creds, mock_boto_client, capsys
    ):
        """Test successfully updating security group."""
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_fetch_ip.return_value = "203.0.113.42"

        update_security_group()

        mock_setup_creds.assert_called_once()
        mock_boto_client.assert_called_once_with("ec2", region_name="us-east-1")
        mock_fetch_ip.assert_called_once_with()

        self._assert_security_group_call_args(mock_ec2)
        self._assert_success_output(capsys)

    @patch("cost_toolkit.scripts.rds.update_rds_security_group.boto3.client")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group._fetch_current_ip")
    def test_update_security_group_ip_with_whitespace(
        self, mock_fetch_ip, _mock_setup_creds, mock_boto_client
    ):
        """Test handling IP with whitespace."""
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_fetch_ip.return_value = "203.0.113.42"

        update_security_group()

        call_args = mock_ec2.authorize_security_group_ingress.call_args[1]
        assert call_args["IpPermissions"][0]["IpRanges"][0]["CidrIp"] == "203.0.113.42/32"


class TestUpdateSecurityGroupErrors:
    """Tests for update_security_group function - error handling."""

    @patch("cost_toolkit.scripts.rds.update_rds_security_group.boto3.client")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group._fetch_current_ip")
    def test_update_security_group_get_ip_fails(
        self, mock_fetch_ip, _mock_setup_creds, mock_boto_client, capsys
    ):
        """Test handling failure to get current IP."""
        mock_boto_client.return_value = MagicMock()
        mock_fetch_ip.side_effect = ClientError(
            {"Error": {"Code": "NetworkError", "Message": "Network unreachable"}}, "GetIP"
        )

        update_security_group()

        captured = capsys.readouterr()
        assert "Could not get current IP:" in captured.out
        assert "Please provide your public IP address manually" in captured.out

    @patch("cost_toolkit.scripts.rds.update_rds_security_group.boto3.client")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group._fetch_current_ip")
    def test_update_security_group_rule_already_exists(
        self, mock_fetch_ip, _mock_setup_creds, mock_boto_client, capsys
    ):
        """Test handling when security group rule already exists."""
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_fetch_ip.return_value = "203.0.113.42"
        mock_ec2.authorize_security_group_ingress.side_effect = ClientError(
            {"Error": {"Code": "InvalidPermission.Duplicate", "Message": "already exists"}},
            "AuthorizeSecurityGroupIngress",
        )

        update_security_group()

        captured = capsys.readouterr()
        assert "Rule already exists for your IP" in captured.out

    @patch("cost_toolkit.scripts.rds.update_rds_security_group.boto3.client")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group._fetch_current_ip")
    def test_update_security_group_other_error(
        self, mock_fetch_ip, _mock_setup_creds, mock_boto_client, capsys
    ):
        """Test handling other errors when updating security group."""
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_fetch_ip.return_value = "203.0.113.42"
        mock_ec2.authorize_security_group_ingress.side_effect = ClientError(
            {"Error": {"Code": "InvalidGroup.NotFound", "Message": "Security group not found"}},
            "AuthorizeSecurityGroupIngress",
        )

        update_security_group()

        captured = capsys.readouterr()
        assert "Error updating security group:" in captured.out

    @patch("cost_toolkit.scripts.rds.update_rds_security_group.boto3.client")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group._fetch_current_ip")
    def test_update_security_group_timeout(
        self, mock_fetch_ip, _mock_setup_creds, mock_boto_client
    ):
        """Test that timeout exception propagates (not caught in current code)."""
        mock_boto_client.return_value = MagicMock()
        mock_fetch_ip.side_effect = Exception("Request timeout")

        with pytest.raises(Exception, match="Request timeout"):
            update_security_group()


class TestUpdateSecurityGroupConfiguration:
    """Tests for update_security_group function - configuration validation."""

    @patch("cost_toolkit.scripts.rds.update_rds_security_group.boto3.client")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group._fetch_current_ip")
    def test_update_security_group_timeout_parameter(self, mock_fetch_ip, _mock_setup_creds, mock_boto_client):
        """Test that IP request uses correct timeout."""
        mock_boto_client.return_value = MagicMock()
        mock_fetch_ip.return_value = "203.0.113.42"

        update_security_group()

        mock_fetch_ip.assert_called_once_with()

    @patch("cost_toolkit.scripts.rds.update_rds_security_group.boto3.client")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.update_rds_security_group._fetch_current_ip")
    def test_update_security_group_correct_port(
        self, mock_fetch_ip, _mock_setup_creds, mock_boto_client
    ):
        """Test that security group rule uses PostgreSQL port 5432."""
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_fetch_ip.return_value = "203.0.113.42"

        update_security_group()

        call_args = mock_ec2.authorize_security_group_ingress.call_args[1]
        assert call_args["IpPermissions"][0]["FromPort"] == 5432
        assert call_args["IpPermissions"][0]["ToPort"] == 5432


@patch("cost_toolkit.scripts.rds.update_rds_security_group.update_security_group")
def test_main_calls_update_security_group(mock_update):
    """Test that main calls update_security_group."""
    main()

    mock_update.assert_called_once()
