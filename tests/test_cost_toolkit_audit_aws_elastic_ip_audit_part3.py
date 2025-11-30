"""Comprehensive tests for aws_elastic_ip_audit.py - Part 3: Main audit function tests."""

from __future__ import annotations

from unittest.mock import patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_elastic_ip_audit import (
    audit_all_elastic_ips,
    main,
)


class TestAuditAllElasticIpsBasicCases:
    """Tests for audit_all_elastic_ips function - basic success cases."""

    def test_audit_all_no_eips_found(self, capsys):
        """Test audit when no Elastic IPs are found."""
        with patch(
            "cost_toolkit.scripts.audit.aws_elastic_ip_audit.load_credentials_from_env",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                "cost_toolkit.scripts.audit.aws_elastic_ip_audit.get_all_regions",
                return_value=["us-east-1"],
            ):
                with patch(
                    "cost_toolkit.scripts.audit.aws_elastic_ip_audit._scan_all_regions",
                    return_value=([], 0, 0, 0),
                ):
                    audit_all_elastic_ips()

        captured = capsys.readouterr()
        assert "AWS Elastic IP Audit" in captured.out
        assert "Scanning all regions for Elastic IP addresses" in captured.out
        assert "No Elastic IPs found in any region" in captured.out
        assert "No Elastic IP costs detected" in captured.out

    def test_audit_all_with_eips_found(self, capsys):
        """Test audit when Elastic IPs are found."""
        regions_with_eips = [
            {
                "region": "us-east-1",
                "total_eips": 3,
                "associated_eips": [{"public_ip": "1.2.3.4", "instance_id": "i-123"}],
                "unassociated_eips": [{"allocation_id": "eipalloc-1", "monthly_cost": 3.65}],
                "total_monthly_cost": 3.65,
            }
        ]

        module_path = "cost_toolkit.scripts.audit.aws_elastic_ip_audit"
        with patch(
            f"{module_path}.load_credentials_from_env",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.get_all_regions",
                return_value=["us-east-1"],
            ):
                with patch(
                    f"{module_path}._scan_all_regions",
                    return_value=(regions_with_eips, 3, 1, 3.65),
                ):
                    with patch(f"{module_path}._print_associated_eips"):
                        with patch(f"{module_path}._print_unassociated_eips"):
                            with patch(f"{module_path}._print_cleanup_recommendations"):
                                audit_all_elastic_ips()

        captured = capsys.readouterr()
        assert "ELASTIC IP AUDIT RESULTS" in captured.out
        assert "Total Elastic IPs found: 3" in captured.out
        assert "Unassociated Elastic IPs: 1" in captured.out
        assert "Monthly cost from unassociated EIPs: $3.65" in captured.out
        assert "Annual cost from unassociated EIPs: $43.80" in captured.out


class TestAuditAllElasticIpsPrintFunctions:
    """Tests for audit_all_elastic_ips function - print function interactions."""

    def test_audit_all_calls_print_functions(self):
        """Test that audit_all_elastic_ips calls all print functions correctly."""
        regions_with_eips = [
            {
                "region": "us-east-1",
                "total_eips": 2,
                "associated_eips": [{"public_ip": "1.2.3.4"}],
                "unassociated_eips": [{"allocation_id": "eipalloc-1"}],
                "total_monthly_cost": 3.65,
            },
            {
                "region": "us-west-2",
                "total_eips": 1,
                "associated_eips": [],
                "unassociated_eips": [{"allocation_id": "eipalloc-2"}],
                "total_monthly_cost": 3.65,
            },
        ]

        module_path = "cost_toolkit.scripts.audit.aws_elastic_ip_audit"
        with patch(
            f"{module_path}.load_credentials_from_env",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.get_all_regions",
                return_value=["us-east-1", "us-west-2"],
            ):
                with patch(
                    f"{module_path}._scan_all_regions",
                    return_value=(regions_with_eips, 3, 2, 7.30),
                ):
                    with patch(f"{module_path}._print_associated_eips") as mock_assoc:
                        with patch(f"{module_path}._print_unassociated_eips") as mock_unassoc:
                            with patch(
                                f"{module_path}._print_cleanup_recommendations"
                            ) as mock_cleanup:
                                audit_all_elastic_ips()

        assert mock_assoc.call_count == 2
        assert mock_unassoc.call_count == 2
        mock_cleanup.assert_called_once_with(regions_with_eips, 7.30)

    def test_audit_all_no_recommendations_when_no_unassociated(self):
        """Test that recommendations are not printed when no unassociated EIPs."""
        regions_with_eips = [
            {
                "region": "us-east-1",
                "total_eips": 2,
                "associated_eips": [
                    {"public_ip": "1.2.3.4"},
                    {"public_ip": "5.6.7.8"},
                ],
                "unassociated_eips": [],
                "total_monthly_cost": 0,
            }
        ]

        module_path = "cost_toolkit.scripts.audit.aws_elastic_ip_audit"
        with patch(
            f"{module_path}.load_credentials_from_env",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.get_all_regions",
                return_value=["us-east-1"],
            ):
                with patch(
                    f"{module_path}._scan_all_regions",
                    return_value=(regions_with_eips, 2, 0, 0),
                ):
                    with patch(f"{module_path}._print_associated_eips"):
                        with patch(f"{module_path}._print_unassociated_eips"):
                            with patch(
                                f"{module_path}._print_cleanup_recommendations"
                            ) as mock_cleanup:
                                audit_all_elastic_ips()

        mock_cleanup.assert_not_called()


class TestAuditAllElasticIpsRegionHandling:
    """Tests for audit_all_elastic_ips function - region handling and output."""

    def test_audit_all_raises_client_error(self):
        """Test that audit_all_elastic_ips raises ClientError when get_all_regions fails."""
        with patch(
            "cost_toolkit.scripts.audit.aws_elastic_ip_audit.load_credentials_from_env",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                "cost_toolkit.scripts.audit.aws_elastic_ip_audit.get_all_regions",
                side_effect=ClientError(
                    {"Error": {"Code": "UnauthorizedOperation"}}, "DescribeRegions"
                ),
            ):
                try:
                    audit_all_elastic_ips()
                    assert False, "Expected ClientError to be raised"
                except ClientError:
                    pass

    def test_audit_all_region_details_printed(self, capsys):
        """Test that region details are printed for each region."""
        regions_with_eips = [
            {
                "region": "us-east-1",
                "total_eips": 1,
                "associated_eips": [],
                "unassociated_eips": [{"allocation_id": "eipalloc-1"}],
                "total_monthly_cost": 3.65,
            },
            {
                "region": "eu-west-1",
                "total_eips": 1,
                "associated_eips": [{"public_ip": "1.2.3.4"}],
                "unassociated_eips": [],
                "total_monthly_cost": 0,
            },
        ]

        module_path = "cost_toolkit.scripts.audit.aws_elastic_ip_audit"
        with patch(
            f"{module_path}.load_credentials_from_env",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.get_all_regions",
                return_value=["us-east-1", "eu-west-1"],
            ):
                with patch(
                    f"{module_path}._scan_all_regions",
                    return_value=(regions_with_eips, 2, 1, 3.65),
                ):
                    with patch(f"{module_path}._print_associated_eips"):
                        with patch(f"{module_path}._print_unassociated_eips"):
                            with patch(f"{module_path}._print_cleanup_recommendations"):
                                audit_all_elastic_ips()

        captured = capsys.readouterr()
        assert "Region: us-east-1" in captured.out
        assert "Region: eu-west-1" in captured.out


class TestMain:
    """Tests for main function."""

    def test_main_success(self):
        """Test successful main execution."""
        with patch(
            "cost_toolkit.scripts.audit.aws_elastic_ip_audit.audit_all_elastic_ips"
        ) as mock_audit:
            main()

        mock_audit.assert_called_once()

    def test_main_with_client_error(self, capsys):
        """Test main function with ClientError."""
        with patch(
            "cost_toolkit.scripts.audit.aws_elastic_ip_audit.audit_all_elastic_ips",
            side_effect=ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
                "operation",
            ),
        ):
            try:
                main()
            except SystemExit as e:
                assert e.code == 1

        captured = capsys.readouterr()
        assert "Script failed:" in captured.out

    def test_main_reraises_non_client_errors(self):
        """Test that main reraises non-ClientError exceptions."""
        with patch(
            "cost_toolkit.scripts.audit.aws_elastic_ip_audit.audit_all_elastic_ips",
            side_effect=ValueError("Some error"),
        ):
            try:
                main()
                assert False, "Expected ValueError to be raised"
            except ValueError as e:
                assert str(e) == "Some error"
