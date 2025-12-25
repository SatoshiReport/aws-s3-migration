"""Comprehensive tests for route53_helpers.py - Part 2."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.setup.route53_helpers import (
    _apply_dns_changes,
    _create_root_domain_change,
    _create_www_subdomain_change,
)


class TestCreateRootDomainChange:
    """Tests for _create_root_domain_change function."""

    def test_create_change_when_not_exists(self, capsys):
        """Test creating change when root A record doesn't exist."""
        existing_records = {"www.example.com.-A": {}}
        canva_ip = "192.168.1.1"

        result = _create_root_domain_change("example.com", existing_records, canva_ip)

        assert result is not None
        assert result is not False
        assert result["Action"] == "CREATE"
        assert result["ResourceRecordSet"]["Name"] == "example.com"
        assert result["ResourceRecordSet"]["Type"] == "A"
        assert result["ResourceRecordSet"]["TTL"] == 300
        assert result["ResourceRecordSet"]["ResourceRecords"][0]["Value"] == canva_ip
        captured = capsys.readouterr()
        assert "Will create root domain A record" in captured.out

    def test_no_change_when_exists(self):
        """Test no change when root A record already exists."""
        existing_records = {"example.com.-A": {}}
        canva_ip = "192.168.1.1"

        result = _create_root_domain_change("example.com", existing_records, canva_ip)

        assert result is None

    def test_create_change_no_ip(self, capsys):
        """Test creating change when no Canva IP provided."""
        existing_records = {}
        canva_ip = None

        result = _create_root_domain_change("example.com", existing_records, canva_ip)

        assert result is False
        captured = capsys.readouterr()
        assert "Need Canva IP address" in captured.out

    def test_create_change_empty_ip(self):
        """Test creating change when Canva IP is empty string."""
        existing_records = {}
        canva_ip = ""

        result = _create_root_domain_change("example.com", existing_records, canva_ip)

        assert result is False


class TestCreateWwwSubdomainChange:
    """Tests for _create_www_subdomain_change function."""

    def test_create_change_when_not_exists(self, capsys):
        """Test creating change when www A record doesn't exist."""
        existing_records = {"example.com.-A": {}}
        canva_ip = "192.168.1.1"

        result = _create_www_subdomain_change("example.com", existing_records, canva_ip)

        assert result is not None
        assert result is not False
        assert result["Action"] == "CREATE"
        assert result["ResourceRecordSet"]["Name"] == "www.example.com"
        assert result["ResourceRecordSet"]["Type"] == "A"
        assert result["ResourceRecordSet"]["TTL"] == 300
        assert result["ResourceRecordSet"]["ResourceRecords"][0]["Value"] == canva_ip
        captured = capsys.readouterr()
        assert "Will create www subdomain A record" in captured.out

    def test_no_change_when_exists(self):
        """Test no change when www A record already exists."""
        existing_records = {"www.example.com.-A": {}}
        canva_ip = "192.168.1.1"

        result = _create_www_subdomain_change("example.com", existing_records, canva_ip)

        assert result is None

    def test_create_change_no_ip(self, capsys):
        """Test creating change when no Canva IP provided."""
        existing_records = {}
        canva_ip = None

        result = _create_www_subdomain_change("example.com", existing_records, canva_ip)

        assert result is False
        captured = capsys.readouterr()
        assert "Need Canva IP address" in captured.out

    def test_create_change_empty_ip(self):
        """Test creating change when Canva IP is empty string."""
        existing_records = {}
        canva_ip = ""

        result = _create_www_subdomain_change("example.com", existing_records, canva_ip)

        assert result is False


class TestApplyDnsChangesBasic:
    """Tests for basic _apply_dns_changes scenarios."""

    @patch("cost_toolkit.scripts.setup.route53_helpers.datetime")
    def test_apply_single_change(self, mock_datetime, capsys):
        """Test applying a single DNS change."""
        mock_route53 = MagicMock()
        mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now

        mock_route53.change_resource_record_sets.return_value = {"ChangeInfo": {"Id": "/change/C123456789"}}

        mock_waiter = MagicMock()
        mock_route53.get_waiter.return_value = mock_waiter

        changes = [
            {
                "Action": "CREATE",
                "ResourceRecordSet": {
                    "Name": "example.com",
                    "Type": "A",
                    "ResourceRecords": [{"Value": "192.168.1.1"}],
                },
            }
        ]

        _apply_dns_changes(mock_route53, "Z123456789ABC", changes)

        mock_route53.change_resource_record_sets.assert_called_once()
        call_args = mock_route53.change_resource_record_sets.call_args
        assert call_args[1]["HostedZoneId"] == "/hostedzone/Z123456789ABC"
        assert "ChangeBatch" in call_args[1]
        assert len(call_args[1]["ChangeBatch"]["Changes"]) == 1

        mock_waiter.wait.assert_called_once()
        captured = capsys.readouterr()
        assert "DNS changes submitted" in captured.out
        assert "C123456789" in captured.out

    @patch("cost_toolkit.scripts.setup.route53_helpers.datetime")
    def test_apply_multiple_changes(self, mock_datetime, capsys):
        """Test applying multiple DNS changes."""
        mock_route53 = MagicMock()
        mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now

        mock_route53.change_resource_record_sets.return_value = {"ChangeInfo": {"Id": "/change/C123456789"}}

        mock_waiter = MagicMock()
        mock_route53.get_waiter.return_value = mock_waiter

        changes = [
            {
                "Action": "CREATE",
                "ResourceRecordSet": {
                    "Name": "example.com",
                    "Type": "A",
                    "ResourceRecords": [{"Value": "192.168.1.1"}],
                },
            },
            {
                "Action": "CREATE",
                "ResourceRecordSet": {
                    "Name": "www.example.com",
                    "Type": "A",
                    "ResourceRecords": [{"Value": "192.168.1.1"}],
                },
            },
        ]

        _apply_dns_changes(mock_route53, "Z123456789ABC", changes)

        call_args = mock_route53.change_resource_record_sets.call_args
        assert len(call_args[1]["ChangeBatch"]["Changes"]) == 2
        captured = capsys.readouterr()
        assert "DNS changes completed successfully" in captured.out


class TestApplyDnsChangesPropagation:
    """Tests for DNS propagation and metadata in _apply_dns_changes."""

    @patch("cost_toolkit.scripts.setup.route53_helpers.datetime")
    def test_apply_changes_waits_for_propagation(self, mock_datetime):
        """Test that apply changes waits for DNS propagation."""
        mock_route53 = MagicMock()
        mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now

        mock_route53.change_resource_record_sets.return_value = {"ChangeInfo": {"Id": "/change/C123456789"}}

        mock_waiter = MagicMock()
        mock_route53.get_waiter.return_value = mock_waiter

        changes = [
            {
                "Action": "CREATE",
                "ResourceRecordSet": {
                    "Name": "example.com",
                    "Type": "A",
                },
            }
        ]

        _apply_dns_changes(mock_route53, "Z123456789ABC", changes)

        mock_route53.get_waiter.assert_called_once_with("resource_record_sets_changed")
        mock_waiter.wait.assert_called_once_with(Id="/change/C123456789", WaiterConfig={"Delay": 10, "MaxAttempts": 30})

    @patch("cost_toolkit.scripts.setup.route53_helpers.datetime")
    def test_apply_changes_includes_comment(self, mock_datetime):
        """Test that change batch includes descriptive comment."""
        mock_route53 = MagicMock()
        mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now

        mock_route53.change_resource_record_sets.return_value = {"ChangeInfo": {"Id": "/change/C123456789"}}

        mock_waiter = MagicMock()
        mock_route53.get_waiter.return_value = mock_waiter

        changes = [
            {
                "Action": "CREATE",
                "ResourceRecordSet": {"Name": "example.com", "Type": "A"},
            }
        ]

        _apply_dns_changes(mock_route53, "Z123456789ABC", changes)

        call_args = mock_route53.change_resource_record_sets.call_args
        comment = call_args[1]["ChangeBatch"]["Comment"]
        assert "Creating missing DNS records for Canva setup" in comment
        assert mock_now.isoformat() in comment
