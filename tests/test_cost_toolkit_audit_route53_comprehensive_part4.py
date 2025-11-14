"""Comprehensive tests for aws_route53_audit.py - Part 4."""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.scripts.audit.aws_route53_audit import (
    COST_VARIANCE_THRESHOLD,
    DEFAULT_DNS_RECORD_COUNT,
    EXPECTED_HEALTH_CHECK_COUNT,
    EXPECTED_HOSTED_ZONE_COUNT_1,
    EXPECTED_HOSTED_ZONE_COUNT_2,
    _print_cost_explanation,
    main,
)


class TestPrintCostExplanation:
    """Tests for _print_cost_explanation function."""

    def test_print_explanation_three_zones(self, capsys):
        """Test cost explanation with 3 hosted zones."""
        hosted_zones = [
            {"zone_name": "zone1.com"},
            {"zone_name": "zone2.com"},
            {"zone_name": "zone3.com"},
        ]
        health_checks = []

        _print_cost_explanation(hosted_zones, health_checks)

        captured = capsys.readouterr()
        assert "LIKELY EXPLANATION FOR $1.57" in captured.out
        assert "3 hosted zones" in captured.out
        assert "$1.50/month" in captured.out
        assert "Plus DNS queries and other small charges" in captured.out

    def test_print_explanation_two_zones_two_health_checks(self, capsys):
        """Test cost explanation with 2 zones and 2 health checks."""
        hosted_zones = [{"zone_name": "zone1.com"}, {"zone_name": "zone2.com"}]
        health_checks = [{"id": "hc-1"}, {"id": "hc-2"}]

        _print_cost_explanation(hosted_zones, health_checks)

        captured = capsys.readouterr()
        assert "2 hosted zones" in captured.out
        assert "2 health checks" in captured.out
        assert "$2.00/month" in captured.out
        assert "Partial month billing could explain $1.57" in captured.out

    def test_print_explanation_other_configuration(self, capsys):
        """Test cost explanation with other configuration."""
        hosted_zones = [{"zone_name": "zone1.com"}]
        health_checks = []

        _print_cost_explanation(hosted_zones, health_checks)

        captured = capsys.readouterr()
        assert "Route 53 charges include" in captured.out
        assert "Hosted zones: $0.50/month each" in captured.out
        assert "DNS queries: $0.40 per million queries" in captured.out
        assert "Health checks: $0.50/month each" in captured.out


def test_main_function_main_execution(capsys):
    """Test main function execution."""
    with patch(
        "cost_toolkit.scripts.audit.aws_route53_audit.audit_route53_hosted_zones"
    ) as mock_zones:
        with patch(
            "cost_toolkit.scripts.audit.aws_route53_audit.audit_route53_health_checks"
        ) as mock_health:
            with patch(
                "cost_toolkit.scripts.audit.aws_route53_audit.audit_route53_resolver_endpoints"
            ) as mock_resolver:
                mock_zones.return_value = [
                    {
                        "zone_name": "example.com",
                        "monthly_cost": 0.50,
                        "record_count": 5,
                        "zone_id": "Z123",
                        "is_private": False,
                    }
                ]
                mock_health.return_value = [{"id": "hc-123", "monthly_cost": 0.50, "type": "HTTPS"}]
                mock_resolver.return_value = []

                main()

    captured = capsys.readouterr()
    assert "AWS Route 53 Cost Audit" in captured.out
    assert "ROUTE 53 COST BREAKDOWN" in captured.out
    assert "OPTIMIZATION OPPORTUNITIES" in captured.out
    assert "LIKELY EXPLANATION FOR $1.57" in captured.out


def test_constants_verify_constants():
    """Verify that constants have expected values."""
    assert COST_VARIANCE_THRESHOLD == 0.50
    assert DEFAULT_DNS_RECORD_COUNT == 2
    assert EXPECTED_HOSTED_ZONE_COUNT_1 == 3
    assert EXPECTED_HOSTED_ZONE_COUNT_2 == 2
    assert EXPECTED_HEALTH_CHECK_COUNT == 2
