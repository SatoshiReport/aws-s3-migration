"""Tests for cost_toolkit/scripts/aws_route53_operations.py - Zone and Record Management"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_route53_operations import (
    change_resource_record_sets,
    create_hosted_zone,
    delete_hosted_zone,
    list_domains,
)
from tests.assertions import assert_equal


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_create_hosted_zone_minimal_params(mock_create_client):
    """Test create_hosted_zone with minimal parameters."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.create_hosted_zone.return_value = {
        "HostedZone": {
            "Id": "/hostedzone/Z1234567890ABC",
            "Name": "newdomain.com.",
            "ResourceRecordSetCount": 2,
        }
    }

    result = create_hosted_zone("newdomain.com", "unique-ref-123")

    mock_create_client.assert_called_once_with(aws_access_key_id=None, aws_secret_access_key=None)
    mock_client.create_hosted_zone.assert_called_once_with(Name="newdomain.com", CallerReference="unique-ref-123")
    assert_equal(result["Id"], "/hostedzone/Z1234567890ABC")
    assert_equal(result["Name"], "newdomain.com.")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_create_hosted_zone_with_comment(mock_create_client):
    """Test create_hosted_zone with comment."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.create_hosted_zone.return_value = {"HostedZone": {}}

    _ = create_hosted_zone("newdomain.com", "unique-ref-456", comment="Test zone")

    call_args = mock_client.create_hosted_zone.call_args[1]
    assert_equal(call_args["HostedZoneConfig"]["Comment"], "Test zone")
    assert_equal(call_args["HostedZoneConfig"]["PrivateZone"], False)


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_create_hosted_zone_private_with_vpc(mock_create_client):
    """Test create_hosted_zone for private zone with VPC config."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.create_hosted_zone.return_value = {"HostedZone": {}}

    _ = create_hosted_zone(
        "private.local",
        "unique-ref-789",
        comment="Private zone",
        private_zone=True,
        vpc_config=("vpc-12345", "us-east-1"),
    )

    call_args = mock_client.create_hosted_zone.call_args[1]
    assert_equal(call_args["HostedZoneConfig"]["PrivateZone"], True)
    assert_equal(call_args["VPC"]["VPCId"], "vpc-12345")
    assert_equal(call_args["VPC"]["VPCRegion"], "us-east-1")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_create_hosted_zone_with_credentials(mock_create_client):
    """Test create_hosted_zone with AWS credentials."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.create_hosted_zone.return_value = {"HostedZone": {}}

    _ = create_hosted_zone(
        "newdomain.com",
        "unique-ref-999",
        credentials=("test_key", "test_secret"),
    )

    mock_create_client.assert_called_once_with(aws_access_key_id="test_key", aws_secret_access_key="test_secret")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_create_hosted_zone_private_without_vpc(mock_create_client):
    """Test create_hosted_zone private zone without VPC config."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.create_hosted_zone.return_value = {"HostedZone": {}}

    _ = create_hosted_zone(
        "private.local",
        "unique-ref-111",
        comment="Private zone",
        private_zone=True,
    )

    call_args = mock_client.create_hosted_zone.call_args[1]
    assert_equal(call_args["HostedZoneConfig"]["PrivateZone"], True)
    assert "VPC" not in call_args


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_create_hosted_zone_duplicate_error(mock_create_client):
    """Test create_hosted_zone raises ClientError for duplicate zone."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.create_hosted_zone.side_effect = ClientError(
        {"Error": {"Code": "HostedZoneAlreadyExists", "Message": "Zone exists"}},
        "CreateHostedZone",
    )

    try:
        create_hosted_zone("existing.com", "unique-ref-222")
        assert False, "Expected ClientError to be raised"
    except ClientError as e:
        assert_equal(e.response["Error"]["Code"], "HostedZoneAlreadyExists")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_delete_hosted_zone_success(mock_create_client, capsys):
    """Test delete_hosted_zone successfully deletes zone."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.delete_hosted_zone.return_value = {}

    result = delete_hosted_zone("Z1234567890ABC")

    mock_create_client.assert_called_once_with(aws_access_key_id=None, aws_secret_access_key=None)
    mock_client.delete_hosted_zone.assert_called_once_with(Id="Z1234567890ABC")
    assert_equal(result, True)

    captured = capsys.readouterr()
    assert "Deleted hosted zone: Z1234567890ABC" in captured.out


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_delete_hosted_zone_with_credentials(mock_create_client):
    """Test delete_hosted_zone with AWS credentials."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.delete_hosted_zone.return_value = {}

    result = delete_hosted_zone(
        "Z1234567890ABC",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    mock_create_client.assert_called_once_with(aws_access_key_id="test_key", aws_secret_access_key="test_secret")
    assert_equal(result, True)


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_delete_hosted_zone_not_found(mock_create_client, capsys):
    """Test delete_hosted_zone handles zone not found error."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.delete_hosted_zone.side_effect = ClientError(
        {"Error": {"Code": "NoSuchHostedZone", "Message": "Zone not found"}},
        "DeleteHostedZone",
    )

    result = delete_hosted_zone("Z9999999999999")

    assert_equal(result, False)

    captured = capsys.readouterr()
    assert "Failed to delete hosted zone Z9999999999999" in captured.out


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_delete_hosted_zone_not_empty(mock_create_client, capsys):
    """Test delete_hosted_zone handles zone not empty error."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.delete_hosted_zone.side_effect = ClientError(
        {"Error": {"Code": "HostedZoneNotEmpty", "Message": "Zone has records"}},
        "DeleteHostedZone",
    )

    result = delete_hosted_zone("Z1234567890ABC")

    assert_equal(result, False)

    captured = capsys.readouterr()
    assert "Failed to delete hosted zone Z1234567890ABC" in captured.out


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_change_resource_record_sets_success(mock_create_client):
    """Test change_resource_record_sets makes record changes."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.change_resource_record_sets.return_value = {
        "ChangeInfo": {
            "Id": "/change/C1234567890ABC",
            "Status": "PENDING",
            "SubmittedAt": "2025-03-15T12:00:00Z",
        }
    }

    changes = [
        {
            "Action": "CREATE",
            "ResourceRecordSet": {
                "Name": "test.example.com",
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [{"Value": "192.0.2.1"}],
            },
        }
    ]

    result = change_resource_record_sets("Z1234567890ABC", changes)

    mock_create_client.assert_called_once_with(aws_access_key_id=None, aws_secret_access_key=None)
    mock_client.change_resource_record_sets.assert_called_once()
    call_args = mock_client.change_resource_record_sets.call_args[1]
    assert_equal(call_args["HostedZoneId"], "Z1234567890ABC")
    assert_equal(call_args["ChangeBatch"]["Changes"], changes)
    assert_equal(result["Status"], "PENDING")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_change_resource_record_sets_invalid_change(mock_create_client):
    """Test change_resource_record_sets raises ClientError for invalid change."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.change_resource_record_sets.side_effect = ClientError(
        {"Error": {"Code": "InvalidChangeBatch", "Message": "Invalid change"}},
        "ChangeResourceRecordSets",
    )

    changes = [{"Action": "INVALID", "ResourceRecordSet": {}}]

    try:
        change_resource_record_sets("Z1234567890ABC", changes)
        assert False, "Expected ClientError to be raised"
    except ClientError as e:
        assert_equal(e.response["Error"]["Code"], "InvalidChangeBatch")


def test_list_domains_raises_not_implemented():
    """List domains should fail fast until route53domains support is implemented."""
    with pytest.raises(NotImplementedError):
        list_domains()


def test_list_domains_with_credentials_raises_not_implemented():
    """List domains should fail fast even when credentials are provided."""
    with pytest.raises(NotImplementedError):
        list_domains(aws_access_key_id="test_key", aws_secret_access_key="test_secret")
