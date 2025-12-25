"""Extended comprehensive tests for aws_comprehensive_vpc_audit.py - Part 2."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.common.aws_test_constants import DEFAULT_TEST_REGIONS
from cost_toolkit.scripts.audit.aws_comprehensive_vpc_audit import (
    _has_region_resources,
    _print_cleanup_recommendations,
    _print_detailed_results,
    _print_region_summary,
    audit_comprehensive_vpc,
    main,
)


def test_print_cleanup_recommendations_print_recommendations(capsys):
    """Test printing cleanup recommendations."""
    _print_cleanup_recommendations(5)

    captured = capsys.readouterr()
    assert "CLEANUP RECOMMENDATIONS" in captured.out
    assert "Delete unused security groups" in captured.out
    assert "Delete unused network interfaces" in captured.out
    assert "Review VPC endpoints" in captured.out
    assert "Cleanup commands will be provided after confirmation" in captured.out


def test_print_cleanup_no_recommendations_no_recommendations(capsys):
    """Test when no cleanup recommendations needed."""
    _print_cleanup_recommendations(0)

    captured = capsys.readouterr()
    assert "CLEANUP RECOMMENDATIONS" not in captured.out


class TestHasRegionResources:
    """Tests for _has_region_resources function."""

    def test_has_resources_with_vpcs(self):
        """Test region has resources when VPCs present."""
        region_data = {
            "vpcs": [{"vpc_id": "vpc-123"}],
            "unused_security_groups": [],
            "unused_network_interfaces": [],
            "vpc_endpoints": [],
        }

        assert _has_region_resources(region_data) is True

    def test_has_resources_with_unused_sgs(self):
        """Test region has resources with unused security groups."""
        region_data = {
            "vpcs": [],
            "unused_security_groups": [{"group_id": "sg-123"}],
            "unused_network_interfaces": [],
            "vpc_endpoints": [],
        }

        assert _has_region_resources(region_data) is True

    def test_has_no_resources(self):
        """Test region has no resources."""
        region_data = {
            "vpcs": [],
            "unused_security_groups": [],
            "unused_network_interfaces": [],
            "vpc_endpoints": [],
        }

        assert _has_region_resources(region_data) is False

    def test_has_resources_none(self):
        """Test when region data is None."""
        assert _has_region_resources(None) is False


def test_print_region_summary_print_summary(capsys):
    """Test printing region summary."""
    region_data = {
        "vpcs": [{"vpc_id": "vpc-1"}, {"vpc_id": "vpc-2"}],
        "unused_security_groups": [{"group_id": "sg-1"}],
        "unused_network_interfaces": [{"interface_id": "eni-1"}],
        "vpc_endpoints": [{"endpoint_id": "vpce-1"}],
    }

    _print_region_summary(region_data)

    captured = capsys.readouterr()
    assert "Found 2 VPC(s)" in captured.out
    assert "1 unused security groups" in captured.out
    assert "1 unused network interfaces" in captured.out
    assert "1 VPC endpoints" in captured.out


def test_print_detailed_results_print_results(capsys):
    """Test printing detailed results."""
    regions_data = [
        {
            "region": "us-east-1",
            "vpcs": [
                {
                    "vpc_id": "vpc-123",
                    "name": "test-vpc",
                    "cidr": "10.0.0.0/16",
                    "is_default": False,
                    "instance_count": 0,
                    "instances": [],
                    "subnets": [],
                    "security_groups": [],
                    "route_tables": [],
                    "internet_gateways": [],
                    "nat_gateways": [],
                }
            ],
            "unused_security_groups": [],
            "unused_network_interfaces": [],
            "vpc_endpoints": [],
        }
    ]

    _print_detailed_results(regions_data)

    captured = capsys.readouterr()
    assert "Region: us-east-1" in captured.out
    assert "VPC: vpc-123 (test-vpc)" in captured.out


class TestAuditComprehensiveVpc:
    """Tests for audit_comprehensive_vpc function."""

    def test_audit_with_resources(self, capsys):
        """Test comprehensive VPC audit with resources."""
        with patch("cost_toolkit.common.credential_utils.setup_aws_credentials") as mock_creds:
            with patch("cost_toolkit.scripts.audit.aws_comprehensive_vpc_audit.audit_vpc_resources_in_region") as mock_audit:
                mock_creds.return_value = ("test-key", "test-secret")
                mock_audit.return_value = {
                    "region": "us-east-1",
                    "vpcs": [
                        {
                            "vpc_id": "vpc-123",
                            "name": "test-vpc",
                            "cidr": "10.0.0.0/16",
                            "is_default": False,
                            "instance_count": 0,
                            "instances": [],
                            "subnets": [],
                            "security_groups": [],
                            "route_tables": [],
                            "internet_gateways": [],
                            "nat_gateways": [],
                        }
                    ],
                    "unused_security_groups": [
                        {
                            "group_id": "sg-123",
                            "name": "unused-sg",
                            "vpc_id": "vpc-123",
                            "description": "Unused",
                        }
                    ],
                    "unused_network_interfaces": [],
                    "vpc_endpoints": [],
                }

                audit_comprehensive_vpc()

        captured = capsys.readouterr()
        assert "AWS Comprehensive VPC Audit" in captured.out
        assert "COMPREHENSIVE VPC AUDIT RESULTS" in captured.out
        vpcs_per_region = len(mock_audit.return_value["vpcs"])
        unused_per_region = len(mock_audit.return_value["unused_security_groups"]) + len(
            mock_audit.return_value["unused_network_interfaces"]
        )
        expected_vpcs = len(DEFAULT_TEST_REGIONS) * vpcs_per_region
        expected_unused = len(DEFAULT_TEST_REGIONS) * unused_per_region
        assert f"Total VPCs found: {expected_vpcs}" in captured.out
        assert f"Total unused resources: {expected_unused}" in captured.out

    def test_audit_no_resources(self, capsys):
        """Test comprehensive VPC audit with no resources."""
        with patch("cost_toolkit.common.credential_utils.setup_aws_credentials") as mock_creds:
            with patch("cost_toolkit.scripts.audit.aws_comprehensive_vpc_audit.audit_vpc_resources_in_region") as mock_audit:
                mock_creds.return_value = ("test-key", "test-secret")
                mock_audit.return_value = None

                audit_comprehensive_vpc()

        captured = capsys.readouterr()
        assert "No VPC resources found in audited regions" in captured.out


def test_main_function_main_execution(capsys):
    """Test main function execution."""
    with patch("cost_toolkit.scripts.audit.aws_comprehensive_vpc_audit.audit_comprehensive_vpc"):
        main()

    captured = capsys.readouterr()
    assert captured.out == "" or "VPC" in captured.out


def test_main_client_error_main_error(capsys):
    """Test main function with client error."""
    with patch("cost_toolkit.scripts.audit.aws_comprehensive_vpc_audit.audit_comprehensive_vpc") as mock_audit:
        mock_audit.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "describe_vpcs")

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Script failed" in captured.out
