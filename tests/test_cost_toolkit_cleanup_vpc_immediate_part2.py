"""Comprehensive tests for aws_vpc_immediate_cleanup.py - Part 2."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup import (
    _categorize_vpcs,
    _check_vpc_rds_instances,
    _print_vpc_analysis,
    _print_vpc_recommendations,
    analyze_vpc_dependencies,
    main,
)


class TestCheckVpcRdsInstances:
    """Tests for _check_vpc_rds_instances function."""

    def test_check_with_rds_instances(self):
        """Test checking VPC with RDS instances."""
        with patch("boto3.client") as mock_boto3:
            mock_rds = MagicMock()
            mock_boto3.return_value = mock_rds
            mock_rds.describe_db_instances.return_value = {
                "DBInstances": [
                    {
                        "DBInstanceIdentifier": "db-1",
                        "DBSubnetGroup": {"VpcId": "vpc-123"},
                    },
                    {
                        "DBInstanceIdentifier": "db-2",
                        "DBSubnetGroup": {"VpcId": "vpc-123"},
                    },
                    {
                        "DBInstanceIdentifier": "db-3",
                        "DBSubnetGroup": {"VpcId": "vpc-456"},
                    },
                ]
            }

            analysis = {"can_delete": True, "blocking_resources": []}
            _check_vpc_rds_instances("us-east-1", "vpc-123", analysis)

            assert analysis["can_delete"] is False
            assert "2 RDS instances" in analysis["blocking_resources"]

    def test_check_with_no_rds_instances(self):
        """Test checking VPC with no RDS instances."""
        with patch("boto3.client") as mock_boto3:
            mock_rds = MagicMock()
            mock_boto3.return_value = mock_rds
            mock_rds.describe_db_instances.return_value = {"DBInstances": []}

            analysis = {"can_delete": True, "blocking_resources": []}
            _check_vpc_rds_instances("us-east-1", "vpc-123", analysis)

            assert analysis["can_delete"] is True

    def test_check_with_error(self, capsys):
        """Test error handling when checking RDS instances."""
        with patch("boto3.client") as mock_boto3:
            mock_rds = MagicMock()
            mock_boto3.return_value = mock_rds
            mock_rds.describe_db_instances.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "describe_db_instances")

            analysis = {"can_delete": True, "blocking_resources": []}
            _check_vpc_rds_instances("us-east-1", "vpc-123", analysis)

            captured = capsys.readouterr()
            assert "Warning: Could not check RDS instances" in captured.out


class TestPrintVpcAnalysis:
    """Tests for _print_vpc_analysis function."""

    def test_print_default_vpc_can_delete(self, capsys):
        """Test printing analysis for deletable default VPC."""
        analysis = {
            "can_delete": True,
            "dependencies": ["1 Internet Gateways"],
            "blocking_resources": [],
        }

        _print_vpc_analysis("vpc-123", True, analysis)

        captured = capsys.readouterr()
        assert "vpc-123" in captured.out
        assert "Default" in captured.out
        assert "Yes" in captured.out
        assert "1 Internet Gateways" in captured.out

    def test_print_custom_vpc_cannot_delete(self, capsys):
        """Test printing analysis for non-deletable custom VPC."""
        analysis = {
            "can_delete": False,
            "dependencies": [],
            "blocking_resources": ["2 EC2 instances", "1 NAT Gateways"],
        }

        _print_vpc_analysis("vpc-456", False, analysis)

        captured = capsys.readouterr()
        assert "vpc-456" in captured.out
        assert "Custom" in captured.out
        assert "No" in captured.out
        assert "2 EC2 instances" in captured.out
        assert "1 NAT Gateways" in captured.out


class TestAnalyzeVpcDependencies:
    """Tests for analyze_vpc_dependencies function."""

    def test_analyze_vpc_dependencies_success(self, capsys):
        """Test successful VPC dependency analysis."""
        with patch("boto3.client") as mock_boto3:
            mock_ec2 = MagicMock()
            mock_boto3.return_value = mock_ec2
            mock_ec2.describe_vpcs.return_value = {
                "Vpcs": [
                    {"VpcId": "vpc-123", "IsDefault": False},
                    {"VpcId": "vpc-456", "IsDefault": True},
                ]
            }
            mock_ec2.describe_instances.return_value = {"Reservations": []}
            mock_ec2.describe_internet_gateways.return_value = {"InternetGateways": []}
            mock_ec2.describe_nat_gateways.return_value = {"NatGateways": []}
            mock_ec2.describe_vpc_endpoints.return_value = {"VpcEndpoints": []}

            with (
                patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup._check_vpc_load_balancers"),  # pylint: disable=line-too-long
                patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup._check_vpc_rds_instances"),  # pylint: disable=line-too-long
            ):
                result = analyze_vpc_dependencies("us-east-1")

            assert "vpc-123" in result
            assert "vpc-456" in result
            assert result["vpc-123"]["can_delete"] is True
            assert result["vpc-456"]["can_delete"] is False  # Default VPCs should not be deleted
            captured = capsys.readouterr()
            assert "Analyzing VPC dependencies" in captured.out

    def test_analyze_vpc_dependencies_client_error(self, capsys):
        """Test handling of client error during analysis."""
        with patch("boto3.client") as mock_boto3:
            mock_ec2 = MagicMock()
            mock_boto3.return_value = mock_ec2
            mock_ec2.describe_vpcs.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "describe_vpcs")

            result = analyze_vpc_dependencies("us-east-1")

            assert not result
            captured = capsys.readouterr()
            assert "Error analyzing VPC dependencies" in captured.out


class TestCategorizeVpcs:
    """Tests for _categorize_vpcs function."""

    def test_categorize_empty_analysis(self):
        """Test categorizing with no VPCs."""
        all_vpc_analysis = {}

        deletable, non_deletable = _categorize_vpcs(all_vpc_analysis)

        assert len(deletable) == 0
        assert len(non_deletable) == 0

    def test_categorize_mixed_vpcs(self):
        """Test categorizing with mix of deletable and non-deletable VPCs."""
        all_vpc_analysis = {
            "us-east-1": {
                "vpc-123": {
                    "can_delete": True,
                    "dependencies": [],
                    "blocking_resources": [],
                    "is_default": False,
                },
                "vpc-456": {
                    "can_delete": False,
                    "dependencies": [],
                    "blocking_resources": ["2 EC2 instances"],
                    "is_default": True,
                },
            },
            "us-west-2": {
                "vpc-789": {
                    "can_delete": True,
                    "dependencies": ["1 Internet Gateways"],
                    "blocking_resources": [],
                    "is_default": False,
                }
            },
        }

        deletable, non_deletable = _categorize_vpcs(all_vpc_analysis)

        assert len(deletable) == 2
        assert len(non_deletable) == 1
        assert any(vpc[1] == "vpc-123" for vpc in deletable)
        assert any(vpc[1] == "vpc-789" for vpc in deletable)
        assert non_deletable[0][1] == "vpc-456"


class TestPrintVpcRecommendations:
    """Tests for _print_vpc_recommendations function."""

    def test_print_recommendations_with_deletable(self, capsys):
        """Test printing recommendations with deletable VPCs."""
        deletable_vpcs = [
            (
                "us-east-1",
                "vpc-123",
                {
                    "dependencies": ["1 Internet Gateways"],
                    "is_default": False,
                },
            ),
            (
                "us-west-2",
                "vpc-456",
                {
                    "dependencies": [],
                    "is_default": False,
                },
            ),
        ]
        non_deletable_vpcs = []

        _print_vpc_recommendations(deletable_vpcs, non_deletable_vpcs)

        captured = capsys.readouterr()
        assert "VPC DELETION ANALYSIS" in captured.out
        assert "CAN be safely deleted (2)" in captured.out
        assert "vpc-123" in captured.out
        assert "vpc-456" in captured.out
        assert "NEXT STEPS" in captured.out

    def test_print_recommendations_with_non_deletable(self, capsys):
        """Test printing recommendations with non-deletable VPCs."""
        deletable_vpcs = []
        non_deletable_vpcs = [
            (
                "us-east-1",
                "vpc-123",
                {
                    "blocking_resources": ["2 EC2 instances"],
                    "is_default": True,
                },
            ),
            (
                "us-west-2",
                "vpc-456",
                {
                    "blocking_resources": ["1 NAT Gateways"],
                    "is_default": False,
                },
            ),
        ]

        _print_vpc_recommendations(deletable_vpcs, non_deletable_vpcs)

        captured = capsys.readouterr()
        assert "CANNOT be deleted (2)" in captured.out
        assert "vpc-123" in captured.out
        assert "Default VPC" in captured.out
        assert "vpc-456" in captured.out
        assert "1 NAT Gateways" in captured.out

    def test_print_recommendations_mixed(self, capsys):
        """Test printing recommendations with both types."""
        deletable_vpcs = [("us-east-1", "vpc-123", {"dependencies": [], "is_default": False})]
        non_deletable_vpcs = [
            (
                "us-west-2",
                "vpc-456",
                {"blocking_resources": ["2 EC2 instances"], "is_default": False},
            )
        ]

        _print_vpc_recommendations(deletable_vpcs, non_deletable_vpcs)

        captured = capsys.readouterr()
        assert "1" in captured.out or "deletable" in captured.out.lower()


class TestMain:
    """Tests for main function."""

    def test_main_success(self, capsys):
        """Test successful main execution."""
        with (
            patch(
                "cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.release_public_ip_from_instance"  # pylint: disable=line-too-long
            ) as mock_release,
            patch(
                "cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.remove_detached_internet_gateway"  # pylint: disable=line-too-long
            ) as mock_remove,
            patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.analyze_vpc_dependencies") as mock_analyze,
            patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup._categorize_vpcs") as mock_categorize,
            patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup._print_vpc_recommendations"),
        ):
            mock_release.return_value = True
            mock_remove.return_value = True
            mock_analyze.return_value = {}
            mock_categorize.return_value = ([], [])

            main()

            captured = capsys.readouterr()
            assert "AWS VPC Immediate Cleanup" in captured.out
            assert "TASK 1" in captured.out
            assert "TASK 2" in captured.out
            assert "TASK 3" in captured.out
            assert "CLEANUP SUMMARY" in captured.out

    def test_main_with_failures(self, capsys):
        """Test main with task failures."""
        with (
            patch(
                "cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.release_public_ip_from_instance"  # pylint: disable=line-too-long
            ) as mock_release,
            patch(
                "cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.remove_detached_internet_gateway"  # pylint: disable=line-too-long
            ) as mock_remove,
            patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.analyze_vpc_dependencies") as mock_analyze,
            patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup._categorize_vpcs") as mock_categorize,
            patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup._print_vpc_recommendations"),
        ):
            mock_release.return_value = False
            mock_remove.return_value = False
            mock_analyze.return_value = {}
            mock_categorize.return_value = ([], [])

            main()

            captured = capsys.readouterr()
            assert "Failed" in captured.out or "Manual action required" in captured.out

    def test_main_with_non_deletable_vpcs(self, capsys):
        """Test main with non-deletable VPCs."""
        with (
            patch(
                "cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.release_public_ip_from_instance"  # pylint: disable=line-too-long
            ),
            patch(
                "cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.remove_detached_internet_gateway"  # pylint: disable=line-too-long
            ),
            patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.analyze_vpc_dependencies") as mock_analyze,
            patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup._categorize_vpcs") as mock_categorize,
            patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup._print_vpc_recommendations"),
        ):
            mock_analyze.return_value = {}
            # Return some non-deletable VPCs
            mock_categorize.return_value = ([], [("us-east-1", "vpc-123", {})])

            main()

            captured = capsys.readouterr()
            assert "VPCs have blocking resources" in captured.out or "blocking" in captured.out.lower()
