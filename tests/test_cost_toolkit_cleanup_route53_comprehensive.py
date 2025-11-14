"""Comprehensive tests for aws_route53_cleanup.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_route53_cleanup import (
    _calculate_total_savings,
    _delete_health_checks,
    _delete_zones,
    _print_cleanup_warning,
    _print_failed_deletions,
    _print_successful_deletions,
    _print_summary,
    delete_health_check,
    delete_hosted_zone,
)


class TestDeleteHealthCheck:
    """Tests for delete_health_check function."""

    def test_delete_health_check_http(self, capsys):
        """Test deleting HTTP health check."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.get_health_check.return_value = {
                "HealthCheck": {
                    "HealthCheckConfig": {
                        "Type": "HTTP",
                        "FullyQualifiedDomainName": "example.com",
                        "Port": 80,
                        "ResourcePath": "/health",
                    }
                }
            }
            mock_client.return_value = mock_r53

            result = delete_health_check("hc-123")

            assert result is True
            mock_r53.delete_health_check.assert_called_once_with(HealthCheckId="hc-123")
            captured = capsys.readouterr()
            assert "deleted successfully" in captured.out
            assert "Monthly savings: $0.50" in captured.out

    def test_delete_health_check_https(self):
        """Test deleting HTTPS health check."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.get_health_check.return_value = {
                "HealthCheck": {
                    "HealthCheckConfig": {
                        "Type": "HTTPS",
                        "FullyQualifiedDomainName": "secure.com",
                        "Port": 443,
                        "ResourcePath": "/",
                    }
                }
            }
            mock_client.return_value = mock_r53

            result = delete_health_check("hc-456")

            assert result is True

    def test_delete_health_check_no_details(self, capsys):
        """Test deleting health check when details unavailable."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.get_health_check.side_effect = ClientError(
                {"Error": {"Code": "NotFound"}}, "get_health_check"
            )
            mock_client.return_value = mock_r53

            result = delete_health_check("hc-789")

            assert result is True
            captured = capsys.readouterr()
            assert "Could not get health check details" in captured.out

    def test_delete_health_check_error(self, capsys):
        """Test error when deleting health check."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.get_health_check.return_value = {
                "HealthCheck": {"HealthCheckConfig": {"Type": "TCP"}}
            }
            mock_r53.delete_health_check.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "delete_health_check"
            )
            mock_client.return_value = mock_r53

            result = delete_health_check("hc-error")

            assert result is False
            captured = capsys.readouterr()
            assert "Error deleting health check" in captured.out


class TestDeleteHostedZone:
    """Tests for delete_hosted_zone function."""

    def test_delete_zone_with_records(self, capsys):
        """Test deleting zone with custom records."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.list_resource_record_sets.return_value = {
                "ResourceRecordSets": [
                    {"Type": "NS", "Name": "example.com."},
                    {"Type": "SOA", "Name": "example.com."},
                    {"Type": "A", "Name": "www.example.com."},
                    {"Type": "CNAME", "Name": "blog.example.com."},
                ]
            }
            mock_r53.change_resource_record_sets.return_value = {"ChangeInfo": {"Id": "change-123"}}
            mock_waiter = MagicMock()
            mock_r53.get_waiter.return_value = mock_waiter
            mock_client.return_value = mock_r53

            result = delete_hosted_zone("example.com.", "Z123")

            assert result is True
            mock_r53.delete_hosted_zone.assert_called_once()
            captured = capsys.readouterr()
            assert "Deleting 2 DNS records" in captured.out
            assert "deleted successfully" in captured.out

    def test_delete_zone_no_custom_records(self, capsys):
        """Test deleting zone with only NS and SOA records."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.list_resource_record_sets.return_value = {
                "ResourceRecordSets": [
                    {"Type": "NS", "Name": "example.com."},
                    {"Type": "SOA", "Name": "example.com."},
                ]
            }
            mock_client.return_value = mock_r53

            result = delete_hosted_zone("example.com.", "Z123")

            assert result is True
            captured = capsys.readouterr()
            assert "No custom DNS records to delete" in captured.out

    def test_delete_zone_record_deletion_error(self, capsys):
        """Test error when deleting DNS records."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.list_resource_record_sets.return_value = {
                "ResourceRecordSets": [{"Type": "A", "Name": "www.example.com."}]
            }
            mock_r53.change_resource_record_sets.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "change_resource_record_sets"
            )
            mock_client.return_value = mock_r53

            result = delete_hosted_zone("example.com.", "Z123")

            assert result is False
            captured = capsys.readouterr()
            assert "Error deleting DNS records" in captured.out

    def test_delete_zone_error(self, capsys):
        """Test error when deleting hosted zone."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.list_resource_record_sets.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "list_resource_record_sets"
            )
            mock_client.return_value = mock_r53

            result = delete_hosted_zone("example.com.", "Z123")

            assert result is False
            captured = capsys.readouterr()
            assert "Error deleting hosted zone" in captured.out


class TestPrintFunctions:
    """Tests for print and output functions."""

    def test_print_cleanup_warning(self, capsys):
        """Test printing cleanup warning."""
        _print_cleanup_warning()

        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "health check" in captured.out
        assert "hosted zones" in captured.out
        assert "Total monthly savings: $1.50" in captured.out

    def test_print_successful_deletions(self, capsys):
        """Test printing successful deletions."""
        _print_successful_deletions(["Zone1", "Zone2", "HealthCheck"])

        captured = capsys.readouterr()
        assert "Successfully deleted: 3" in captured.out
        assert "Zone1" in captured.out
        assert "Zone2" in captured.out

    def test_print_summary(self, capsys):
        """Test printing cleanup summary."""
        results = [
            ("Health Check", True),
            ("zone1.com.", True),
            ("zone2.com.", False),
        ]
        zones = [("zone1.com.", "Z123"), ("zone2.com.", "Z456")]

        savings = _print_summary(results, zones)

        assert savings == 1.00
        captured = capsys.readouterr()
        assert "CLEANUP SUMMARY" in captured.out
        assert "Successfully deleted: 2" in captured.out
        assert "Failed to delete: 1" in captured.out


class TestDeleteHealthChecks:
    """Tests for _delete_health_checks function."""

    def test_delete_health_checks_success(self, capsys):
        """Test successful health check deletion."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_route53_cleanup.delete_health_check",
            return_value=True,
        ):
            results = _delete_health_checks("hc-123")

        assert len(results) == 1
        assert results[0] == ("Health Check", True)
        captured = capsys.readouterr()
        assert "DELETING HEALTH CHECK" in captured.out

    def test_delete_health_checks_failure(self):
        """Test failed health check deletion."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_route53_cleanup.delete_health_check",
            return_value=False,
        ):
            results = _delete_health_checks("hc-123")

        assert results[0] == ("Health Check", False)


class TestDeleteZones:
    """Tests for _delete_zones function."""

    def test_delete_zones_success(self, capsys):
        """Test successful zone deletions."""
        zones = [("example.com.", "Z123"), ("test.com.", "Z456")]

        with patch(
            "cost_toolkit.scripts.cleanup.aws_route53_cleanup.delete_hosted_zone", return_value=True
        ):
            with patch("time.sleep"):
                results = _delete_zones(zones)

        assert len(results) == 2
        assert all(success for _, success in results)
        captured = capsys.readouterr()
        assert "DELETING HOSTED ZONES" in captured.out

    def test_delete_zones_partial_failure(self):
        """Test partial zone deletion failures."""
        zones = [("example.com.", "Z123"), ("test.com.", "Z456")]

        with patch(
            "cost_toolkit.scripts.cleanup.aws_route53_cleanup.delete_hosted_zone",
            side_effect=[True, False],
        ):
            with patch("time.sleep"):
                results = _delete_zones(zones)

        assert len(results) == 2
        assert results[0][1] is True
        assert results[1][1] is False


class TestPrintFailedDeletions:
    """Tests for _print_failed_deletions function."""

    def test_print_failed_deletions(self, capsys):
        """Test printing failed deletions."""
        _print_failed_deletions(["Zone1", "Zone2"])

        captured = capsys.readouterr()
        assert "Failed to delete: 2" in captured.out
        assert "Zone1" in captured.out

    def test_print_no_failed_deletions(self, capsys):
        """Test printing when no failures."""
        _print_failed_deletions([])

        captured = capsys.readouterr()
        assert "Failed to delete" not in captured.out


class TestCalculateTotalSavings:
    """Tests for _calculate_total_savings function."""

    def test_calculate_savings_all_success(self):
        """Test calculating savings when all deletions succeed."""
        results = [
            ("Health Check", True),
            ("zone1.com.", True),
            ("zone2.com.", True),
        ]
        zones = [("zone1.com.", "Z123"), ("zone2.com.", "Z456")]

        savings = _calculate_total_savings(results, zones)

        assert savings == 1.50  # 0.50 for HC + 0.50 * 2 zones

    def test_calculate_savings_partial_success(self):
        """Test calculating savings with partial success."""
        results = [
            ("Health Check", True),
            ("zone1.com.", True),
            ("zone2.com.", False),
        ]
        zones = [("zone1.com.", "Z123"), ("zone2.com.", "Z456")]

        savings = _calculate_total_savings(results, zones)

        assert savings == 1.00  # 0.50 for HC + 0.50 for 1 zone
