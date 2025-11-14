"""Comprehensive tests for aws_vpc_flow_logs_audit.py - Part 2."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_vpc_flow_logs_audit import (
    _print_cost_analysis,
    _print_flow_logs_summary,
    audit_additional_vpc_costs_in_region,
    main,
)


class TestAuditAdditionalVpcCosts:
    """Tests for audit_additional_vpc_costs_in_region function."""

    def test_audit_additional_vpc_costs_success(self, capsys):
        """Test successful additional VPC costs audit."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_vpc_peering_connections.return_value = {"VpcPeeringConnections": []}
            mock_ec2.describe_vpc_endpoints.return_value = {"VpcEndpoints": []}
            mock_ec2.describe_security_groups.return_value = {"SecurityGroups": []}
            mock_ec2.describe_network_acls.return_value = {"NetworkAcls": []}
            mock_ec2.describe_route_tables.return_value = {"RouteTables": []}
            mock_ec2.describe_subnets.return_value = {"Subnets": []}

            audit_additional_vpc_costs_in_region("us-east-1")

        captured = capsys.readouterr()
        assert "Checking additional VPC cost sources" in captured.out

    def test_audit_additional_vpc_costs_client_error(self, capsys):
        """Test error handling during additional VPC costs audit."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_vpc_peering_connections.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "describe_vpc_peering_connections"
            )

            audit_additional_vpc_costs_in_region("us-east-1")

        captured = capsys.readouterr()
        assert "Error checking additional VPC costs" in captured.out


class TestPrintFlowLogsSummary:
    """Tests for _print_flow_logs_summary function."""

    def test_print_flow_logs_summary_with_logs(self, capsys):
        """Test printing summary with flow logs."""
        flow_logs = [
            {
                "flow_log_id": "fl-123",
                "flow_log_status": "ACTIVE",
                "log_destination": "s3://bucket",
                "storage_cost": 0.50,
            },
            {
                "flow_log_id": "fl-456",
                "flow_log_status": "INACTIVE",
                "log_destination": "s3://bucket2",
            },
        ]

        _print_flow_logs_summary(flow_logs, 0.50)

        captured = capsys.readouterr()
        assert "Total VPC Flow Logs found: 2" in captured.out
        assert "Active Flow Logs: 1" in captured.out
        assert "Inactive Flow Logs: 1" in captured.out
        assert "fl-123 -> s3://bucket" in captured.out
        assert "Storage cost: $0.50/month" in captured.out

    def test_print_flow_logs_summary_no_logs(self, capsys):
        """Test printing summary with no flow logs."""
        _print_flow_logs_summary([], 0)

        captured = capsys.readouterr()
        assert "Total VPC Flow Logs found: 0" in captured.out

    def test_print_flow_logs_summary_all_active(self, capsys):
        """Test printing summary with all active logs."""
        flow_logs = [
            {
                "flow_log_id": "fl-123",
                "flow_log_status": "ACTIVE",
                "log_destination": "s3://bucket",
            }
        ]

        _print_flow_logs_summary(flow_logs, 0)

        captured = capsys.readouterr()
        assert "Active Flow Logs: 1" in captured.out
        assert "Inactive Flow Logs: 0" in captured.out


class TestPrintCostAnalysis:
    """Tests for _print_cost_analysis function."""

    def test_print_cost_analysis_no_mystery(self, capsys):
        """Test cost analysis with no unaccounted costs."""
        _print_cost_analysis(6.00)

        captured = capsys.readouterr()
        assert "Known Public IPv4 cost: $3.60/month" in captured.out
        assert "Flow Logs storage cost: $6.00/month" in captured.out
        assert "Total identified: $9.60/month" in captured.out
        assert "Unaccounted for: $0.00/month" in captured.out

    def test_print_cost_analysis_with_mystery(self, capsys):
        """Test cost analysis with unaccounted costs."""
        _print_cost_analysis(1.00)

        captured = capsys.readouterr()
        assert "REMAINING MYSTERY COSTS:" in captured.out
        assert "Possible sources for the remaining $5.00:" in captured.out
        assert "Data transfer charges" in captured.out
        assert "VPC DNS queries" in captured.out

    def test_print_cost_analysis_small_mystery(self, capsys):
        """Test cost analysis with small unaccounted amount."""
        _print_cost_analysis(5.00)

        captured = capsys.readouterr()
        assert "REMAINING MYSTERY COSTS:" not in captured.out


def test_main_integration():
    """Test main function integration."""
    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_logs = MagicMock()

        def client_side_effect(service, *_args, **_kwargs):
            if service == "ec2":
                return mock_ec2
            if service == "logs":
                return mock_logs
            return MagicMock()

        mock_client.side_effect = client_side_effect

        mock_ec2.describe_flow_logs.return_value = {"FlowLogs": []}
        mock_ec2.describe_vpc_peering_connections.return_value = {"VpcPeeringConnections": []}
        mock_ec2.describe_vpc_endpoints.return_value = {"VpcEndpoints": []}
        mock_ec2.describe_security_groups.return_value = {"SecurityGroups": []}
        mock_ec2.describe_network_acls.return_value = {"NetworkAcls": []}
        mock_ec2.describe_route_tables.return_value = {"RouteTables": []}
        mock_ec2.describe_subnets.return_value = {"Subnets": []}

        main()
