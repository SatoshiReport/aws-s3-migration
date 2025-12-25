"""Comprehensive tests for aws_route53_domain_setup.py main function."""

from __future__ import annotations

from unittest.mock import patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.setup.aws_route53_domain_setup import main


class TestMainSuccess:
    """Tests for main function with successful DNS configuration."""

    def test_main_success_all_dns_present(self, capsys):
        """Test main function when all DNS records present."""
        mod = "cost_toolkit.scripts.setup.aws_route53_domain_setup"
        with (
            patch(f"{mod}._WAIT_EVENT.wait"),
            patch(f"{mod}.get_current_hosted_zone_nameservers") as mock_get_ns,
            patch(f"{mod}.verify_canva_dns_setup") as mock_verify_dns,
            patch(f"{mod}.create_missing_dns_records") as mock_create_records,
            patch(f"{mod}.update_domain_nameservers_at_registrar") as mock_update_ns,
            patch(f"{mod}.verify_dns_resolution") as mock_test_dns,
        ):
            nameservers = ["ns-1.awsdns-01.com", "ns-2.awsdns-02.net"]
            zone_id = "Z123456789ABC"

            mock_get_ns.return_value = (nameservers, zone_id)
            mock_verify_dns.return_value = (True, "192.168.1.1")
            mock_update_ns.return_value = True

            result = main()

            assert result == 0
            mock_get_ns.assert_called_once()
            mock_verify_dns.assert_called_once_with("iwannabenewyork.com", zone_id)
            mock_create_records.assert_not_called()
            mock_update_ns.assert_called_once()
            mock_test_dns.assert_called_once()
            captured = capsys.readouterr()
            assert "SETUP SUMMARY" in captured.out

    def test_main_success_with_missing_records(self, capsys):
        """Test main function when DNS records need to be created."""
        mod = "cost_toolkit.scripts.setup.aws_route53_domain_setup"
        with (
            patch(f"{mod}._WAIT_EVENT.wait"),
            patch(f"{mod}.get_current_hosted_zone_nameservers") as mock_get_ns,
            patch(f"{mod}.verify_canva_dns_setup") as mock_verify_dns,
            patch(f"{mod}.create_missing_dns_records") as mock_create_records,
            patch(f"{mod}.update_domain_nameservers_at_registrar") as mock_update_ns,
            patch(f"{mod}.verify_dns_resolution"),
        ):
            nameservers = ["ns-1.awsdns-01.com", "ns-2.awsdns-02.net"]
            zone_id = "Z123456789ABC"

            mock_get_ns.return_value = (nameservers, zone_id)
            mock_verify_dns.return_value = (False, "192.168.1.1")
            mock_create_records.return_value = True
            mock_update_ns.return_value = True

            result = main()

            assert result == 0
            mock_create_records.assert_called_once_with("iwannabenewyork.com", zone_id, "192.168.1.1")
            captured = capsys.readouterr()
            assert "Nameservers updated at registrar" in captured.out


class TestMainDNSRecordHandling:
    """Tests for main function DNS record handling scenarios."""

    def test_main_missing_records_no_ip(self, capsys):
        """Test main function when DNS records missing and no Canva IP."""
        mod = "cost_toolkit.scripts.setup.aws_route53_domain_setup"
        with (
            patch(f"{mod}._WAIT_EVENT.wait"),
            patch(f"{mod}.get_current_hosted_zone_nameservers") as mock_get_ns,
            patch(f"{mod}.verify_canva_dns_setup") as mock_verify_dns,
            patch(f"{mod}.create_missing_dns_records") as mock_create_records,
            patch(f"{mod}.update_domain_nameservers_at_registrar") as mock_update_ns,
            patch(f"{mod}.verify_dns_resolution"),
        ):
            nameservers = ["ns-1.awsdns-01.com", "ns-2.awsdns-02.net"]
            zone_id = "Z123456789ABC"

            mock_get_ns.return_value = (nameservers, zone_id)
            mock_verify_dns.return_value = (False, None)
            mock_update_ns.return_value = True

            result = main()

            assert result == 0
            mock_create_records.assert_not_called()
            captured = capsys.readouterr()
            assert "Cannot create missing records without Canva IP address" in captured.out

    def test_main_nameserver_update_not_needed(self, capsys):
        """Test main function when nameserver update not needed."""
        mod = "cost_toolkit.scripts.setup.aws_route53_domain_setup"
        with (
            patch(f"{mod}._WAIT_EVENT.wait") as mock_sleep,
            patch(f"{mod}.get_current_hosted_zone_nameservers") as mock_get_ns,
            patch(f"{mod}.verify_canva_dns_setup") as mock_verify_dns,
            patch(f"{mod}.update_domain_nameservers_at_registrar") as mock_update_ns,
            patch(f"{mod}.verify_dns_resolution"),
        ):
            nameservers = ["ns-1.awsdns-01.com", "ns-2.awsdns-02.net"]
            zone_id = "Z123456789ABC"

            mock_get_ns.return_value = (nameservers, zone_id)
            mock_verify_dns.return_value = (True, "192.168.1.1")
            mock_update_ns.return_value = False

            result = main()

            assert result == 0
            mock_sleep.assert_not_called()
            captured = capsys.readouterr()
            assert "Manual nameserver update required" in captured.out
            for ns in nameservers:
                assert ns in captured.out


@patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.get_current_hosted_zone_nameservers")
def test_main_client_error(mock_get_ns, capsys):
    """Test main function with ClientError."""
    error = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
        "list_hosted_zones",
    )
    mock_get_ns.side_effect = error

    result = main()

    assert result == 1
    captured = capsys.readouterr()
    assert "Error:" in captured.out


class TestMainSummaryOutput:
    """Tests for main function summary output and propagation."""

    def test_main_prints_summary(self, capsys):
        """Test main function prints complete summary."""
        mod = "cost_toolkit.scripts.setup.aws_route53_domain_setup"
        with (
            patch(f"{mod}._WAIT_EVENT.wait"),
            patch(f"{mod}.get_current_hosted_zone_nameservers") as mock_get_ns,
            patch(f"{mod}.verify_canva_dns_setup") as mock_verify_dns,
            patch(f"{mod}.update_domain_nameservers_at_registrar") as mock_update_ns,
            patch(f"{mod}.verify_dns_resolution"),
        ):
            nameservers = ["ns-1.awsdns-01.com", "ns-2.awsdns-02.net"]
            zone_id = "Z123456789ABC"

            mock_get_ns.return_value = (nameservers, zone_id)
            mock_verify_dns.return_value = (True, "192.168.1.1")
            mock_update_ns.return_value = True

            result = main()

            assert result == 0
            captured = capsys.readouterr()
            assert "SETUP SUMMARY" in captured.out
            assert "Route53 hosted zone configured" in captured.out
            assert "DNS records verified for Canva" in captured.out
            assert "Your domain should resolve to your Canva site" in captured.out
            assert "https://iwannabenewyork.com" in captured.out

    def test_main_waits_after_nameserver_update(self):
        """Test main function waits for DNS propagation after nameserver update."""
        mod = "cost_toolkit.scripts.setup.aws_route53_domain_setup"
        with (
            patch(f"{mod}._WAIT_EVENT.wait") as mock_sleep,
            patch(f"{mod}.get_current_hosted_zone_nameservers") as mock_get_ns,
            patch(f"{mod}.verify_canva_dns_setup") as mock_verify_dns,
            patch(f"{mod}.create_missing_dns_records"),
            patch(f"{mod}.update_domain_nameservers_at_registrar") as mock_update_ns,
            patch(f"{mod}.verify_dns_resolution"),
        ):
            nameservers = ["ns-1.awsdns-01.com"]
            zone_id = "Z123"

            mock_get_ns.return_value = (nameservers, zone_id)
            mock_verify_dns.return_value = (True, "192.168.1.1")
            mock_update_ns.return_value = True

            main()

            mock_sleep.assert_called_once_with(30)
