"""Comprehensive tests for aws_cleanup_unused_resources.py - Part 3."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.cleanup.aws_cleanup_unused_resources import (
    _group_resources_by_region,
    delete_unused_subnets,
)


class TestDeleteUnusedSubnets:
    """Tests for delete_unused_subnets function."""

    def test_delete_success(self, capsys):
        """Test successful deletion of subnets."""
        unused_subnets = [
            {"SubnetId": "subnet-1", "CidrBlock": "10.0.1.0/24"},
            {"SubnetId": "subnet-2", "CidrBlock": "10.0.2.0/24"},
        ]

        with patch("boto3.client") as mock_boto3:
            mock_ec2 = MagicMock()
            mock_boto3.return_value = mock_ec2

            result = delete_unused_subnets(unused_subnets, "us-east-1")

            assert result is True
            assert mock_ec2.delete_subnet.call_count == 2
            captured = capsys.readouterr()
            assert "Deleted: 2" in captured.out

    def test_delete_empty_list(self, capsys):
        """Test deletion with empty list."""
        result = delete_unused_subnets([], "us-east-1")

        assert result is True
        captured = capsys.readouterr()
        assert "No unused subnets to delete" in captured.out


class TestGroupResourcesByRegion:
    """Tests for _group_resources_by_region function."""

    def test_group_resources(self):
        """Test grouping resources by region."""
        all_unused_sgs = [
            ("us-east-1", {"GroupId": "sg-1"}),
            ("us-east-1", {"GroupId": "sg-2"}),
            ("us-west-2", {"GroupId": "sg-3"}),
        ]
        all_unused_subnets = [
            ("us-east-1", {"SubnetId": "subnet-1"}),
            ("us-west-2", {"SubnetId": "subnet-2"}),
        ]

        result = _group_resources_by_region(all_unused_sgs, all_unused_subnets)

        assert len(result) == 2
        assert len(result["us-east-1"]["sgs"]) == 2
        assert len(result["us-east-1"]["subnets"]) == 1
        assert len(result["us-west-2"]["sgs"]) == 1
        assert len(result["us-west-2"]["subnets"]) == 1

    def test_group_empty_resources(self):
        """Test grouping with no resources."""
        result = _group_resources_by_region([], [])

        assert len(result) == 0
