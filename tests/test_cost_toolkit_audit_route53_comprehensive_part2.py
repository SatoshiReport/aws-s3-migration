"""Comprehensive tests for aws_route53_audit.py - Part 2."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_route53_audit import audit_route53_health_checks


class TestAuditRoute53HealthChecksSuccess:
    """Tests for audit_route53_health_checks function - success scenarios."""

    def _assert_health_check_fields(self, check, check_id, check_type):
        """Helper to assert health check fields."""
        assert check["id"] == check_id
        assert check["type"] == check_type

    def _assert_health_checks_output(self, capsys):
        """Helper to assert health checks output messages."""
        captured = capsys.readouterr()
        assert "Auditing Route 53 Health Checks" in captured.out
        assert "Health Check: hc-123" in captured.out
        assert "Type: HTTPS" in captured.out
        assert "Target: https://example.com:443/health" in captured.out
        assert "Total health checks: 2" in captured.out
        assert "Estimated monthly cost: $1.00" in captured.out

    def test_audit_health_checks_with_checks(self, capsys):
        """Test auditing health checks with checks present."""
        with patch(
            "cost_toolkit.scripts.audit.aws_route53_audit.create_route53_client"
        ) as mock_client:
            mock_route53 = MagicMock()
            mock_route53.list_health_checks.return_value = {
                "HealthChecks": [
                    {
                        "Id": "hc-123",
                        "HealthCheckConfig": {
                            "Type": "HTTPS",
                            "FullyQualifiedDomainName": "example.com",
                            "Port": 443,
                            "ResourcePath": "/health",
                        },
                    },
                    {
                        "Id": "hc-456",
                        "HealthCheckConfig": {
                            "Type": "TCP",
                        },
                    },
                ]
            }
            mock_client.return_value = mock_route53
            health_checks = audit_route53_health_checks()
        assert len(health_checks) == 2
        self._assert_health_check_fields(health_checks[0], "hc-123", "HTTPS")
        assert health_checks[0]["monthly_cost"] == 0.50
        self._assert_health_check_fields(health_checks[1], "hc-456", "TCP")
        self._assert_health_checks_output(capsys)

    def test_audit_health_checks_http(self, capsys):
        """Test auditing HTTP health checks."""
        with patch(
            "cost_toolkit.scripts.audit.aws_route53_audit.create_route53_client"
        ) as mock_client:
            mock_route53 = MagicMock()
            mock_route53.list_health_checks.return_value = {
                "HealthChecks": [
                    {
                        "Id": "hc-http",
                        "HealthCheckConfig": {
                            "Type": "HTTP",
                            "FullyQualifiedDomainName": "api.example.com",
                            "Port": 80,
                            "ResourcePath": "/ping",
                        },
                    }
                ]
            }
            mock_client.return_value = mock_route53
            audit_route53_health_checks()
        captured = capsys.readouterr()
        assert "Target: http://api.example.com:80/ping" in captured.out

    def test_audit_health_checks_no_checks(self, capsys):
        """Test auditing when no health checks exist."""
        with patch(
            "cost_toolkit.scripts.audit.aws_route53_audit.create_route53_client"
        ) as mock_client:
            mock_route53 = MagicMock()
            mock_route53.list_health_checks.return_value = {"HealthChecks": []}
            mock_client.return_value = mock_route53
            health_checks = audit_route53_health_checks()
        assert len(health_checks) == 0
        captured = capsys.readouterr()
        assert "No health checks found" in captured.out


def test_audit_health_checks_client_error(capsys):
    """Test error handling when auditing health checks fails."""
    with patch("cost_toolkit.scripts.audit.aws_route53_audit.create_route53_client") as mock_client:
        mock_route53 = MagicMock()
        mock_route53.list_health_checks.side_effect = ClientError(
            {"Error": {"Code": "Throttling"}}, "list_health_checks"
        )
        mock_client.return_value = mock_route53
        health_checks = audit_route53_health_checks()
    assert len(health_checks) == 0
    captured = capsys.readouterr()
    assert "Error auditing health checks" in captured.out
