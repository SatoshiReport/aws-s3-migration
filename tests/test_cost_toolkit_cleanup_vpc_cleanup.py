"""Comprehensive tests for aws_vpc_cleanup.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_vpc_cleanup import release_elastic_ips_in_region
from tests.aws_region_test_utils import ELASTIC_IP_RESPONSE, SINGLE_ELASTIC_IP_RESPONSE


class TestReleaseElasticIpsBasic:
    """Tests for release_elastic_ips_in_region basic scenarios."""

    def test_release_elastic_ips_no_addresses(self, capsys):
        """Test when no elastic IPs exist."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_addresses.return_value = {"Addresses": []}

            savings = release_elastic_ips_in_region("us-east-1")

        assert savings == 0
        captured = capsys.readouterr()
        assert "No Elastic IP addresses found" in captured.out

    def test_release_elastic_ips_unassociated(self, capsys):
        """Test releasing unassociated elastic IP."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_addresses.return_value = SINGLE_ELASTIC_IP_RESPONSE

            savings = release_elastic_ips_in_region("us-east-1")

        assert savings == 3.60
        mock_ec2.release_address.assert_called_once_with(AllocationId="eipalloc-123")
        captured = capsys.readouterr()
        assert "Processing IP: 54.123.45.67" in captured.out
        assert "Released 54.123.45.67 successfully" in captured.out
        assert "Released: 1 Elastic IPs" in captured.out
        assert "Monthly savings: $3.60" in captured.out

    def test_release_elastic_ips_multiple(self, capsys):
        """Test releasing multiple elastic IPs."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_addresses.return_value = ELASTIC_IP_RESPONSE

            savings = release_elastic_ips_in_region("us-east-1")

        assert savings == 7.20
        assert mock_ec2.release_address.call_count == 2
        captured = capsys.readouterr()
        assert "Released: 2 Elastic IPs" in captured.out
        assert "Monthly savings: $7.20" in captured.out


def test_release_elastic_ips_associated(capsys):
    """Test releasing associated elastic IP."""
    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_client.return_value = mock_ec2
        mock_ec2.describe_addresses.return_value = {
            "Addresses": [
                {
                    "PublicIp": "54.123.45.68",
                    "AllocationId": "eipalloc-456",
                    "AssociationId": "eipassoc-789",
                }
            ]
        }

        savings = release_elastic_ips_in_region("us-east-1")

    assert savings == 3.60
    mock_ec2.disassociate_address.assert_called_once_with(AssociationId="eipassoc-789")
    mock_ec2.release_address.assert_called_once_with(AllocationId="eipalloc-456")
    captured = capsys.readouterr()
    assert "Disassociating from instance" in captured.out
    assert "Disassociated successfully" in captured.out
    assert "Released 54.123.45.68 successfully" in captured.out


class TestReleaseElasticIpsDisassociateErrors:
    """Tests for disassociation error handling."""

    def test_release_elastic_ips_disassociate_error_retry(self, capsys):
        """Test handling disassociation error and retry without it."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [
                    {
                        "PublicIp": "54.123.45.69",
                        "AllocationId": "eipalloc-789",
                        "AssociationId": "eipassoc-999",
                    }
                ]
            }

            mock_ec2.disassociate_address.side_effect = ClientError(
                {"Error": {"Code": "InvalidAssociationID.NotFound"}},
                "disassociate_address",
            )

            savings = release_elastic_ips_in_region("us-east-1")

        assert savings == 3.60
        mock_ec2.release_address.assert_called_once_with(AllocationId="eipalloc-789")
        captured = capsys.readouterr()
        assert "Released 54.123.45.69 successfully" in captured.out

    def test_release_elastic_ips_other_disassociate_error(self, capsys):
        """Test handling other disassociation errors."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [
                    {
                        "PublicIp": "54.123.45.74",
                        "AllocationId": "eipalloc-444",
                        "AssociationId": "eipassoc-444",
                    }
                ]
            }

            mock_ec2.disassociate_address.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "disassociate_address")

            savings = release_elastic_ips_in_region("us-east-1")

        assert savings == 0
        captured = capsys.readouterr()
        assert "Failed to process 54.123.45.74" in captured.out

    def test_release_elastic_ips_disassociate_and_release_both_fail(self, capsys):
        """Test when both disassociation and release fail."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [
                    {
                        "PublicIp": "54.123.45.73",
                        "AllocationId": "eipalloc-333",
                        "AssociationId": "eipassoc-333",
                    }
                ]
            }

            mock_ec2.disassociate_address.side_effect = ClientError(
                {"Error": {"Code": "InvalidAssociationID.NotFound"}},
                "disassociate_address",
            )
            mock_ec2.release_address.side_effect = ClientError({"Error": {"Code": "InUse"}}, "release_address")

            savings = release_elastic_ips_in_region("us-east-1")

        assert savings == 0
        captured = capsys.readouterr()
        assert "Failed to release 54.123.45.73" in captured.out


class TestReleaseElasticIpsReleaseErrors:
    """Tests for release operation error handling."""

    def test_release_elastic_ips_release_error(self, capsys):
        """Test handling release error."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [
                    {
                        "PublicIp": "54.123.45.70",
                        "AllocationId": "eipalloc-999",
                    }
                ]
            }

            mock_ec2.release_address.side_effect = ClientError({"Error": {"Code": "InUse"}}, "release_address")

            savings = release_elastic_ips_in_region("us-east-1")

        assert savings == 0
        captured = capsys.readouterr()
        assert "Failed to process" in captured.out
        assert "Released: 0 Elastic IPs" in captured.out

    def test_release_elastic_ips_partial_failure(self, capsys):
        """Test partial success when some releases fail."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [
                    {
                        "PublicIp": "54.123.45.71",
                        "AllocationId": "eipalloc-111",
                    },
                    {
                        "PublicIp": "54.123.45.72",
                        "AllocationId": "eipalloc-222",
                    },
                ]
            }

            mock_ec2.release_address.side_effect = [
                None,  # First release succeeds
                ClientError({"Error": {"Code": "InUse"}}, "release_address"),
            ]

            savings = release_elastic_ips_in_region("us-east-1")

        assert savings == 3.60
        captured = capsys.readouterr()
        assert "Released 54.123.45.71 successfully" in captured.out
        assert "Failed to process" in captured.out
        assert "Released: 1 Elastic IPs" in captured.out


def test_release_elastic_ips_describe_addresses_error(capsys):
    """Test handling describe_addresses error."""
    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_client.return_value = mock_ec2
        mock_ec2.describe_addresses.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "describe_addresses")

        savings = release_elastic_ips_in_region("us-east-1")

    assert savings == 0
    captured = capsys.readouterr()
    assert "Error accessing us-east-1" in captured.out
