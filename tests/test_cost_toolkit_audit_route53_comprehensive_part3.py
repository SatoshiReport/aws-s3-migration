"""Comprehensive tests for aws_route53_audit.py - Part 3."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_route53_audit import (
    DEFAULT_DNS_RECORD_COUNT,
    _print_cost_breakdown,
    _print_optimization_opportunities,
    audit_route53_resolver_endpoints,
)


class TestAuditRoute53ResolverEndpoints:
    """Tests for audit_route53_resolver_endpoints function."""

    def _assert_endpoint_fields(self, endpoint, *, endpoint_id, name, direction, status):
        """Helper to assert endpoint fields."""
        assert endpoint["id"] == endpoint_id
        assert endpoint["name"] == name
        assert endpoint["direction"] == direction
        assert endpoint["status"] == status

    def _assert_endpoints_output(self, capsys):
        """Helper to assert endpoints output messages."""
        captured = capsys.readouterr()
        assert "Auditing Route 53 Resolver Endpoints" in captured.out
        assert "Resolver Endpoint: inbound-endpoint" in captured.out
        assert "Direction: INBOUND" in captured.out
        assert "Status: OPERATIONAL" in captured.out
        assert "Monthly Cost: $90.00" in captured.out
        assert "Total endpoints: 2" in captured.out
        assert "Estimated monthly cost: $180.00" in captured.out

    def test_audit_resolver_endpoints_with_endpoints(self, capsys):
        """Test auditing resolver endpoints with endpoints present."""
        with patch(
            "cost_toolkit.scripts.audit.aws_route53_audit.create_route53resolver_client"
        ) as mock_client:
            mock_resolver = MagicMock()
            mock_resolver.list_resolver_endpoints.return_value = {
                "ResolverEndpoints": [
                    {
                        "Id": "rslvr-in-123",
                        "Name": "inbound-endpoint",
                        "Direction": "INBOUND",
                        "Status": "OPERATIONAL",
                    },
                    {
                        "Id": "rslvr-out-456",
                        "Name": "outbound-endpoint",
                        "Direction": "OUTBOUND",
                        "Status": "OPERATIONAL",
                    },
                ]
            }
            mock_client.return_value = mock_resolver

            endpoints = audit_route53_resolver_endpoints()

        assert len(endpoints) == 2
        self._assert_endpoint_fields(
            endpoints[0],
            endpoint_id="rslvr-in-123",
            name="inbound-endpoint",
            direction="INBOUND",
            status="OPERATIONAL",
        )
        assert endpoints[0]["monthly_cost"] == 90.0
        self._assert_endpoints_output(capsys)

    def test_audit_resolver_endpoints_no_endpoints(self, capsys):
        """Test auditing when no resolver endpoints exist."""
        with patch(
            "cost_toolkit.scripts.audit.aws_route53_audit.create_route53resolver_client"
        ) as mock_client:
            mock_resolver = MagicMock()
            mock_resolver.list_resolver_endpoints.return_value = {"ResolverEndpoints": []}
            mock_client.return_value = mock_resolver

            endpoints = audit_route53_resolver_endpoints()

        assert len(endpoints) == 0
        captured = capsys.readouterr()
        assert "No resolver endpoints found" in captured.out

    def test_audit_resolver_endpoints_client_error(self, capsys):
        """Test error handling when auditing resolver endpoints fails."""
        with patch(
            "cost_toolkit.scripts.audit.aws_route53_audit.create_route53resolver_client"
        ) as mock_client:
            mock_resolver = MagicMock()
            mock_resolver.list_resolver_endpoints.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied"}}, "list_resolver_endpoints"
            )
            mock_client.return_value = mock_resolver

            endpoints = audit_route53_resolver_endpoints()

        assert len(endpoints) == 0
        captured = capsys.readouterr()
        assert "Error auditing resolver endpoints" in captured.out


class TestPrintCostBreakdown:
    """Tests for _print_cost_breakdown function."""

    def test_print_cost_breakdown_matching(self, capsys):
        """Test cost breakdown when estimated matches reported."""
        hosted_zones = [
            {"zone_name": "example.com", "monthly_cost": 0.50},
            {"zone_name": "test.com", "monthly_cost": 0.50},
            {"zone_name": "demo.com", "monthly_cost": 0.50},
        ]
        health_checks = []
        resolver_endpoints = []

        _print_cost_breakdown(
            hosted_zones,
            health_checks,
            resolver_endpoints,
            total_hosted_zone_cost=1.50,
            total_health_check_cost=0.0,
            total_resolver_cost=0.0,
            total_estimated_cost=1.50,
        )

        captured = capsys.readouterr()
        assert "ROUTE 53 COST BREAKDOWN" in captured.out
        assert "Hosted Zones: $1.50/month (3 zones)" in captured.out
        assert "Health Checks: $0.00/month (0 checks)" in captured.out
        assert "Resolver Endpoints: $0.00/month (0 endpoints)" in captured.out
        assert "Total Estimated: $1.50/month" in captured.out
        assert "Your Reported Cost: $1.57" in captured.out
        assert "Estimated cost closely matches reported cost" in captured.out

    def test_print_cost_breakdown_not_matching(self, capsys):
        """Test cost breakdown when estimated differs from reported."""
        hosted_zones = [{"zone_name": "example.com", "monthly_cost": 0.50}]
        health_checks = []
        resolver_endpoints = [
            {"id": "rslvr-123", "monthly_cost": 90.0},
        ]

        _print_cost_breakdown(
            hosted_zones,
            health_checks,
            resolver_endpoints,
            total_hosted_zone_cost=0.50,
            total_health_check_cost=0.0,
            total_resolver_cost=90.0,
            total_estimated_cost=90.50,
        )

        captured = capsys.readouterr()
        assert "Total Estimated: $90.50/month" in captured.out
        assert "Estimated cost differs from reported cost" in captured.out


class TestPrintOptimizationOpportunities:
    """Tests for _print_optimization_opportunities function."""

    def test_print_optimization_unused_zones(self, capsys):
        """Test optimization opportunities with unused zones."""
        hosted_zones = [
            {
                "zone_name": "example.com",
                "record_count": DEFAULT_DNS_RECORD_COUNT,
                "monthly_cost": 0.50,
            },
            {"zone_name": "active.com", "record_count": 10, "monthly_cost": 0.50},
        ]
        health_checks = []
        resolver_endpoints = []

        _print_optimization_opportunities(hosted_zones, health_checks, resolver_endpoints)

        captured = capsys.readouterr()
        assert "OPTIMIZATION OPPORTUNITIES" in captured.out
        assert "example.com - appears unused (only default records)" in captured.out
        assert "active.com - has 10 records (likely in use)" in captured.out

    def test_print_optimization_with_health_checks(self, capsys):
        """Test optimization opportunities with health checks."""
        hosted_zones = []
        health_checks = [
            {"id": "hc-1", "monthly_cost": 0.50},
            {"id": "hc-2", "monthly_cost": 0.50},
        ]
        resolver_endpoints = []

        _print_optimization_opportunities(hosted_zones, health_checks, resolver_endpoints)

        captured = capsys.readouterr()
        assert "Health Checks (2 checks)" in captured.out
        assert "Review if all health checks are necessary" in captured.out
        assert "Each health check costs $0.50/month" in captured.out

    def test_print_optimization_with_resolver_endpoints(self, capsys):
        """Test optimization opportunities with resolver endpoints."""
        hosted_zones = []
        health_checks = []
        resolver_endpoints = [{"id": "rslvr-123", "monthly_cost": 90.0}]

        _print_optimization_opportunities(hosted_zones, health_checks, resolver_endpoints)

        captured = capsys.readouterr()
        assert "Resolver Endpoints (1 endpoints)" in captured.out
        assert "Very expensive! Each endpoint costs ~$90/month" in captured.out
        assert "Review if resolver endpoints are actually needed" in captured.out
