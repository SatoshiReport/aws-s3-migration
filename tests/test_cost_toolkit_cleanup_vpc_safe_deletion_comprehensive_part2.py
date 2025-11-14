"""Comprehensive tests for aws_vpc_safe_deletion.py - Part 2."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_vpc_safe_deletion import (
    _delete_vpcs,
    _get_safe_vpcs,
    _print_vpc_deletion_summary,
    delete_vpc_and_dependencies,
    main,
)


class TestDeleteVpcAndDependencies:
    """Tests for delete_vpc_and_dependencies function."""

    def test_delete_vpc_success(self, capsys):
        """Test successful VPC and dependencies deletion."""
        with patch("boto3.client") as mock_boto3:
            mock_ec2 = MagicMock()
            mock_boto3.return_value = mock_ec2
            mock_ec2.describe_internet_gateways.return_value = {"InternetGateways": []}
            mock_ec2.describe_vpc_endpoints.return_value = {"VpcEndpoints": []}
            mock_ec2.describe_nat_gateways.return_value = {"NatGateways": []}
            mock_ec2.describe_security_groups.return_value = {"SecurityGroups": []}
            mock_ec2.describe_network_acls.return_value = {"NetworkAcls": []}
            mock_ec2.describe_route_tables.return_value = {"RouteTables": []}
            mock_ec2.describe_subnets.return_value = {"Subnets": []}

            result = delete_vpc_and_dependencies("vpc-123", "us-east-1")

            assert result is True
            mock_ec2.delete_vpc.assert_called_once_with(VpcId="vpc-123")
            captured = capsys.readouterr()
            assert "VPC vpc-123 deleted successfully" in captured.out

    def test_delete_vpc_failure(self, capsys):
        """Test VPC deletion failure."""
        with patch("boto3.client") as mock_boto3:
            mock_ec2 = MagicMock()
            mock_boto3.return_value = mock_ec2
            mock_ec2.describe_internet_gateways.return_value = {"InternetGateways": []}
            mock_ec2.describe_vpc_endpoints.return_value = {"VpcEndpoints": []}
            mock_ec2.describe_nat_gateways.return_value = {"NatGateways": []}
            mock_ec2.describe_security_groups.return_value = {"SecurityGroups": []}
            mock_ec2.describe_network_acls.return_value = {"NetworkAcls": []}
            mock_ec2.describe_route_tables.return_value = {"RouteTables": []}
            mock_ec2.describe_subnets.return_value = {"Subnets": []}
            mock_ec2.delete_vpc.side_effect = ClientError(
                {"Error": {"Code": "DependencyViolation"}}, "delete_vpc"
            )

            result = delete_vpc_and_dependencies("vpc-123", "us-east-1")

            assert result is False
            captured = capsys.readouterr()
            assert "Error deleting VPC vpc-123" in captured.out

    def test_delete_vpc_with_client_error(self, capsys):
        """Test deletion with client error."""
        with patch("boto3.client") as mock_boto3:
            mock_boto3.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "create_client"
            )

            result = delete_vpc_and_dependencies("vpc-123", "us-east-1")

            assert result is False
            captured = capsys.readouterr()
            assert "Error during VPC deletion process" in captured.out


def test_get_safe_vpcs_returns_list():
    """Test that function returns list of VPCs."""
    result = _get_safe_vpcs()

    assert isinstance(result, list)
    assert len(result) > 0
    for vpc_id, region in result:
        assert vpc_id.startswith("vpc-")
        assert isinstance(region, str)


class TestDeleteVpcs:
    """Tests for _delete_vpcs function."""

    def test_delete_vpcs_all_success(self, capsys):
        """Test deleting all VPCs successfully."""
        safe_vpcs = [("vpc-1", "us-east-1"), ("vpc-2", "us-west-2")]

        with patch(
            "cost_toolkit.scripts.cleanup.aws_vpc_safe_deletion.delete_vpc_and_dependencies"
        ) as mock_delete:
            with patch("time.sleep"):
                mock_delete.return_value = True

                result = _delete_vpcs(safe_vpcs)

                assert len(result) == 2
                assert all(success for _, _, success in result)
                captured = capsys.readouterr()
                assert "deletion completed successfully" in captured.out

    def test_delete_vpcs_with_failures(self, capsys):
        """Test deleting VPCs with some failures."""
        safe_vpcs = [("vpc-1", "us-east-1"), ("vpc-2", "us-west-2")]

        with patch(
            "cost_toolkit.scripts.cleanup.aws_vpc_safe_deletion.delete_vpc_and_dependencies"
        ) as mock_delete:
            with patch("time.sleep"):
                mock_delete.side_effect = [True, False]

                result = _delete_vpcs(safe_vpcs)

                assert len(result) == 2
                assert result[0][2] is True
                assert result[1][2] is False
                captured = capsys.readouterr()
                assert "deletion failed" in captured.out


class TestPrintVpcDeletionSummary:
    """Tests for _print_vpc_deletion_summary function."""

    def test_print_all_successful(self, capsys):
        """Test summary with all successful deletions."""
        deletion_results = [
            ("vpc-1", "us-east-1", True),
            ("vpc-2", "us-west-2", True),
        ]

        _print_vpc_deletion_summary(deletion_results)

        captured = capsys.readouterr()
        assert "Successfully deleted VPCs: 2" in captured.out
        assert "vpc-1" in captured.out
        assert "vpc-2" in captured.out
        assert "Failed to delete VPCs" not in captured.out

    def test_print_with_failures(self, capsys):
        """Test summary with some failures."""
        deletion_results = [
            ("vpc-1", "us-east-1", True),
            ("vpc-2", "us-west-2", False),
            ("vpc-3", "us-east-2", False),
        ]

        _print_vpc_deletion_summary(deletion_results)

        captured = capsys.readouterr()
        assert "Successfully deleted VPCs: 1" in captured.out
        assert "Failed to delete VPCs: 2" in captured.out

    def test_print_empty_results(self, capsys):
        """Test summary with no results."""
        _print_vpc_deletion_summary([])

        captured = capsys.readouterr()
        assert "Successfully deleted VPCs: 0" in captured.out


class TestMain:
    """Tests for main function."""

    def test_main_execution(self, capsys):
        """Test main function execution."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_vpc_safe_deletion._get_safe_vpcs"
        ) as mock_get_vpcs:
            with patch(
                "cost_toolkit.scripts.cleanup.aws_vpc_safe_deletion._delete_vpcs"
            ) as mock_delete:
                mock_get_vpcs.return_value = [("vpc-1", "us-east-1")]
                mock_delete.return_value = [("vpc-1", "us-east-1", True)]

                main()

                captured = capsys.readouterr()
                assert "AWS VPC Safe Deletion" in captured.out
                assert "DELETION SUMMARY" in captured.out

    def test_main_calls_delete_vpcs(self):
        """Test that main calls _delete_vpcs."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_vpc_safe_deletion._get_safe_vpcs"
        ) as mock_get_vpcs:
            with patch(
                "cost_toolkit.scripts.cleanup.aws_vpc_safe_deletion._delete_vpcs"
            ) as mock_delete:
                mock_get_vpcs.return_value = [("vpc-1", "us-east-1")]
                mock_delete.return_value = []

                main()

                mock_delete.assert_called_once()
