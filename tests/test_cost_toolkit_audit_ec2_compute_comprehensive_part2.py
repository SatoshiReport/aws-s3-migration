"""Comprehensive tests for aws_ec2_compute_detailed_audit.py - Part 2."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_ec2_compute_detailed_audit import (
    GP3_DEFAULT_THROUGHPUT_MBS,
    _process_single_volume,
    analyze_ebs_volumes_in_region,
    calculate_ebs_monthly_cost,
)


def _assert_volume_properties(result):
    """Helper to assert basic volume properties."""
    assert result["volume_id"] == "vol-123"
    assert result["volume_type"] == "gp3"
    assert result["size_gb"] == 100
    assert result["state"] == "in-use"
    assert result["attached_to"] == "i-123"


def _assert_volume_output(capsys):
    """Helper to assert volume output messages."""
    captured = capsys.readouterr()
    assert "Volume: vol-123" in captured.out
    assert "Type: gp3" in captured.out
    assert "Size: 100 GB" in captured.out
    assert "IOPS: 3000" in captured.out
    assert "Throughput: 125 MB/s" in captured.out


def test_process_single_volume_process_volume(capsys):
    """Test processing a single EBS volume."""
    volume = {
        "VolumeId": "vol-123",
        "VolumeType": "gp3",
        "Size": 100,
        "State": "in-use",
        "Iops": 3000,
        "Throughput": 125,
        "Attachments": [{"InstanceId": "i-123"}],
    }

    result = _process_single_volume(volume)

    _assert_volume_properties(result)
    assert result["monthly_cost"] == 8.0
    _assert_volume_output(capsys)


class TestAnalyzeEbsVolumes:
    """Tests for analyze_ebs_volumes_in_region function."""

    def test_analyze_with_volumes(self, capsys):
        """Test analyzing region with EBS volumes."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_volumes.return_value = {
                "Volumes": [
                    {
                        "VolumeId": "vol-123",
                        "VolumeType": "gp3",
                        "Size": 50,
                        "State": "available",
                        "Iops": 3000,
                        "Throughput": 125,
                        "Attachments": [],
                    }
                ]
            }
            mock_client.return_value = mock_ec2

            volumes = analyze_ebs_volumes_in_region("us-east-1")

        assert len(volumes) == 1
        assert volumes[0]["volume_id"] == "vol-123"
        captured = capsys.readouterr()
        assert "Analyzing EBS Storage in us-east-1" in captured.out

    def test_analyze_no_volumes(self, capsys):
        """Test analyzing region with no volumes."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_volumes.return_value = {"Volumes": []}
            mock_client.return_value = mock_ec2

            volumes = analyze_ebs_volumes_in_region("us-west-2")

        assert len(volumes) == 0
        captured = capsys.readouterr()
        assert "No EBS volumes found in us-west-2" in captured.out

    def test_analyze_client_error(self, capsys):
        """Test error handling when analyzing volumes."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_volumes.side_effect = ClientError(
                {"Error": {"Code": "UnauthorizedOperation"}}, "describe_volumes"
            )
            mock_client.return_value = mock_ec2

            volumes = analyze_ebs_volumes_in_region("eu-west-1")

        assert volumes == []
        captured = capsys.readouterr()
        assert "Error analyzing EBS in eu-west-1" in captured.out


class TestCalculateEbsMonthlyCost:
    """Tests for calculate_ebs_monthly_cost function."""

    def test_gp3_base_cost(self):
        """Test gp3 base cost calculation."""
        cost = calculate_ebs_monthly_cost("gp3", 100, 3000, GP3_DEFAULT_THROUGHPUT_MBS)
        assert cost == 8.0

    def test_gp2_cost(self):
        """Test gp2 cost calculation."""
        cost = calculate_ebs_monthly_cost("gp2", 100, 0, 0)
        assert cost == 10.0

    def test_io1_with_extra_iops(self):
        """Test io1 with extra IOPS cost."""
        cost = calculate_ebs_monthly_cost("io1", 100, 500, 0)
        extra_iops = 500 - (100 * 3)
        expected_cost = (0.125 * 100) + (extra_iops * 0.065)
        assert cost == expected_cost

    def test_io2_with_base_iops(self):
        """Test io2 with base IOPS."""
        cost = calculate_ebs_monthly_cost("io2", 100, 300, 0)
        assert cost == 12.5

    def test_gp3_with_extra_throughput(self):
        """Test gp3 with extra throughput cost."""
        cost = calculate_ebs_monthly_cost("gp3", 100, 3000, 200)
        extra_throughput = 200 - GP3_DEFAULT_THROUGHPUT_MBS
        expected_cost = (0.08 * 100) + (extra_throughput * 0.04)
        assert cost == expected_cost

    def test_st1_cost(self):
        """Test st1 cost calculation."""
        cost = calculate_ebs_monthly_cost("st1", 500, 0, 0)
        assert cost == 22.5

    def test_sc1_cost(self):
        """Test sc1 cost calculation."""
        cost = calculate_ebs_monthly_cost("sc1", 500, 0, 0)
        assert cost == 12.5

    def test_unknown_volume_type(self):
        """Test fallback for unknown volume types."""
        cost = calculate_ebs_monthly_cost("unknown", 100, 0, 0)
        assert cost == 10.0
