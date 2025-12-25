"""Comprehensive tests for aws_elastic_ip_audit.py - Part 2: Print function tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.audit.aws_elastic_ip_audit import (
    _print_associated_eips,
    _print_cleanup_recommendations,
    _print_unassociated_eips,
)


class TestPrintAssociatedEipsBasic:
    """Tests for _print_associated_eips function - basic cases."""

    def test_print_no_associated_eips(self, capsys):
        """Test printing when no associated EIPs exist."""
        region_data = {
            "region": "us-east-1",
            "associated_eips": [],
        }

        _print_associated_eips(region_data, "test-key", "test-secret")

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_associated_eips_with_instances(self, capsys):
        """Test printing associated EIPs attached to instances."""
        region_data = {
            "region": "us-east-1",
            "associated_eips": [
                {
                    "public_ip": "1.2.3.4",
                    "instance_id": "i-123",
                    "network_interface_id": None,
                },
                {
                    "public_ip": "5.6.7.8",
                    "instance_id": "i-456",
                    "network_interface_id": "eni-456",
                },
            ],
        }

        mock_ec2_client = MagicMock()
        with patch(
            "cost_toolkit.scripts.audit.aws_elastic_ip_audit.create_ec2_client",
            return_value=mock_ec2_client,
        ):
            with patch(
                "cost_toolkit.scripts.audit.aws_elastic_ip_audit.get_instance_name",
                side_effect=["web-server", "db-server"],
            ):
                _print_associated_eips(region_data, "test-key", "test-secret")

        captured = capsys.readouterr()
        assert "Associated Elastic IPs (2):" in captured.out
        assert "1.2.3.4 → Instance: i-123 (web-server)" in captured.out
        assert "5.6.7.8 → Instance: i-456 (db-server)" in captured.out

    def test_print_associated_eips_with_network_interfaces(self, capsys):
        """Test printing associated EIPs attached to network interfaces only."""
        region_data = {
            "region": "us-east-1",
            "associated_eips": [
                {
                    "public_ip": "1.2.3.4",
                    "instance_id": None,
                    "network_interface_id": "eni-123",
                }
            ],
        }

        mock_ec2_client = MagicMock()
        with patch(
            "cost_toolkit.scripts.audit.aws_elastic_ip_audit.create_ec2_client",
            return_value=mock_ec2_client,
        ):
            _print_associated_eips(region_data, "test-key", "test-secret")

        captured = capsys.readouterr()
        assert "Associated Elastic IPs (1):" in captured.out
        assert "1.2.3.4 → Network Interface: eni-123" in captured.out


class TestPrintAssociatedEipsEdgeCases:
    """Tests for _print_associated_eips function - edge cases."""

    def test_print_associated_eips_creates_client_correctly(self):
        """Test that EC2 client is created with correct parameters."""
        region_data = {
            "region": "eu-west-1",
            "associated_eips": [
                {
                    "public_ip": "1.2.3.4",
                    "instance_id": "i-123",
                    "network_interface_id": None,
                }
            ],
        }

        mock_ec2_client = MagicMock()
        with patch(
            "cost_toolkit.scripts.audit.aws_elastic_ip_audit.create_ec2_client",
            return_value=mock_ec2_client,
        ) as mock_create:
            with patch("cost_toolkit.scripts.audit.aws_elastic_ip_audit.get_instance_name"):
                _print_associated_eips(region_data, "my-key", "my-secret")

        mock_create.assert_called_once_with(
            region="eu-west-1",
            aws_access_key_id="my-key",
            aws_secret_access_key="my-secret",
        )

    def test_print_associated_eips_neither_instance_nor_eni(self, capsys):
        """Test printing associated EIPs with neither instance nor ENI (edge case)."""
        region_data = {
            "region": "us-east-1",
            "associated_eips": [
                {
                    "public_ip": "1.2.3.4",
                    "instance_id": None,
                    "network_interface_id": None,
                }
            ],
        }

        mock_ec2_client = MagicMock()
        with patch(
            "cost_toolkit.scripts.audit.aws_elastic_ip_audit.create_ec2_client",
            return_value=mock_ec2_client,
        ):
            _print_associated_eips(region_data, "test-key", "test-secret")

        captured = capsys.readouterr()
        assert "1.2.3.4 → Unknown" in captured.out


class TestPrintUnassociatedEips:
    """Tests for _print_unassociated_eips function."""

    def test_print_no_unassociated_eips(self, capsys):
        """Test printing when no unassociated EIPs exist."""
        region_data = {
            "unassociated_eips": [],
        }

        _print_unassociated_eips(region_data)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_unassociated_eips_without_tags(self, capsys):
        """Test printing unassociated EIPs without tags."""
        region_data = {
            "unassociated_eips": [
                {
                    "public_ip": "1.2.3.4",
                    "allocation_id": "eipalloc-123",
                    "monthly_cost": 3.65,
                    "tags": [],
                },
                {
                    "public_ip": "5.6.7.8",
                    "allocation_id": "eipalloc-456",
                    "monthly_cost": 3.65,
                    "tags": [],
                },
            ],
        }

        _print_unassociated_eips(region_data)

        captured = capsys.readouterr()
        assert "Unassociated Elastic IPs (2) - COSTING MONEY:" in captured.out
        assert "1.2.3.4 (ID: eipalloc-123) - $3.65/month" in captured.out
        assert "5.6.7.8 (ID: eipalloc-456) - $3.65/month" in captured.out

    def test_print_unassociated_eips_with_tags(self, capsys):
        """Test printing unassociated EIPs with tags."""
        region_data = {
            "unassociated_eips": [
                {
                    "public_ip": "1.2.3.4",
                    "allocation_id": "eipalloc-123",
                    "monthly_cost": 3.65,
                    "tags": [
                        {"Key": "Name", "Value": "old-server"},
                        {"Key": "Environment", "Value": "dev"},
                    ],
                }
            ],
        }

        _print_unassociated_eips(region_data)

        captured = capsys.readouterr()
        assert "Unassociated Elastic IPs (1) - COSTING MONEY:" in captured.out
        assert "1.2.3.4 (ID: eipalloc-123) - $3.65/month" in captured.out
        assert "(Tags: Name:old-server, Environment:dev)" in captured.out

    def test_print_unassociated_eips_single_tag(self, capsys):
        """Test printing unassociated EIP with single tag."""
        region_data = {
            "unassociated_eips": [
                {
                    "public_ip": "1.2.3.4",
                    "allocation_id": "eipalloc-123",
                    "monthly_cost": 3.65,
                    "tags": [{"Key": "Owner", "Value": "admin"}],
                }
            ],
        }

        _print_unassociated_eips(region_data)

        captured = capsys.readouterr()
        assert "(Tags: Owner:admin)" in captured.out


class TestPrintCleanupRecommendations:
    """Tests for _print_cleanup_recommendations function."""

    def test_print_cleanup_recommendations_single_region(self, capsys):
        """Test printing cleanup recommendations for single region."""
        regions_with_eips = [
            {
                "region": "us-east-1",
                "unassociated_eips": [
                    {"allocation_id": "eipalloc-123"},
                    {"allocation_id": "eipalloc-456"},
                ],
            }
        ]
        total_monthly_cost = 7.30

        _print_cleanup_recommendations(regions_with_eips, total_monthly_cost)

        captured = capsys.readouterr()
        assert "RECOMMENDATIONS:" in captured.out
        assert "Release unused Elastic IPs to eliminate charges" in captured.out
        assert "Commands to release unassociated Elastic IPs:" in captured.out
        assert "aws ec2 release-address --allocation-id eipalloc-123 --region us-east-1" in captured.out
        assert "aws ec2 release-address --allocation-id eipalloc-456 --region us-east-1" in captured.out
        assert "Total potential monthly savings: $7.30" in captured.out
        assert "Total potential annual savings: $87.60" in captured.out

    def test_print_cleanup_recommendations_multiple_regions(self, capsys):
        """Test printing cleanup recommendations for multiple regions."""
        regions_with_eips = [
            {
                "region": "us-east-1",
                "unassociated_eips": [{"allocation_id": "eipalloc-111"}],
            },
            {
                "region": "us-west-2",
                "unassociated_eips": [{"allocation_id": "eipalloc-222"}],
            },
            {
                "region": "eu-west-1",
                "unassociated_eips": [],
            },
        ]
        total_monthly_cost = 7.30

        _print_cleanup_recommendations(regions_with_eips, total_monthly_cost)

        captured = capsys.readouterr()
        assert "aws ec2 release-address --allocation-id eipalloc-111 --region us-east-1" in captured.out
        assert "aws ec2 release-address --allocation-id eipalloc-222 --region us-west-2" in captured.out
        assert "eu-west-1" not in captured.out

    def test_print_cleanup_recommendations_cost_formatting(self, capsys):
        """Test cost formatting in recommendations."""
        regions_with_eips = [
            {
                "region": "us-east-1",
                "unassociated_eips": [{"allocation_id": "eipalloc-123"}],
            }
        ]
        total_monthly_cost = 3.65

        _print_cleanup_recommendations(regions_with_eips, total_monthly_cost)

        captured = capsys.readouterr()
        assert "Total potential monthly savings: $3.65" in captured.out
        assert "Total potential annual savings: $43.80" in captured.out
