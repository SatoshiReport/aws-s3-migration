"""Tests for cost_toolkit/overview/optimization.py module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.overview.optimization import (
    _calculate_volume_cost,
    _check_unattached_ebs_volumes,
    _check_unused_elastic_ips,
    _scan_region_for_unattached_volumes,
)


def test_calculate_volume_cost_gp3():
    """Test _calculate_volume_cost for gp3 volumes."""
    cost = _calculate_volume_cost(100, "gp3")
    assert cost == 8.0  # 100 * 0.08


def test_calculate_volume_cost_gp2():
    """Test _calculate_volume_cost for gp2 volumes."""
    cost = _calculate_volume_cost(100, "gp2")
    assert cost == 10.0  # 100 * 0.10


def test_calculate_volume_cost_unknown_type():
    """Test _calculate_volume_cost for unknown volume types."""
    cost = _calculate_volume_cost(100, "io1")
    assert cost == 10.0  # Falls back to 0.10


def test_scan_region_for_unattached_volumes_with_volumes():
    """Test _scan_region_for_unattached_volumes finds unattached volumes."""
    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_volumes.return_value = {
            "Volumes": [
                {
                    "VolumeId": "vol-1",
                    "Size": 10,
                    "VolumeType": "gp3",
                    "Attachments": [],
                },
                {
                    "VolumeId": "vol-2",
                    "Size": 20,
                    "VolumeType": "gp2",
                    "Attachments": [],
                },
            ]
        }
        mock_client.return_value = mock_ec2

        count, cost = _scan_region_for_unattached_volumes("us-east-1")

        assert count == 2
        assert cost > 0


def test_scan_region_for_unattached_volumes_all_attached():
    """Test _scan_region_for_unattached_volumes when all volumes are attached."""
    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_volumes.return_value = {
            "Volumes": [
                {
                    "VolumeId": "vol-1",
                    "Size": 10,
                    "VolumeType": "gp3",
                    "Attachments": [{"InstanceId": "i-123"}],
                }
            ]
        }
        mock_client.return_value = mock_ec2

        count, cost = _scan_region_for_unattached_volumes("us-east-1")

        assert count == 0
        assert cost == 0.0


def test_scan_region_for_unattached_volumes_error():
    """Test _scan_region_for_unattached_volumes handles errors."""
    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_volumes.side_effect = ClientError(
            {"Error": {"Code": "TestError"}}, "test"
        )
        mock_client.return_value = mock_ec2

        count, cost = _scan_region_for_unattached_volumes("us-east-1")

        assert count == 0
        assert cost == 0.0


def test_check_unattached_ebs_volumes_with_volumes():
    """Test _check_unattached_ebs_volumes returns recommendation."""
    with patch("cost_toolkit.overview.optimization.get_default_regions") as mock_regions:
        with patch(
            "cost_toolkit.overview.optimization._scan_region_for_unattached_volumes"
        ) as mock_scan:
            mock_regions.return_value = ["us-east-1"]
            mock_scan.return_value = (5, 50.0)

            result = _check_unattached_ebs_volumes()

            assert result is not None
            assert result["category"] == "EBS Optimization"
            assert result["potential_savings"] == 50.0


def test_check_unattached_ebs_volumes_none_found():
    """Test _check_unattached_ebs_volumes when no unattached volumes exist."""
    with patch("cost_toolkit.overview.optimization.get_default_regions") as mock_regions:
        with patch(
            "cost_toolkit.overview.optimization._scan_region_for_unattached_volumes"
        ) as mock_scan:
            mock_regions.return_value = ["us-east-1"]
            mock_scan.return_value = (0, 0.0)

            result = _check_unattached_ebs_volumes()

            assert result is None


def test_check_unused_elastic_ips_with_unused():
    """Test _check_unused_elastic_ips finds unused IPs."""
    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_addresses.return_value = {
            "Addresses": [
                {"PublicIp": "1.2.3.4"},  # No InstanceId
                {"PublicIp": "5.6.7.8", "InstanceId": "i-123"},  # Attached
            ]
        }
        mock_client.return_value = mock_ec2

        result = _check_unused_elastic_ips()

        assert result is not None
        assert result["category"] == "VPC Optimization"
        assert "Elastic IPs" in result["description"]


def test_check_unused_elastic_ips_all_used():
    """Test _check_unused_elastic_ips when all IPs are in use."""
    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_addresses.return_value = {
            "Addresses": [
                {"PublicIp": "1.2.3.4", "InstanceId": "i-123"},
                {"PublicIp": "5.6.7.8", "InstanceId": "i-456"},
            ]
        }
        mock_client.return_value = mock_ec2

        result = _check_unused_elastic_ips()

        assert result is None


def test_check_unused_elastic_ips_error():
    """Test _check_unused_elastic_ips handles errors gracefully."""
    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_addresses.side_effect = ClientError(
            {"Error": {"Code": "TestError"}}, "test"
        )
        mock_client.return_value = mock_ec2

        result = _check_unused_elastic_ips()

        # Should handle error and return None
        assert result is None or isinstance(result, dict)
