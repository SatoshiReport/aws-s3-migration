"""Comprehensive tests for aws_network_interface_audit.py - Part 4: Main Function Tests."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_network_interface_audit import main
from tests.network_interface_test_utils import build_attached_interfaces


def _run_main_with_region_data(region_data, regions=None):
    """Execute main with patched dependencies returning provided region data."""
    module_path = "cost_toolkit.scripts.audit.aws_network_interface_audit"
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                f"{module_path}.setup_aws_credentials",
                return_value=("test-key", "test-secret"),
            )
        )
        stack.enter_context(patch(f"{module_path}.get_all_regions", return_value=regions or ["us-east-1"]))
        stack.enter_context(
            patch(
                f"{module_path}.audit_network_interfaces_in_region",
                return_value=region_data,
            )
        )
        main()


class TestMainNoInterfaces:  # pylint: disable=too-few-public-methods
    """Tests for main function with no interfaces found."""

    def _assert_main_scanning_output(self, captured_output, num_regions, region_name):
        """Helper to assert scanning progress output from main."""
        assert "AWS Network Interface Audit" in captured_output
        assert f"Scanning {num_regions} AWS regions" in captured_output
        assert f"Checking region: {region_name}" in captured_output
        assert "No network interfaces found" in captured_output

    def _assert_main_summary_output(self, captured_output, expected_counts):
        """Helper to assert summary statistics output from main."""
        assert "NETWORK INTERFACE AUDIT SUMMARY" in captured_output
        assert f"Regions scanned: {expected_counts['regions']}" in captured_output
        assert f"Total network interfaces: {expected_counts['total']}" in captured_output
        assert f"Unused interfaces: {expected_counts['unused']}" in captured_output

    def test_main_no_interfaces_found(self, capsys):
        """Test main when no network interfaces are found."""
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_audit"
        with patch(
            f"{module_path}.setup_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.get_all_regions",
                return_value=["us-east-1"],
            ):
                with patch(
                    f"{module_path}.audit_network_interfaces_in_region",
                    return_value=None,
                ):
                    main()

        captured = capsys.readouterr()
        expected_counts = {"regions": 1, "total": 0, "unused": 0}
        self._assert_main_scanning_output(captured.out, 1, "us-east-1")
        self._assert_main_summary_output(captured.out, expected_counts)
        assert "No unused network interfaces found!" in captured.out


class TestMainWithUnusedInterfaces:  # pylint: disable=too-few-public-methods
    """Tests for main function with unused interfaces."""

    def test_main_with_unused_interfaces(self, capsys):
        """Test main when unused network interfaces are found."""
        region_data = {
            "region": "us-east-1",
            "total_interfaces": 3,
            "unused_interfaces": [
                {
                    "interface_id": "eni-unused1",
                    "name": "test-unused",
                    "type": "interface",
                    "vpc_id": "vpc-123",
                    "subnet_id": "subnet-123",
                    "private_ip": "10.0.1.1",
                    "description": "Unused interface",
                    "status": "available",
                }
            ],
            "attached_interfaces": [
                {
                    "interface_id": "eni-attached1",
                    "name": "test-attached",
                    "type": "interface",
                    "attached_to": "i-123",
                    "status": "in-use",
                    "vpc_id": "vpc-123",
                    "private_ip": "10.0.1.5",
                    "public_ip": "1.2.3.4",
                },
                {
                    "interface_id": "eni-attached2",
                    "name": "test-attached-2",
                    "type": "interface",
                    "attached_to": "i-456",
                    "status": "in-use",
                    "vpc_id": "vpc-123",
                    "private_ip": "10.0.1.6",
                    "public_ip": "None",
                },
            ],
            "interface_details": [],
        }

        _run_main_with_region_data(region_data)

        captured = capsys.readouterr()
        assert "Total network interfaces: 3" in captured.out
        assert "Unused interfaces: 1" in captured.out
        assert "Attached interfaces: 2" in captured.out
        assert "Found 3 network interfaces" in captured.out
        assert "Unused: 1" in captured.out
        assert "Attached: 2" in captured.out
        assert "UNUSED NETWORK INTERFACES FOUND" in captured.out
        assert "ATTACHED NETWORK INTERFACES DETAILS" in captured.out


class TestMainOnlyAttached:  # pylint: disable=too-few-public-methods
    """Tests for main function with only attached interfaces."""

    def test_main_only_attached_interfaces(self, capsys):
        """Test main when only attached interfaces exist."""
        region_data = {
            "region": "us-west-2",
            "total_interfaces": 2,
            "unused_interfaces": [],
            "attached_interfaces": build_attached_interfaces(overrides={1: {"attached_to": "i-2", "public_ip": "None"}}),
            "interface_details": [],
        }

        _run_main_with_region_data(region_data, regions=["us-west-2"])

        captured = capsys.readouterr()
        assert "No unused network interfaces found!" in captured.out
        assert "Your AWS account has clean network interface configuration" in captured.out
        assert "ATTACHED NETWORK INTERFACES DETAILS" in captured.out


class TestMainMultipleRegions:  # pylint: disable=too-few-public-methods
    """Tests for main function with multiple regions."""

    def test_main_multiple_regions(self, capsys):
        """Test main with multiple regions."""
        region_data_1 = {
            "region": "us-east-1",
            "total_interfaces": 2,
            "unused_interfaces": [],
            "attached_interfaces": [
                {
                    "interface_id": "eni-1",
                    "name": "eni-1",
                    "type": "interface",
                    "attached_to": "i-1",
                    "status": "in-use",
                    "vpc_id": "vpc-1",
                    "private_ip": "10.0.0.1",
                    "public_ip": "None",
                }
            ],
            "interface_details": [],
        }
        region_data_2 = {
            "region": "eu-west-1",
            "total_interfaces": 1,
            "unused_interfaces": [
                {
                    "interface_id": "eni-unused",
                    "name": "unused",
                    "type": "interface",
                    "vpc_id": "vpc-2",
                    "subnet_id": "subnet-2",
                    "private_ip": "10.1.0.1",
                    "description": "test",
                    "status": "available",
                }
            ],
            "attached_interfaces": [],
            "interface_details": [],
        }

        module_path = "cost_toolkit.scripts.audit.aws_network_interface_audit"
        with patch(
            f"{module_path}.setup_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.get_all_regions",
                return_value=["us-east-1", "eu-west-1"],
            ):
                with patch(
                    f"{module_path}.audit_network_interfaces_in_region",
                    side_effect=[region_data_1, region_data_2],
                ):
                    main()

        captured = capsys.readouterr()
        assert "Scanning 2 AWS regions" in captured.out
        assert "Checking region: us-east-1" in captured.out
        assert "Checking region: eu-west-1" in captured.out
        assert "Total network interfaces: 3" in captured.out
        assert "Unused interfaces: 1" in captured.out


class TestMainMixedRegions:  # pylint: disable=too-few-public-methods
    """Tests for main function with mixed region scenarios."""

    def test_main_mixed_regions_some_empty(self, capsys):
        """Test main with some regions having interfaces and some empty."""
        region_data_with_enis = {
            "region": "us-east-1",
            "total_interfaces": 1,
            "unused_interfaces": [],
            "attached_interfaces": [
                {
                    "interface_id": "eni-1",
                    "name": "test",
                    "type": "interface",
                    "attached_to": "i-1",
                    "status": "in-use",
                    "vpc_id": "vpc-1",
                    "private_ip": "10.0.0.1",
                    "public_ip": "None",
                }
            ],
            "interface_details": [],
        }

        module_path = "cost_toolkit.scripts.audit.aws_network_interface_audit"
        with patch(
            f"{module_path}.setup_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.get_all_regions",
                return_value=["us-east-1", "us-west-2", "eu-west-1"],
            ):
                with patch(
                    f"{module_path}.audit_network_interfaces_in_region",
                    side_effect=[region_data_with_enis, None, None],
                ):
                    main()

        captured = capsys.readouterr()
        assert "Regions scanned: 3" in captured.out
        assert "Total network interfaces: 1" in captured.out
        assert captured.out.count("No network interfaces found") == 2


class TestMainSummaryCalculations:  # pylint: disable=too-few-public-methods
    """Tests for main function summary calculations."""

    def test_main_summary_calculations(self, capsys):
        """Test that main correctly calculates summary statistics."""
        unused_eni = {
            "interface_id": "eni-1",
            "name": "unused-1",
            "type": "interface",
            "vpc_id": "vpc-1",
            "subnet_id": "subnet-1",
            "private_ip": "10.0.0.1",
            "description": "test",
            "status": "available",
        }
        attached_eni = {
            "interface_id": "eni-attached-1",
            "name": "attached-1",
            "type": "interface",
            "attached_to": "i-1",
            "status": "in-use",
            "vpc_id": "vpc-1",
            "private_ip": "10.0.0.10",
            "public_ip": "None",
        }
        region_data_1 = {
            "region": "us-east-1",
            "total_interfaces": 5,
            "unused_interfaces": [unused_eni, {**unused_eni, "interface_id": "eni-2"}],
            "attached_interfaces": [{**attached_eni, "interface_id": f"eni-attached-{i}"} for i in range(3)],
            "interface_details": [],
        }
        region_data_2 = {
            "region": "us-west-2",
            "total_interfaces": 3,
            "unused_interfaces": [{**unused_eni, "interface_id": "eni-3", "vpc_id": "vpc-2"}],
            "attached_interfaces": [
                {**attached_eni, "interface_id": "eni-attached-4", "vpc_id": "vpc-2"},
                {**attached_eni, "interface_id": "eni-attached-5", "vpc_id": "vpc-2"},
            ],
            "interface_details": [],
        }
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_audit"
        with patch(
            f"{module_path}.setup_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.get_all_regions",
                return_value=["us-east-1", "us-west-2"],
            ):
                with patch(
                    f"{module_path}.audit_network_interfaces_in_region",
                    side_effect=[region_data_1, region_data_2],
                ):
                    main()
        captured = capsys.readouterr()
        assert "Total network interfaces: 8" in captured.out
        assert "Unused interfaces: 3" in captured.out
        assert "Attached interfaces: 5" in captured.out


class TestMainErrorHandling:  # pylint: disable=too-few-public-methods
    """Tests for main function error handling."""

    def test_main_client_error(self, capsys):
        """Test main function with ClientError."""
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_audit"
        with patch(
            f"{module_path}.setup_aws_credentials",
            side_effect=ClientError(
                {"Error": {"Code": "InvalidClientTokenId", "Message": "Invalid token"}},
                "GetCredentials",
            ),
        ):
            try:
                main()
                assert False, "Expected ClientError to be raised"
            except ClientError as e:
                assert e.response["Error"]["Code"] == "InvalidClientTokenId"

        captured = capsys.readouterr()
        assert "Critical error during network interface audit" in captured.out
