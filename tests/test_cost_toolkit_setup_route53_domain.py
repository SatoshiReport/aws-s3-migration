"""Comprehensive tests for aws_route53_domain_setup.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.setup.aws_route53_domain_setup import (
    create_missing_dns_records,
    get_current_hosted_zone_nameservers,
    update_domain_nameservers_at_registrar,
    verify_canva_dns_setup,
    verify_dns_resolution,
)
from cost_toolkit.scripts.setup.exceptions import (
    AWSAPIError,
    DNSRecordCreationError,
    DNSSetupError,
)


class TestGetCurrentHostedZoneNameservers:
    """Tests for get_current_hosted_zone_nameservers function."""

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.boto3.client")
    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup._find_hosted_zone")
    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup._get_nameserver_records")
    def test_get_nameservers_success(self, mock_get_ns, mock_find_zone, mock_boto_client, capsys):
        """Test successfully getting nameservers."""
        mock_route53 = MagicMock()
        mock_boto_client.return_value = mock_route53

        mock_zone = {"Id": "/hostedzone/Z123456789ABC", "Name": "example.com."}
        mock_find_zone.return_value = mock_zone

        mock_nameservers = [
            "ns-1.awsdns-01.com",
            "ns-2.awsdns-02.net",
            "ns-3.awsdns-03.org",
            "ns-4.awsdns-04.co.uk",
        ]
        mock_get_ns.return_value = mock_nameservers

        nameservers, zone_id = get_current_hosted_zone_nameservers("example.com")

        assert nameservers == mock_nameservers
        assert zone_id == "Z123456789ABC"
        captured = capsys.readouterr()
        assert "Found hosted zone: Z123456789ABC" in captured.out

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.boto3.client")
    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup._find_hosted_zone")
    def test_get_nameservers_client_error(self, mock_find_zone, mock_boto_client):
        """Test getting nameservers with ClientError."""
        mock_route53 = MagicMock()
        mock_boto_client.return_value = mock_route53

        error = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "list_hosted_zones",
        )
        mock_find_zone.side_effect = error

        with pytest.raises(AWSAPIError):
            get_current_hosted_zone_nameservers("example.com")


class TestUpdateDomainNameserversAtRegistrar:
    """Tests for update_domain_nameservers_at_registrar function."""

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.boto3.client")
    def test_update_nameservers_success(self, mock_boto_client, capsys):
        """Test successfully updating nameservers through Route53."""
        mock_route53domains = MagicMock()
        mock_boto_client.return_value = mock_route53domains

        mock_route53domains.get_domain_detail.return_value = {"DomainName": "example.com"}
        mock_route53domains.update_domain_nameservers.return_value = {"OperationId": "op-12345"}

        nameservers = ["ns-1.awsdns-01.com", "ns-2.awsdns-02.net"]

        result = update_domain_nameservers_at_registrar("example.com", nameservers)

        assert result is True
        mock_route53domains.update_domain_nameservers.assert_called_once()
        captured = capsys.readouterr()
        assert "Nameserver update initiated" in captured.out
        assert "op-12345" in captured.out

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.boto3.client")
    def test_update_nameservers_domain_not_found(self, mock_boto_client, capsys):
        """Test updating nameservers when domain not registered through Route53."""
        mock_route53domains = MagicMock()
        mock_boto_client.return_value = mock_route53domains

        error = ClientError(
            {"Error": {"Code": "DomainNotFound", "Message": "Domain not found"}},
            "get_domain_detail",
        )
        mock_route53domains.get_domain_detail.side_effect = error

        nameservers = ["ns-1.awsdns-01.com", "ns-2.awsdns-02.net"]

        result = update_domain_nameservers_at_registrar("example.com", nameservers)

        assert result is False
        captured = capsys.readouterr()
        assert "Domain is NOT registered through Route53" in captured.out
        assert "manually update nameservers" in captured.out

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.boto3.client")
    def test_update_nameservers_with_trailing_dots(self, mock_boto_client):
        """Test nameserver update strips trailing dots."""
        mock_route53domains = MagicMock()
        mock_boto_client.return_value = mock_route53domains

        mock_route53domains.get_domain_detail.return_value = {"DomainName": "example.com"}
        mock_route53domains.update_domain_nameservers.return_value = {"OperationId": "op-12345"}

        nameservers = ["ns-1.awsdns-01.com.", "ns-2.awsdns-02.net."]

        result = update_domain_nameservers_at_registrar("example.com", nameservers)

        assert result is True
        call_args = mock_route53domains.update_domain_nameservers.call_args
        nameserver_list = call_args[1]["Nameservers"]
        assert all(not ns["Name"].endswith(".") for ns in nameserver_list)

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.boto3.client")
    def test_update_nameservers_other_error(self, mock_boto_client, capsys):
        """Test updating nameservers with other ClientError."""
        mock_route53domains = MagicMock()
        mock_boto_client.return_value = mock_route53domains

        error = ClientError(
            {"Error": {"Code": "ServiceError", "Message": "Service error"}}, "get_domain_detail"
        )
        mock_route53domains.get_domain_detail.side_effect = error

        nameservers = ["ns-1.awsdns-01.com"]

        result = update_domain_nameservers_at_registrar("example.com", nameservers)

        assert result is False
        captured = capsys.readouterr()
        assert "Route53 Domains API error" in captured.out


class TestVerifyCanvaDnsSetup:
    """Tests for verify_canva_dns_setup function."""

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.boto3.client")
    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup._check_dns_records")
    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup._print_dns_status")
    def test_verify_dns_all_records_present(
        self, mock_print_status, mock_check_records, mock_boto_client
    ):
        """Test verification when all DNS records present."""
        mock_route53 = MagicMock()
        mock_boto_client.return_value = mock_route53

        mock_route53.list_resource_record_sets.return_value = {
            "ResourceRecordSets": [
                {
                    "Name": "example.com.",
                    "Type": "A",
                    "ResourceRecords": [{"Value": "192.168.1.1"}],
                }
            ]
        }

        mock_check_records.return_value = (True, True, True, "192.168.1.1")
        mock_print_status.return_value = True

        all_present, canva_ip = verify_canva_dns_setup("example.com", "Z123456789ABC")

        assert all_present is True
        assert canva_ip == "192.168.1.1"

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.boto3.client")
    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup._check_dns_records")
    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup._print_dns_status")
    def test_verify_dns_missing_records(
        self, mock_print_status, mock_check_records, mock_boto_client
    ):
        """Test verification when some DNS records missing."""
        mock_route53 = MagicMock()
        mock_boto_client.return_value = mock_route53

        mock_route53.list_resource_record_sets.return_value = {"ResourceRecordSets": []}

        mock_check_records.return_value = (True, False, False, "192.168.1.1")
        mock_print_status.return_value = False

        all_present, canva_ip = verify_canva_dns_setup("example.com", "Z123456789ABC")

        assert all_present is False
        assert canva_ip == "192.168.1.1"

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.boto3.client")
    def test_verify_dns_client_error(self, mock_boto_client):
        """Test DNS verification with ClientError."""
        mock_route53 = MagicMock()
        mock_boto_client.return_value = mock_route53

        error = ClientError(
            {"Error": {"Code": "NoSuchHostedZone", "Message": "Zone not found"}},
            "list_resource_record_sets",
        )
        mock_route53.list_resource_record_sets.side_effect = error

        with pytest.raises(DNSSetupError):
            verify_canva_dns_setup("example.com", "Z123456789ABC")


class TestCreateMissingDnsRecords:
    """Tests for create_missing_dns_records function."""

    def test_create_missing_records_success(self):
        """Test creating missing DNS records successfully."""
        mod = "cost_toolkit.scripts.setup.aws_route53_domain_setup"
        with (
            patch(f"{mod}.boto3.client") as mock_boto_client,
            patch(f"{mod}._build_existing_records_map") as mock_build_map,
            patch(f"{mod}._create_root_domain_change") as mock_root_change,
            patch(f"{mod}._create_www_subdomain_change") as mock_www_change,
            patch(f"{mod}._apply_dns_changes") as mock_apply_changes,
        ):
            mock_route53 = MagicMock()
            mock_boto_client.return_value = mock_route53

            mock_route53.list_resource_record_sets.return_value = {"ResourceRecordSets": []}

            mock_build_map.return_value = {}
            mock_root_change.return_value = {
                "Action": "CREATE",
                "ResourceRecordSet": {"Name": "example.com", "Type": "A"},
            }
            mock_www_change.return_value = {
                "Action": "CREATE",
                "ResourceRecordSet": {"Name": "www.example.com", "Type": "A"},
            }

            result = create_missing_dns_records("example.com", "Z123456789ABC", "192.168.1.1")

            assert result is True
            mock_apply_changes.assert_called_once()
            call_args = mock_apply_changes.call_args[0]
            assert len(call_args[2]) == 2

    def test_create_missing_records_all_exist(self, capsys):
        """Test when all DNS records already exist."""
        mod = "cost_toolkit.scripts.setup.aws_route53_domain_setup"
        with (
            patch(f"{mod}.boto3.client") as mock_boto_client,
            patch(f"{mod}._build_existing_records_map") as mock_build_map,
            patch(f"{mod}._create_root_domain_change") as mock_root_change,
            patch(f"{mod}._create_www_subdomain_change") as mock_www_change,
        ):
            mock_route53 = MagicMock()
            mock_boto_client.return_value = mock_route53

            mock_route53.list_resource_record_sets.return_value = {"ResourceRecordSets": []}

            mock_build_map.return_value = {}
            mock_root_change.return_value = None
            mock_www_change.return_value = None

            result = create_missing_dns_records("example.com", "Z123456789ABC", "192.168.1.1")

            assert result is True
            captured = capsys.readouterr()
            assert "All required DNS records already exist" in captured.out

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.boto3.client")
    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup._build_existing_records_map")
    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup._create_root_domain_change")
    def test_create_missing_records_no_canva_ip(
        self, mock_root_change, mock_build_map, mock_boto_client
    ):
        """Test creating records when Canva IP needed but not provided."""
        mock_route53 = MagicMock()
        mock_boto_client.return_value = mock_route53

        mock_route53.list_resource_record_sets.return_value = {"ResourceRecordSets": []}

        mock_build_map.return_value = {}
        mock_root_change.return_value = False

        result = create_missing_dns_records("example.com", "Z123456789ABC", None)

        assert result is False

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.boto3.client")
    def test_create_missing_records_client_error(self, mock_boto_client):
        """Test creating DNS records with ClientError."""
        mock_route53 = MagicMock()
        mock_boto_client.return_value = mock_route53

        error = ClientError(
            {"Error": {"Code": "InvalidChangeBatch", "Message": "Invalid change"}},
            "change_resource_record_sets",
        )
        mock_route53.list_resource_record_sets.side_effect = error

        with pytest.raises(DNSRecordCreationError):
            create_missing_dns_records("example.com", "Z123456789ABC", "192.168.1.1")


class TestTestDnsResolution:
    """Tests for test_dns_resolution function."""

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.socket.getaddrinfo")
    def test_dns_resolution_both_succeed(self, mock_getaddrinfo, capsys):
        """Test DNS resolution when both root and www resolve."""
        mock_getaddrinfo.side_effect = [
            [(None, None, None, None, ("192.168.1.1", 0))],
            [(None, None, None, None, ("192.168.1.2", 0))],
        ]

        verify_dns_resolution("example.com")

        captured = capsys.readouterr()
        assert "example.com resolves to: 192.168.1.1" in captured.out
        assert "www.example.com resolves to: 192.168.1.2" in captured.out

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.socket.getaddrinfo")
    def test_dns_resolution_root_fails(self, mock_getaddrinfo, capsys):
        """Test DNS resolution when root domain fails."""
        mock_getaddrinfo.side_effect = [
            [],
            [(None, None, None, None, ("192.168.1.2", 0))],
        ]

        verify_dns_resolution("example.com")

        captured = capsys.readouterr()
        assert "example.com does not resolve" in captured.out

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.socket.getaddrinfo")
    def test_dns_resolution_www_fails(self, mock_getaddrinfo, capsys):
        """Test DNS resolution when www subdomain fails."""
        mock_getaddrinfo.side_effect = [
            [(None, None, None, None, ("192.168.1.1", 0))],
            [],
        ]

        verify_dns_resolution("example.com")

        captured = capsys.readouterr()
        assert "example.com resolves to: 192.168.1.1" in captured.out
        assert "www.example.com does not resolve" in captured.out

    @patch("cost_toolkit.scripts.setup.aws_route53_domain_setup.socket.getaddrinfo")
    def test_dns_resolution_socket_error(self, mock_getaddrinfo, capsys):
        """Test DNS resolution with socket error."""
        mock_getaddrinfo.side_effect = [
            OSError("lookup failed"),
            [(None, None, None, None, ("192.168.1.2", 0))],
        ]

        verify_dns_resolution("example.com")

        captured = capsys.readouterr()
        assert "DNS lookup failed for example.com" in captured.out
