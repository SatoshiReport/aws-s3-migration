"""Extended coverage for billing service checks helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import botocore.exceptions
import pytest

from cost_toolkit.scripts.billing.billing_report import service_checks_extended as svc_ext
from cost_toolkit.scripts.billing.billing_report.service_checks import (
    PENDING_DELETION_TARGET,
    ServiceCheckError,
)

# pylint: disable=protected-access


@patch(
    "cost_toolkit.scripts.billing.billing_report.service_checks_extended.get_all_aws_regions",
    return_value=["us-east-1"],
)
@patch("cost_toolkit.scripts.billing.billing_report.service_checks_extended.create_client")
def test_check_lambda_status_resolved(mock_create_client, _):
    """Ensure resolved when no Lambda functions remain."""
    mock_lambda = MagicMock()
    mock_lambda.list_functions.return_value = {"Functions": []}
    mock_create_client.return_value = mock_lambda

    resolved, message = svc_ext.check_lambda_status()
    assert resolved
    assert "Lambda functions deleted" in message


@patch(
    "cost_toolkit.scripts.billing.billing_report.service_checks_extended.get_all_aws_regions",
    return_value=["us-east-1"],
)
@patch("cost_toolkit.scripts.billing.billing_report.service_checks_extended.create_client")
def test_check_lambda_status_active(mock_create_client, _):
    """Verify the check reports unresolved when functions still exist."""
    mock_lambda = MagicMock()
    mock_lambda.list_functions.return_value = {"Functions": [{"FunctionName": "foo"}]}
    mock_create_client.return_value = mock_lambda

    resolved, message = svc_ext.check_lambda_status()
    assert not resolved
    assert "Lambda functions still exist" in message


@patch(
    "cost_toolkit.scripts.billing.billing_report.service_checks_extended.get_all_aws_regions",
    return_value=["us-east-1"],
)
@patch("cost_toolkit.scripts.billing.billing_report.service_checks_extended.create_client")
def test_check_lambda_status_failure(mock_create_client, _):
    """Ensure unexpected AWS errors raise ServiceCheckError."""
    error = botocore.exceptions.ClientError({"Error": {"Code": "Error"}}, "list_functions")
    mock_create_client.side_effect = error
    with pytest.raises(ServiceCheckError):
        svc_ext.check_lambda_status()


@patch(
    "cost_toolkit.scripts.billing.billing_report.service_checks_extended.get_all_aws_regions",
    return_value=["us-east-1"],
)
@patch("cost_toolkit.scripts.billing.billing_report.service_checks_extended.create_client")
def test_check_efs_status_resolved(mock_create_client, _):
    """Assert the EFS status resolves when no filesystems exist."""
    mock_efs = MagicMock()
    mock_efs.describe_file_systems.return_value = {"FileSystems": []}
    mock_create_client.return_value = mock_efs

    resolved, message = svc_ext.check_efs_status()
    assert resolved
    assert "EFS file systems deleted" in message


def test_check_route53_status_resolved():
    """Verify the Route53 status is resolved for empty hosted zones."""
    mock_route53 = MagicMock()
    mock_route53.list_hosted_zones.return_value = {"HostedZones": []}
    with patch(
        "cost_toolkit.scripts.billing.billing_report.service_checks_extended.create_client",
        return_value=mock_route53,
    ):
        resolved, message = svc_ext.check_route53_status()
    assert resolved
    assert "Target hosted zones deleted" in message


@pytest.mark.parametrize(
    "state,expected",
    [
        ("PendingDeletion", True),
        ("Enabled", False),
    ],
)
def test_check_kms_key_status_states(state, expected):
    """Ensure _check_kms_key_status handles varying key states."""
    mock_client = MagicMock()
    mock_client.describe_key.return_value = {"KeyMetadata": {"KeyState": state}}
    assert svc_ext._check_kms_key_status(mock_client, "key") == expected


def test_check_kms_key_status_not_found():
    """Confirm missing keys are considered resolved for cleanup."""
    mock_client = MagicMock()
    error = botocore.exceptions.ClientError(
        {"Error": {"Code": "NotFoundException"}}, "describe_key"
    )
    mock_client.describe_key.side_effect = error
    assert svc_ext._check_kms_key_status(mock_client, "missing") is True


def test_format_kms_status_variants():
    """Cover formatting variations for KMS status summaries."""
    resolved_msg = svc_ext._format_kms_status(PENDING_DELETION_TARGET, PENDING_DELETION_TARGET)
    assert resolved_msg[0] is True

    partial_msg = svc_ext._format_kms_status(2, PENDING_DELETION_TARGET)
    assert partial_msg[0] is False

    active_msg = svc_ext._format_kms_status(0, PENDING_DELETION_TARGET)
    assert "ACTIVE" in active_msg[1]


@patch("cost_toolkit.common.aws_common.get_all_aws_regions", return_value=["us-east-1"])
@patch(
    "cost_toolkit.scripts.billing.billing_report.service_checks_extended._check_kms_key_status",
    return_value=True,
)
def test_check_kms_status_resolved(_mock_check, _):
    """Ensure the KMS status check reports resolved when all keys are scheduled."""
    result = svc_ext.check_kms_status()
    assert result[0] is True
    assert "KMS keys scheduled for deletion" in result[1]


@patch(
    "cost_toolkit.scripts.billing.billing_report.service_checks_extended.get_all_aws_regions",
    return_value=["us-east-1"],
)
@patch("cost_toolkit.scripts.billing.billing_report.service_checks_extended.create_client")
def test_check_vpc_status_active(mock_create_client, _):
    """Ensure VPC check is un-resolved when addresses exist."""
    mock_client = MagicMock()
    mock_client.describe_addresses.return_value = {"Addresses": [{"PublicIp": "1.1.1.1"}]}
    mock_create_client.return_value = mock_client

    resolved, message = svc_ext.check_vpc_status()
    assert not resolved
    assert "NOTED" in message


@patch(
    "cost_toolkit.scripts.billing.billing_report.service_checks_extended.get_all_aws_regions",
    return_value=["us-east-1"],
)
@patch("cost_toolkit.common.aws_client_factory.create_client")
def test_check_vpc_status_resolved(mock_create_client, _):
    """Ensure VPC check resolves when Elastic IPs are released."""
    mock_client = MagicMock()
    mock_client.describe_addresses.return_value = {"Addresses": []}
    mock_create_client.return_value = mock_client

    resolved, message = svc_ext.check_vpc_status()
    assert resolved
    assert "Elastic IPs released" in message
