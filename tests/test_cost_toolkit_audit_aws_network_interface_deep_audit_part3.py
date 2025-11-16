"""Comprehensive tests for aws_network_interface_deep_audit.py - Part 3."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_network_interface_deep_audit import (
    investigate_network_interface,
    main,
)


class TestInvestigateNetworkInterfaceTerminatedAndStopped:  # gitleaks:allow
    """Tests for investigate_network_interface with terminated/stopped instances."""

    def test_investigate_interface_with_terminated_instance(self, capsys):
        """Test investigating interface attached to terminated instance."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_network_interfaces.return_value = {
            "NetworkInterfaces": [
                {
                    "Status": "available",
                    "InterfaceType": "interface",
                    "Description": "Orphaned interface",
                    "VpcId": "vpc-123",
                    "SubnetId": "subnet-456",
                    "Attachment": {
                        "InstanceId": "i-terminated",
                        "Status": "detached",
                        "AttachTime": "2024-01-01T00:00:00Z",
                    },
                }
            ]
        }
        mock_ec2.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "State": {"Name": "terminated"},
                            "InstanceType": "t2.micro",
                        }
                    ]
                }
            ]
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_network_interface_deep_audit.boto3.client"
        ) as mock_client:
            mock_client.return_value = mock_ec2
            result = investigate_network_interface(
                "us-east-1",
                "eni-orphaned",
                "test-key",
                "test-secret",
            )

        assert result == "orphaned"
        captured = capsys.readouterr()
        assert "Deep Analysis: eni-orphaned" in captured.out

    def test_investigate_interface_stopped_instance(
        self, capsys
    ):  # pylint: disable=unused-argument
        """Test investigating interface attached to stopped instance."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_network_interfaces.return_value = {
            "NetworkInterfaces": [
                {
                    "Status": "in-use",
                    "InterfaceType": "interface",
                    "Description": "Stopped instance interface",
                    "VpcId": "vpc-123",
                    "SubnetId": "subnet-456",
                    "Attachment": {
                        "InstanceId": "i-stopped",
                        "Status": "attached",
                        "AttachTime": "2024-01-01T00:00:00Z",
                    },
                }
            ]
        }
        mock_ec2.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "State": {"Name": "stopped"},
                            "InstanceType": "t2.medium",
                        }
                    ]
                }
            ]
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_network_interface_deep_audit.boto3.client"
        ) as mock_client:
            mock_client.return_value = mock_ec2
            result = investigate_network_interface(
                "us-west-2",
                "eni-stopped",
                "test-key",
                "test-secret",
            )

        assert result == "attached_stopped"


class TestInvestigateNetworkInterfaceNatGateway:  # pylint: disable=too-few-public-methods
    """Tests for investigate_network_interface with NAT gateway."""

    def test_investigate_interface_nat_gateway(self, capsys):
        """Test investigating NAT gateway interface."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_network_interfaces.return_value = {
            "NetworkInterfaces": [
                {
                    "Status": "in-use",
                    "InterfaceType": "nat_gateway",
                    "Description": "NAT Gateway interface",
                    "VpcId": "vpc-123",
                    "SubnetId": "subnet-456",
                }
            ]
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_network_interface_deep_audit.boto3.client"
        ) as mock_client:
            mock_client.return_value = mock_ec2
            result = investigate_network_interface(
                "eu-west-1",
                "eni-nat",
                "test-key",
                "test-secret",
            )

        assert result == "aws_service"
        captured = capsys.readouterr()
        assert "Special interface type: nat_gateway" in captured.out


class TestInvestigateNetworkInterfaceErrors:  # pylint: disable=too-few-public-methods
    """Tests for investigate_network_interface error handling."""

    def test_investigate_interface_client_error(self, capsys):
        """Test investigating interface with ClientError."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_network_interfaces.side_effect = ClientError(
            {"Error": {"Code": "InvalidNetworkInterfaceID.NotFound", "Message": "Not found"}},
            "DescribeNetworkInterfaces",
        )

        with patch(
            "cost_toolkit.scripts.audit.aws_network_interface_deep_audit.boto3.client"
        ) as mock_client:
            mock_client.return_value = mock_ec2
            result = investigate_network_interface(
                "us-east-1",
                "eni-notfound",
                "test-key",
                "test-secret",
            )

        assert result == "error"
        captured = capsys.readouterr()
        assert "Error investigating eni-notfound:" in captured.out


class TestMainSuccess:
    """Tests for main function success scenarios - basic cases."""

    def test_main_success_with_cleanup_candidates(self, capsys):
        """Test successful main execution with cleanup candidates."""
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_deep_audit"
        with patch(
            f"{module_path}.load_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.investigate_network_interface",
                side_effect=[
                    "orphaned",
                    "detached",
                    "active",
                    "attached_stopped",
                    "orphaned",
                ],
            ) as mock_investigate:
                main()

        captured = capsys.readouterr()
        assert "AWS Network Interface Deep Audit" in captured.out
        assert "Investigating 5 network interfaces" in captured.out
        assert "DEEP AUDIT SUMMARY" in captured.out
        assert "Network interfaces that can be deleted:" in captured.out
        assert "CLEANUP RECOMMENDATIONS:" in captured.out
        assert "These network interfaces appear to be orphaned or unused" in captured.out
        assert "Deleting them will improve account hygiene" in captured.out

        assert mock_investigate.call_count == 5

    def test_main_success_all_active(self, capsys):
        """Test successful main execution with all active interfaces."""
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_deep_audit"
        with patch(
            f"{module_path}.load_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.investigate_network_interface",
                side_effect=[
                    "active",
                    "active",
                    "attached_stopped",
                    "active",
                    "active",
                ],
            ):
                main()

        captured = capsys.readouterr()
        assert "No orphaned network interfaces found!" in captured.out
        assert "All network interfaces are properly attached and in use." in captured.out

    def test_main_success_mixed_results(self, capsys):
        """Test main execution with mixed results."""
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_deep_audit"
        with patch(
            f"{module_path}.load_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.investigate_network_interface",
                side_effect=[
                    "orphaned",
                    "active",
                    "detached",
                    "attached_stopped",
                    "error",
                ],
            ):
                main()

        captured = capsys.readouterr()
        assert "Network interfaces that can be deleted: 2" in captured.out
        assert "Active/legitimate network interfaces: 2" in captured.out


class TestMainSuccessExtended:
    """Tests for main function success scenarios - extended cases."""

    def test_main_only_cleanup_candidates(self, capsys):
        """Test main when only cleanup candidates exist."""
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_deep_audit"
        with patch(
            f"{module_path}.load_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.investigate_network_interface",
                side_effect=[
                    "orphaned",
                    "detached",
                    "orphaned",
                    "detached",
                    "orphaned",
                ],
            ):
                main()

        captured = capsys.readouterr()
        assert "Network interfaces that can be deleted: 5" in captured.out
        assert "Active/legitimate network interfaces:" not in captured.out

    def test_main_error_results_not_categorized(self, capsys):
        """Test that error results are not categorized as cleanup or active."""
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_deep_audit"
        with patch(
            f"{module_path}.load_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.investigate_network_interface",
                side_effect=["error", "error", "error", "error", "error"],
            ):
                main()

        captured = capsys.readouterr()
        assert "No orphaned network interfaces found!" in captured.out


class TestMainDetailsAndErrors:
    """Tests for main function output details."""

    def test_main_investigates_correct_regions(self):
        """Test that main investigates all specified regions and interfaces."""
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_deep_audit"
        with patch(
            f"{module_path}.load_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.investigate_network_interface",
                return_value="active",
            ) as mock_investigate:
                main()

        expected_calls = [
            ("us-east-1", "eni-0a369310199dd8b96", "test-key", "test-secret"),
            ("us-east-1", "eni-01c2a771086939fe3", "test-key", "test-secret"),
            ("eu-west-2", "eni-04933185523bf68c7", "test-key", "test-secret"),
            ("eu-west-2", "eni-01f92363be8241c0d", "test-key", "test-secret"),
            ("us-east-2", "eni-070796a225e04cb80", "test-key", "test-secret"),
        ]

        assert mock_investigate.call_count == 5
        actual_calls = [call[0] for call in mock_investigate.call_args_list]
        for expected_args in expected_calls:
            assert expected_args in actual_calls

    def test_main_prints_cleanup_candidates_details(self, capsys):
        """Test that main prints detailed cleanup candidate information."""
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_deep_audit"
        with patch(
            f"{module_path}.load_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.investigate_network_interface",
                side_effect=["orphaned", "detached", "active", "active", "active"],
            ):
                main()

        captured = capsys.readouterr()
        assert "eni-0a369310199dd8b96 (us-east-1) - orphaned" in captured.out
        assert "eni-01c2a771086939fe3 (us-east-1) - detached" in captured.out

    def test_main_prints_active_interfaces_details(self, capsys):
        """Test that main prints detailed active interface information."""
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_deep_audit"
        with patch(
            f"{module_path}.load_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.investigate_network_interface",
                side_effect=[
                    "active",
                    "attached_stopped",
                    "orphaned",
                    "active",
                    "active",
                ],
            ):
                main()

        captured = capsys.readouterr()
        assert "Active/legitimate network interfaces:" in captured.out
        assert "eni-0a369310199dd8b96 (us-east-1) - active" in captured.out
        assert "eni-01c2a771086939fe3 (us-east-1) - attached_stopped" in captured.out


class TestMainErrorHandling:
    """Tests for main function error handling."""

    def test_main_credential_error(self):
        """Test main execution with credential error."""
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_deep_audit"
        with patch(
            f"{module_path}.load_aws_credentials",
            side_effect=ValueError("AWS credentials not found"),
        ):
            with pytest.raises(ValueError, match="AWS credentials not found"):
                main()

    def test_main_client_error_during_investigation(self):
        """Test main execution with ClientError during investigation."""
        module_path = "cost_toolkit.scripts.audit.aws_network_interface_deep_audit"
        with patch(
            f"{module_path}.load_aws_credentials",
            return_value=("test-key", "test-secret"),
        ):
            with patch(
                f"{module_path}.investigate_network_interface",
                side_effect=ClientError(
                    {
                        "Error": {
                            "Code": "UnauthorizedOperation",
                            "Message": "Not authorized",
                        }
                    },
                    "DescribeNetworkInterfaces",
                ),
            ):
                with pytest.raises(ClientError):
                    main()
