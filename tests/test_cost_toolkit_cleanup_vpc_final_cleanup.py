"""Tests for aws_vpc_final_cleanup script."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_vpc_final_cleanup import (
    main,
    release_remaining_elastic_ip,
)


class TestReleaseElasticIPSuccess:
    """Test successful releases of Elastic IP addresses."""

    def test_release_no_ips(self, capsys):
        """Test when no Elastic IPs exist."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_addresses.return_value = {"Addresses": []}
            mock_client.return_value = mock_ec2
            result = release_remaining_elastic_ip()
            assert result is True
            captured = capsys.readouterr()
            assert "No Elastic IP addresses found" in captured.out

    def test_release_single_ip_success(self, capsys):
        """Test successful release of single Elastic IP."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [{"AllocationId": "eipalloc-123", "PublicIp": "1.2.3.4"}]
            }
            mock_ec2.release_address.return_value = {}
            mock_client.return_value = mock_ec2
            result = release_remaining_elastic_ip()
            assert result is True
            captured = capsys.readouterr()
            assert "Found IP: 1.2.3.4" in captured.out
            assert "Successfully released 1.2.3.4" in captured.out
            mock_ec2.release_address.assert_called_once_with(AllocationId="eipalloc-123")

    def test_release_multiple_ips(self, capsys):
        """Test releasing multiple Elastic IPs."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [
                    {"AllocationId": "eipalloc-123", "PublicIp": "1.2.3.4"},
                    {"AllocationId": "eipalloc-456", "PublicIp": "5.6.7.8"},
                ]
            }
            mock_ec2.release_address.return_value = {}
            mock_client.return_value = mock_ec2
            result = release_remaining_elastic_ip()
            assert result is True
            captured = capsys.readouterr()
            assert "Found IP: 1.2.3.4" in captured.out
            assert "Successfully released 1.2.3.4" in captured.out
            assert "Found IP: 5.6.7.8" in captured.out
            assert "Successfully released 5.6.7.8" in captured.out
            assert mock_ec2.release_address.call_count == 2


class TestReleaseElasticIPAssociated:
    """Test releasing associated Elastic IP addresses."""

    def test_release_associated_ip_success(self, capsys):
        """Test releasing Elastic IP that is associated with an instance."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [
                    {
                        "AllocationId": "eipalloc-123",
                        "PublicIp": "1.2.3.4",
                        "AssociationId": "eipassoc-456",
                    }
                ]
            }
            mock_ec2.disassociate_address.return_value = {}
            mock_ec2.release_address.return_value = {}
            mock_client.return_value = mock_ec2
            result = release_remaining_elastic_ip()
            assert result is True
            captured = capsys.readouterr()
            assert "Disassociating from instance" in captured.out
            assert "Disassociated successfully" in captured.out
            assert "Successfully released 1.2.3.4" in captured.out
            mock_ec2.disassociate_address.assert_called_once_with(AssociationId="eipassoc-456")
            mock_ec2.release_address.assert_called_once_with(AllocationId="eipalloc-123")

    def test_release_mixed_associated_and_unassociated(self, capsys):
        """Test releasing mix of associated and unassociated IPs."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [
                    {
                        "AllocationId": "eipalloc-123",
                        "PublicIp": "1.2.3.4",
                        "AssociationId": "eipassoc-456",
                    },
                    {"AllocationId": "eipalloc-789", "PublicIp": "5.6.7.8"},
                ]
            }
            mock_ec2.disassociate_address.return_value = {}
            mock_ec2.release_address.return_value = {}
            mock_client.return_value = mock_ec2
            result = release_remaining_elastic_ip()
            assert result is True
            captured = capsys.readouterr()
            assert "Disassociating from instance" in captured.out
            assert "Successfully released 1.2.3.4" in captured.out
            assert "Successfully released 5.6.7.8" in captured.out
            assert mock_ec2.disassociate_address.call_count == 1
            assert mock_ec2.release_address.call_count == 2


class TestReleaseElasticIPErrorHandling:
    """Test error handling during Elastic IP release - specific errors."""

    def test_release_locked_ip(self, capsys):
        """Test releasing Elastic IP that is locked by AWS."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [{"AllocationId": "eipalloc-123", "PublicIp": "1.2.3.4"}]
            }
            error = ClientError(
                {
                    "Error": {
                        "Code": "InvalidAddress.Locked",
                        "Message": "Address is locked by AWS",
                    }
                },
                "release_address",
            )
            mock_ec2.release_address.side_effect = error
            mock_client.return_value = mock_ec2
            result = release_remaining_elastic_ip()
            assert result is False
            captured = capsys.readouterr()
            assert "IP is locked by AWS" in captured.out
            assert "This IP requires AWS Support to unlock" in captured.out

    def test_release_generic_error(self, capsys):
        """Test handling of generic error during release."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [{"AllocationId": "eipalloc-123", "PublicIp": "1.2.3.4"}]
            }
            error = ClientError(
                {"Error": {"Code": "GenericError", "Message": "Something went wrong"}},
                "release_address",
            )
            mock_ec2.release_address.side_effect = error
            mock_client.return_value = mock_ec2
            result = release_remaining_elastic_ip()
            assert result is False
            captured = capsys.readouterr()
            assert "Failed to release 1.2.3.4" in captured.out

    def test_release_disassociate_error(self, capsys):
        """Test error during disassociation."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [
                    {
                        "AllocationId": "eipalloc-123",
                        "PublicIp": "1.2.3.4",
                        "AssociationId": "eipassoc-456",
                    }
                ]
            }
            error = ClientError(
                {"Error": {"Code": "InvalidAssociationID.NotFound", "Message": "Not found"}},
                "disassociate_address",
            )
            mock_ec2.disassociate_address.side_effect = error
            mock_client.return_value = mock_ec2
            result = release_remaining_elastic_ip()
            assert result is False
            captured = capsys.readouterr()
            assert "Failed to release 1.2.3.4" in captured.out


class TestReleaseElasticIPFailures:
    """Test failure scenarios during Elastic IP release."""

    def test_release_describe_error(self, capsys):
        """Test error during describe_addresses."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            error = ClientError({"Error": {"Code": "UnauthorizedOperation"}}, "describe_addresses")
            mock_ec2.describe_addresses.side_effect = error
            mock_client.return_value = mock_ec2
            result = release_remaining_elastic_ip()
            assert result is False
            captured = capsys.readouterr()
            assert "Error accessing eu-west-2" in captured.out

    def test_release_first_fails_stops_processing(self, capsys):
        """Test that first failure stops processing remaining IPs."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [
                    {"AllocationId": "eipalloc-123", "PublicIp": "1.2.3.4"},
                    {"AllocationId": "eipalloc-456", "PublicIp": "5.6.7.8"},
                ]
            }
            error = ClientError(
                {"Error": {"Code": "GenericError", "Message": "Error"}}, "release_address"
            )
            mock_ec2.release_address.side_effect = error
            mock_client.return_value = mock_ec2
            result = release_remaining_elastic_ip()
            assert result is False
            captured = capsys.readouterr()
            assert "Failed to release 1.2.3.4" in captured.out
            assert mock_ec2.release_address.call_count == 1


class TestMain:
    """Test main execution function."""

    def test_main_success(self, capsys):
        """Test successful main execution."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_vpc_final_cleanup.release_remaining_elastic_ip"
        ) as mock_release:
            mock_release.return_value = True
            main()
            captured = capsys.readouterr()
            assert "SUCCESS" in captured.out
            assert "All Elastic IPs have been released" in captured.out
            assert "Total monthly savings: $14.40" in captured.out
            assert "Annual savings: $172.80" in captured.out

    def test_main_partial_success(self, capsys):
        """Test main execution with partial success."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_vpc_final_cleanup.release_remaining_elastic_ip"
        ) as mock_release:
            mock_release.return_value = False
            main()
            captured = capsys.readouterr()
            assert "PARTIAL SUCCESS" in captured.out
            assert "1 IP remains locked by AWS" in captured.out
            assert "Monthly savings so far: $10.80" in captured.out
            assert "Remaining cost: $3.60/month for locked IP" in captured.out
            assert "Contact AWS Support" in captured.out

    def test_main_calls_release_function(self):
        """Test that main calls the release function."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_vpc_final_cleanup.release_remaining_elastic_ip"
        ) as mock_release:
            mock_release.return_value = True
            main()
            mock_release.assert_called_once()
