"""Tests for Route53 and KMS service checks in service_checks_extended."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import botocore.exceptions
import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.billing.billing_report.service_checks_extended import (
    ServiceCheckError,
    _check_kms_key_status,
    _format_kms_status,
    check_kms_status,
    check_route53_status,
)


class TestCheckRoute53Status:
    """Test Route53 service status checking."""

    def test_route53_target_zones_deleted(self):
        """Test status when target hosted zones are deleted."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.list_hosted_zones.return_value = {
                "HostedZones": [
                    {"Name": "other-zone.com."},
                    {"Name": "example.org."},
                ]
            }
            mock_client.return_value = mock_r53
            is_resolved, message = check_route53_status()
            assert is_resolved is True
            assert "RESOLVED" in message
            assert "Target hosted zones deleted" in message
            assert "88.176.35.in-addr.arpa" in message
            assert "apicentral.ai" in message

    def test_route53_all_target_zones_exist(self):
        """Test status when all target zones still exist."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.list_hosted_zones.return_value = {
                "HostedZones": [
                    {"Name": "88.176.35.in-addr.arpa."},
                    {"Name": "apicentral.ai."},
                    {"Name": "other-zone.com."},
                ]
            }
            mock_client.return_value = mock_r53
            is_resolved, message = check_route53_status()
            assert is_resolved is False
            assert "ACTIVE" in message
            assert "2 target zones still exist" in message
            assert "88.176.35.in-addr.arpa" in message
            assert "apicentral.ai" in message

    def test_route53_partial_target_zones(self):
        """Test status when some target zones exist."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.list_hosted_zones.return_value = {
                "HostedZones": [
                    {"Name": "apicentral.ai."},
                    {"Name": "other-zone.com."},
                ]
            }
            mock_client.return_value = mock_r53
            is_resolved, message = check_route53_status()
            assert is_resolved is False
            assert "ACTIVE" in message
            assert "1 target zones still exist" in message
            assert "apicentral.ai" in message

    def test_route53_no_zones(self):
        """Test status when no hosted zones exist."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.list_hosted_zones.return_value = {"HostedZones": []}
            mock_client.return_value = mock_r53
            is_resolved, message = check_route53_status()
            assert is_resolved is True
            assert "RESOLVED" in message

    def test_route53_client_error(self):
        """Test Route53 status raises ClientError (fail-fast)."""
        with patch("boto3.client") as mock_client:
            error = ClientError({"Error": {"Code": "ServiceUnavailable"}}, "list_hosted_zones")
            mock_client.return_value.list_hosted_zones.side_effect = error
            with pytest.raises(ClientError):
                check_route53_status()

    def test_route53_zone_name_matching(self):
        """Test zone name matching with and without trailing dots."""
        with patch("boto3.client") as mock_client:
            mock_r53 = MagicMock()
            mock_r53.list_hosted_zones.return_value = {
                "HostedZones": [
                    {"Name": "88.176.35.in-addr.arpa"},
                    {"Name": "other.zone."},
                ]
            }
            mock_client.return_value = mock_r53
            is_resolved, message = check_route53_status()
            assert is_resolved is False
            assert "1 target zones still exist" in message


class TestCheckKMSKeyStatus:
    """Test KMS key status checking helper."""

    def test_kms_key_pending_deletion(self):
        """Test key in PendingDeletion state."""
        mock_client = MagicMock()
        mock_client.describe_key.return_value = {"KeyMetadata": {"KeyState": "PendingDeletion"}}
        result = _check_kms_key_status(mock_client, "key-123")
        assert result is True

    def test_kms_key_enabled(self):
        """Test key in Enabled state."""
        mock_client = MagicMock()
        mock_client.describe_key.return_value = {"KeyMetadata": {"KeyState": "Enabled"}}
        result = _check_kms_key_status(mock_client, "key-123")
        assert result is False

    def test_kms_key_disabled(self):
        """Test key in Disabled state."""
        mock_client = MagicMock()
        mock_client.describe_key.return_value = {"KeyMetadata": {"KeyState": "Disabled"}}
        result = _check_kms_key_status(mock_client, "key-123")
        assert result is False

    def test_kms_key_not_found(self):
        """Test key not found (already deleted)."""
        mock_client = MagicMock()
        error = botocore.exceptions.ClientError(
            {"Error": {"Code": "NotFoundException"}}, "describe_key"
        )
        mock_client.describe_key.side_effect = error
        result = _check_kms_key_status(mock_client, "key-123")
        assert result is True

    def test_kms_key_other_error(self):
        """Test other errors return False."""
        mock_client = MagicMock()
        error = botocore.exceptions.ClientError({"Error": {"Code": "AccessDenied"}}, "describe_key")
        mock_client.describe_key.side_effect = error
        result = _check_kms_key_status(mock_client, "key-123")
        assert result is False


class TestFormatKMSStatus:
    """Test KMS status formatting."""

    def test_format_all_pending_deletion(self):
        """Test formatting when all keys pending deletion."""
        is_resolved, message = _format_kms_status(4, 4)
        assert is_resolved is True
        assert "RESOLVED" in message
        assert "All 4 KMS keys scheduled for deletion" in message
        assert "saves $4/month" in message

    def test_format_partial_pending_deletion(self):
        """Test formatting when some keys pending deletion."""
        is_resolved, message = _format_kms_status(2, 4)
        assert is_resolved is False
        assert "PARTIAL" in message
        assert "2/4" in message
        assert "KMS keys scheduled for deletion" in message

    def test_format_no_pending_deletion(self):
        """Test formatting when no keys pending deletion."""
        is_resolved, message = _format_kms_status(0, 4)
        assert is_resolved is False
        assert "ACTIVE" in message
        assert "KMS keys still active" in message

    def test_format_single_key_pending(self):
        """Test formatting with single key pending."""
        is_resolved, message = _format_kms_status(1, 4)
        assert is_resolved is False
        assert "PARTIAL" in message
        assert "1/4" in message


class TestCheckKMSStatus:
    """Test KMS service status checking."""

    def test_kms_all_pending_deletion(self):
        """Test when all KMS keys are pending deletion."""
        with patch("boto3.client") as mock_client:
            mock_kms = MagicMock()
            mock_kms.describe_key.return_value = {"KeyMetadata": {"KeyState": "PendingDeletion"}}
            mock_client.return_value = mock_kms
            is_resolved, message = check_kms_status()
            assert is_resolved is True
            assert "RESOLVED" in message
            assert "All 4 KMS keys scheduled for deletion" in message

    def test_kms_all_active(self):
        """Test when all KMS keys are active."""
        with patch("boto3.client") as mock_client:
            mock_kms = MagicMock()
            mock_kms.describe_key.return_value = {"KeyMetadata": {"KeyState": "Enabled"}}
            mock_client.return_value = mock_kms
            is_resolved, message = check_kms_status()
            assert is_resolved is False
            assert "ACTIVE" in message

    def test_kms_partial_pending(self):
        """Test when some KMS keys are pending deletion."""
        with patch("boto3.client") as mock_client:
            mock_kms = MagicMock()
            call_count = [0]

            def describe_key_side_effect(**_):
                call_count[0] += 1
                if call_count[0] <= 2:
                    return {"KeyMetadata": {"KeyState": "PendingDeletion"}}
                return {"KeyMetadata": {"KeyState": "Enabled"}}

            mock_kms.describe_key.side_effect = describe_key_side_effect
            mock_client.return_value = mock_kms
            is_resolved, message = check_kms_status()
            assert is_resolved is False
            assert "PARTIAL" in message

    def test_kms_region_errors(self):
        """Test KMS status with region access errors."""
        with patch("boto3.client") as mock_client:
            mock_kms = MagicMock()
            error = botocore.exceptions.ClientError(
                {"Error": {"Code": "AccessDenied"}}, "describe_key"
            )
            mock_kms.describe_key.side_effect = error
            mock_client.return_value = mock_kms
            is_resolved, message = check_kms_status()
            assert is_resolved is False
            assert "ACTIVE" in message

    def test_kms_client_error(self):
        """Test KMS status raises ServiceCheckError when client creation fails in all regions."""
        with patch("boto3.client") as mock_client:
            error = ClientError({"Error": {"Code": "ServiceUnavailable"}}, "client")
            mock_client.side_effect = error
            # ClientError during client creation is caught per-region, then aggregated
            with pytest.raises(ServiceCheckError) as exc_info:
                check_kms_status()
            assert "Failed to check KMS in regions" in str(exc_info.value)

    def test_kms_mixed_states(self):
        """Test KMS with mixed key states across regions."""
        with patch("boto3.client") as mock_client:
            mock_kms = MagicMock()
            call_count = [0]

            def describe_key_mixed(**_):
                call_count[0] += 1
                if call_count[0] == 1:
                    return {"KeyMetadata": {"KeyState": "PendingDeletion"}}
                if call_count[0] == 2:
                    raise botocore.exceptions.ClientError(
                        {"Error": {"Code": "NotFoundException"}}, "describe_key"
                    )
                if call_count[0] == 3:
                    return {"KeyMetadata": {"KeyState": "Enabled"}}
                return {"KeyMetadata": {"KeyState": "Disabled"}}

            mock_kms.describe_key.side_effect = describe_key_mixed
            mock_client.return_value = mock_kms
            is_resolved, message = check_kms_status()
            assert is_resolved is False
            assert "PARTIAL" in message
