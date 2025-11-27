"""Tests for VPC and main functions in service_checks_extended."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import botocore.exceptions
import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.billing.billing_report.service_checks import ServiceCheckError
from cost_toolkit.scripts.billing.billing_report.service_checks_extended import (
    _add_service_status,
    check_vpc_status,
    get_resolved_services_status,
)


class TestCheckVPCStatus:
    """Test VPC service status checking."""

    def test_vpc_all_ips_released(self):
        """Test status when all Elastic IPs are released."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_addresses.return_value = {"Addresses": []}
            mock_client.return_value = mock_ec2
            is_resolved, message = check_vpc_status()
            assert is_resolved is True
            assert "RESOLVED" in message
            assert "All Elastic IPs released" in message
            assert "saves $14.40/month" in message

    def test_vpc_single_locked_ip(self):
        """Test status with single Elastic IP (locked by AWS)."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            _call_count = [0]

            def describe_side_effect():
                _call_count[0] += 1
                if _call_count[0] == 1:
                    return {"Addresses": [{"AllocationId": "eipalloc-123"}]}
                return {"Addresses": []}

            mock_ec2.describe_addresses.side_effect = describe_side_effect
            mock_client.return_value = mock_ec2
            is_resolved, message = check_vpc_status()
            assert is_resolved is False
            assert "NOTED" in message
            assert "1 Elastic IP locked by AWS" in message
            assert "requires Support contact" in message

    def test_vpc_multiple_ips_exist(self):
        """Test status when multiple Elastic IPs exist."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            call_count = [0]

            def describe_side_effect():
                call_count[0] += 1
                if call_count[0] == 1:
                    return {
                        "Addresses": [
                            {"AllocationId": "eipalloc-123"},
                            {"AllocationId": "eipalloc-456"},
                        ]
                    }
                return {"Addresses": [{"AllocationId": "eipalloc-789"}]}

            mock_ec2.describe_addresses.side_effect = describe_side_effect
            mock_client.return_value = mock_ec2
            is_resolved, message = check_vpc_status()
            assert is_resolved is False
            assert "UNRESOLVED" in message
            assert "3 Elastic IPs still allocated" in message

    def test_vpc_across_regions(self):
        """Test VPC status across multiple regions."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            call_count = [0]

            def describe_addresses_side_effect():
                call_count[0] += 1
                if call_count[0] == 1:
                    return {"Addresses": [{"AllocationId": "eipalloc-us-east"}]}
                return {"Addresses": [{"AllocationId": "eipalloc-eu-west"}]}

            mock_ec2.describe_addresses.side_effect = describe_addresses_side_effect
            mock_client.return_value = mock_ec2
            is_resolved, message = check_vpc_status()
            assert is_resolved is False
            assert "UNRESOLVED" in message
            assert "2 Elastic IPs still allocated" in message


class TestCheckVPCStatusErrors:
    """Error handling tests for VPC status checking."""

    def test_vpc_region_access_error(self):
        """Test VPC status with region access errors."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            error = botocore.exceptions.ClientError(
                {"Error": {"Code": "AccessDenied"}}, "describe_addresses"
            )
            mock_ec2.describe_addresses.side_effect = error
            mock_client.return_value = mock_ec2
            is_resolved, message = check_vpc_status()
            assert is_resolved is True
            assert "RESOLVED" in message
            assert "All Elastic IPs released" in message

    def test_vpc_client_error(self):
        """Test VPC status with general ClientError."""
        with patch("boto3.client") as mock_client:
            error = ClientError({"Error": {"Code": "ServiceUnavailable"}}, "client")
            mock_client.side_effect = error
            is_resolved, message = check_vpc_status()
            assert is_resolved is True
            assert "RESOLVED" in message

    def test_vpc_mixed_regions_one_error(self):
        """Test VPC when one region errors but other succeeds."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            call_count = [0]

            def describe_with_error():
                call_count[0] += 1
                if call_count[0] == 1:
                    raise botocore.exceptions.ClientError(
                        {"Error": {"Code": "AccessDenied"}}, "describe_addresses"
                    )
                return {"Addresses": [{"AllocationId": "eipalloc-123"}]}

            mock_ec2.describe_addresses.side_effect = describe_with_error
            mock_client.return_value = mock_ec2
            is_resolved, message = check_vpc_status()
            assert is_resolved is False
            assert "1 Elastic IP locked by AWS" in message


class TestAddServiceStatus:
    """Test service status addition helper."""

    def test_add_service_status_resolved(self):
        """Test adding resolved service status."""
        resolved_services = {}

        def mock_check():
            return True, "Service is resolved"

        _add_service_status(resolved_services, "TEST_SERVICE", mock_check)
        assert "TEST_SERVICE" in resolved_services
        assert resolved_services["TEST_SERVICE"] == "Service is resolved"

    def test_add_service_status_unresolved(self):
        """Test adding unresolved service status."""
        resolved_services = {}

        def mock_check():
            return False, "Service is active"

        _add_service_status(resolved_services, "TEST_SERVICE", mock_check)
        assert "TEST_SERVICE" in resolved_services
        assert resolved_services["TEST_SERVICE"] == "Service is active"

    def test_add_service_status_error(self):
        """Test adding service status with error (None is skipped)."""
        resolved_services = {}

        def mock_check():
            return None, "Service check error"

        _add_service_status(resolved_services, "TEST_SERVICE", mock_check)
        assert "TEST_SERVICE" not in resolved_services

    def test_add_service_status_multiple_services(self):
        """Test adding multiple service statuses."""
        resolved_services = {}

        def mock_check_1():
            return True, "Service 1 resolved"

        def mock_check_2():
            return False, "Service 2 active"

        _add_service_status(resolved_services, "SERVICE_1", mock_check_1)
        _add_service_status(resolved_services, "SERVICE_2", mock_check_2)
        assert len(resolved_services) == 2
        assert resolved_services["SERVICE_1"] == "Service 1 resolved"
        assert resolved_services["SERVICE_2"] == "Service 2 active"


def test_get_resolved_services_static_entries():
    """Test that static service entries fail fast when all checks raise errors."""
    with patch("boto3.client") as mock_client:
        error = ClientError({"Error": {"Code": "ServiceUnavailable"}}, "client")
        mock_client.side_effect = error
        # Now raises exception instead of returning partial results
        with pytest.raises(ServiceCheckError):
            get_resolved_services_status()


class TestGetResolvedServicesStatus:
    """Test overall service status checking - helper-based scenarios."""

    def _setup_mock_service_all_resolved(self, mock_service):
        """Helper to setup mock service with all empty responses."""
        mock_service.list_accelerators.return_value = {"Accelerators": []}
        mock_service.get_instances.return_value = {"instances": []}
        mock_service.get_relational_databases.return_value = {"relationalDatabases": []}
        mock_service.describe_canaries.return_value = {"Canaries": []}
        mock_service.describe_alarms.return_value = {"MetricAlarms": []}
        mock_service.list_functions.return_value = {"Functions": []}
        mock_service.describe_file_systems.return_value = {"FileSystems": []}
        mock_service.list_hosted_zones.return_value = {"HostedZones": []}
        mock_service.describe_key.return_value = {"KeyMetadata": {"KeyState": "PendingDeletion"}}
        mock_service.describe_addresses.return_value = {"Addresses": []}

    def _assert_aws_services_present(self, services):
        """Helper to assert AWS services are in resolved services."""
        assert "AWS GLOBAL ACCELERATOR" in services
        assert "AWS LAMBDA" in services
        assert "AWS KEY MANAGEMENT SERVICE" in services

    def _assert_amazon_services_present(self, services):
        """Helper to assert Amazon services are in resolved services."""
        assert "AMAZON LIGHTSAIL" in services
        assert "AMAZONCLOUDWATCH" in services
        assert "AMAZON ELASTIC FILE SYSTEM" in services
        assert "AMAZON ROUTE 53" in services
        assert "AMAZON VIRTUAL PRIVATE CLOUD" in services
        assert "AMAZONWORKMAIL" in services
        assert "AMAZON RELATIONAL DATABASE SERVICE" in services

    def _assert_all_services_present(self, services):
        """Helper to assert all services are in resolved services."""
        self._assert_aws_services_present(services)
        self._assert_amazon_services_present(services)
        assert "TAX" in services

    def test_get_resolved_services_all_resolved(self):
        """Test getting status when all services resolved."""
        with patch("boto3.client") as mock_client:
            mock_service = MagicMock()
            self._setup_mock_service_all_resolved(mock_service)

            def client_side_effect(_service, **_kwargs):
                return mock_service

            mock_client.side_effect = client_side_effect
            services = get_resolved_services_status()
            self._assert_all_services_present(services)

    def test_get_resolved_services_mixed_states(self):
        """Test getting status with mixed service states."""
        with patch("boto3.client") as mock_client:
            mock_service = MagicMock()
            _call_count = {"ga": 0, "ls": 0, "cw": 0, "lambda": 0}

            def list_accelerators_mock():
                return {"Accelerators": [{"Name": "acc1", "Enabled": True}]}

            def get_instances_mock():
                return {"instances": [{"name": "inst1", "state": {"name": "running"}}]}

            def describe_canaries_mock():
                return {"Canaries": []}

            def describe_alarms_mock():
                return {"MetricAlarms": []}

            def list_functions_mock():
                return {"Functions": [{"FunctionName": "func1"}]}

            mock_service.list_accelerators = list_accelerators_mock
            mock_service.get_instances = get_instances_mock
            mock_service.get_relational_databases.return_value = {"relationalDatabases": []}
            mock_service.describe_canaries = describe_canaries_mock
            mock_service.describe_alarms = describe_alarms_mock
            mock_service.list_functions = list_functions_mock
            mock_service.describe_file_systems.return_value = {"FileSystems": []}
            mock_service.list_hosted_zones.return_value = {"HostedZones": []}
            mock_service.describe_key.return_value = {"KeyMetadata": {"KeyState": "Enabled"}}
            mock_service.describe_addresses.return_value = {"Addresses": []}
            mock_client.return_value = mock_service
            services = get_resolved_services_status()
            assert "AWS GLOBAL ACCELERATOR" in services
            assert "AMAZON LIGHTSAIL" in services
            assert "AWS LAMBDA" in services
            assert len(services) >= 11
