"""Comprehensive tests for aws_route53_audit.py - Part 1."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_route53_audit import (
    _print_zone_records,
    audit_route53_hosted_zones,
)


class TestPrintZoneRecords:
    """Tests for _print_zone_records function."""

    def test_print_zone_records_with_a_records(self, capsys):
        """Test printing zone records with A records."""
        mock_route53 = MagicMock()
        with patch("cost_toolkit.scripts.audit.aws_route53_audit.list_resource_record_sets") as mock_list:
            mock_list.return_value = [
                {
                    "Name": "example.com.",
                    "Type": "A",
                    "TTL": 300,
                    "ResourceRecords": [{"Value": "1.2.3.4"}],
                },
                {
                    "Name": "www.example.com.",
                    "Type": "CNAME",
                    "TTL": 600,
                    "ResourceRecords": [{"Value": "example.com"}],
                },
            ]

            _print_zone_records(mock_route53, "Z123456789")

        captured = capsys.readouterr()
        assert "Records:" in captured.out
        assert "example.com. (A) TTL: 300" in captured.out
        assert "-> 1.2.3.4" in captured.out
        assert "www.example.com. (CNAME) TTL: 600" in captured.out
        assert "-> example.com" in captured.out

    def test_print_zone_records_with_alias(self, capsys):
        """Test printing zone records with alias targets."""
        mock_route53 = MagicMock()
        with patch("cost_toolkit.scripts.audit.aws_route53_audit.list_resource_record_sets") as mock_list:
            mock_list.return_value = [
                {
                    "Name": "alias.example.com.",
                    "Type": "A",
                    "AliasTarget": {"DNSName": "elb123.us-east-1.elb.amazonaws.com"},
                }
            ]

            _print_zone_records(mock_route53, "Z123456789")

        captured = capsys.readouterr()
        assert "alias.example.com. (A)" in captured.out
        assert "-> ALIAS: elb123.us-east-1.elb.amazonaws.com" in captured.out

    def test_print_zone_records_skip_ns_soa(self, capsys):
        """Test that NS and SOA records are skipped."""
        mock_route53 = MagicMock()
        with patch("cost_toolkit.scripts.audit.aws_route53_audit.list_resource_record_sets") as mock_list:
            mock_list.return_value = [
                {"Name": "example.com.", "Type": "NS", "TTL": 172800},
                {"Name": "example.com.", "Type": "SOA", "TTL": 900},
                {"Name": "example.com.", "Type": "A", "TTL": 300},
            ]

            _print_zone_records(mock_route53, "Z123456789")

        captured = capsys.readouterr()
        assert "NS" not in captured.out
        assert "SOA" not in captured.out
        assert "(A)" in captured.out

    def test_print_zone_records_client_error(self, capsys):
        """Test error handling when listing records fails."""
        mock_route53 = MagicMock()
        with patch("cost_toolkit.scripts.audit.aws_route53_audit.list_resource_record_sets") as mock_list:
            mock_list.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "list_resource_record_sets")

            _print_zone_records(mock_route53, "Z123456789")

        captured = capsys.readouterr()
        assert "Error getting records" in captured.out


class TestAuditRoute53HostedZones:
    """Tests for audit_route53_hosted_zones function."""

    def _assert_zone_basic_fields(self, zone, zone_id, zone_name, is_private):
        """Helper to assert basic zone fields."""
        assert zone["zone_id"] == zone_id
        assert zone["zone_name"] == zone_name
        assert zone["is_private"] is is_private

    def _assert_zone_detailed_fields(self, zone, record_count, monthly_cost):
        """Helper to assert detailed zone fields."""
        assert zone["record_count"] == record_count
        assert zone["monthly_cost"] == monthly_cost

    def _assert_zones_output(self, capsys):
        """Helper to assert zone output messages."""
        captured = capsys.readouterr()
        assert "Auditing Route 53 Hosted Zones" in captured.out
        assert "Hosted Zone: example.com." in captured.out
        assert "Type: Public" in captured.out
        assert "Hosted Zone: private.local." in captured.out
        assert "Type: Private" in captured.out
        assert "Total zones: 2" in captured.out
        assert "Estimated monthly cost: $1.00" in captured.out

    def test_audit_hosted_zones_with_zones(self, capsys):
        """Test auditing hosted zones with zones present."""
        with patch("cost_toolkit.scripts.audit.aws_route53_audit.create_route53_client") as mock_client:
            with patch("cost_toolkit.scripts.audit.aws_route53_audit.list_hosted_zones") as mock_list:
                with patch("cost_toolkit.scripts.audit.aws_route53_audit._print_zone_records"):
                    mock_route53 = MagicMock()
                    mock_client.return_value = mock_route53

                    mock_list.return_value = [
                        {
                            "Id": "/hostedzone/Z123456789",
                            "Name": "example.com.",
                            "Config": {"PrivateZone": False},
                            "ResourceRecordSetCount": 10,
                        },
                        {
                            "Id": "/hostedzone/Z987654321",
                            "Name": "private.local.",
                            "Config": {"PrivateZone": True},
                            "ResourceRecordSetCount": 5,
                        },
                    ]

                    zones = audit_route53_hosted_zones()

        assert len(zones) == 2
        self._assert_zone_basic_fields(zones[0], "Z123456789", "example.com.", False)
        self._assert_zone_detailed_fields(zones[0], 10, 0.50)
        self._assert_zone_basic_fields(zones[1], "Z987654321", "private.local.", True)
        self._assert_zones_output(capsys)

    def test_audit_hosted_zones_no_zones(self, capsys):
        """Test auditing when no hosted zones exist."""
        with patch("cost_toolkit.scripts.audit.aws_route53_audit.create_route53_client"):
            with patch("cost_toolkit.scripts.audit.aws_route53_audit.list_hosted_zones") as mock_list:
                mock_list.return_value = []

                zones = audit_route53_hosted_zones()

        assert len(zones) == 0
        captured = capsys.readouterr()
        assert "No hosted zones found" in captured.out

    def test_audit_hosted_zones_client_error(self, capsys):
        """Test error handling when auditing zones fails."""
        with patch("cost_toolkit.scripts.audit.aws_route53_audit.create_route53_client"):
            with patch("cost_toolkit.scripts.audit.aws_route53_audit.list_hosted_zones") as mock_list:
                mock_list.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "list_hosted_zones")

                zones = audit_route53_hosted_zones()

        assert len(zones) == 0
        captured = capsys.readouterr()
        assert "Error auditing Route 53" in captured.out
