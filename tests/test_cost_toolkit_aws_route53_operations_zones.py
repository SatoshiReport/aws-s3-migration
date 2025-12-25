"""Tests for cost_toolkit/scripts/aws_route53_operations.py - Zone Query and Cost Operations"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_route53_operations import (
    change_resource_record_sets,
    get_change,
    get_hosted_zone,
    list_hosted_zones,
    list_resource_record_sets,
)
from tests.assertions import assert_equal


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_list_hosted_zones_default_params(mock_create_client):
    """Test list_hosted_zones with default parameters."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.list_hosted_zones.return_value = {
        "HostedZones": [
            {
                "Id": "/hostedzone/Z1234567890ABC",
                "Name": "example.com.",
                "ResourceRecordSetCount": 10,
            },
            {
                "Id": "/hostedzone/Z0987654321XYZ",
                "Name": "test.org.",
                "ResourceRecordSetCount": 5,
            },
        ]
    }

    result = list_hosted_zones()

    mock_create_client.assert_called_once_with(aws_access_key_id=None, aws_secret_access_key=None)
    mock_client.list_hosted_zones.assert_called_once()
    assert_equal(len(result), 2)
    assert_equal(result[0]["Name"], "example.com.")
    assert_equal(result[1]["Name"], "test.org.")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_list_hosted_zones_with_credentials(mock_create_client):
    """Test list_hosted_zones with AWS credentials."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.list_hosted_zones.return_value = {"HostedZones": []}

    result = list_hosted_zones(aws_access_key_id="test_key", aws_secret_access_key="test_secret")

    mock_create_client.assert_called_once_with(aws_access_key_id="test_key", aws_secret_access_key="test_secret")
    assert_equal(result, [])


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_list_hosted_zones_empty_response(mock_create_client):
    """Test list_hosted_zones with empty response."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.list_hosted_zones.return_value = {}

    result = list_hosted_zones()

    assert_equal(result, [])


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_list_hosted_zones_client_error(mock_create_client):
    """Test list_hosted_zones raises ClientError on API failure."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.list_hosted_zones.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
        "ListHostedZones",
    )

    try:
        list_hosted_zones()
        assert False, "Expected ClientError to be raised"
    except ClientError as e:
        assert_equal(e.response["Error"]["Code"], "AccessDenied")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_get_hosted_zone_success(mock_create_client):
    """Test get_hosted_zone retrieves zone details."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.get_hosted_zone.return_value = {
        "HostedZone": {
            "Id": "/hostedzone/Z1234567890ABC",
            "Name": "example.com.",
            "ResourceRecordSetCount": 15,
            "Config": {"Comment": "Production zone"},
        }
    }

    result = get_hosted_zone("Z1234567890ABC")

    mock_create_client.assert_called_once_with(aws_access_key_id=None, aws_secret_access_key=None)
    mock_client.get_hosted_zone.assert_called_once_with(Id="Z1234567890ABC")
    assert_equal(result["Id"], "/hostedzone/Z1234567890ABC")
    assert_equal(result["Name"], "example.com.")
    assert_equal(result["Config"]["Comment"], "Production zone")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_get_hosted_zone_with_credentials(mock_create_client):
    """Test get_hosted_zone with AWS credentials."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.get_hosted_zone.return_value = {"HostedZone": {}}

    _ = get_hosted_zone(
        "Z1234567890ABC",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    mock_create_client.assert_called_once_with(aws_access_key_id="test_key", aws_secret_access_key="test_secret")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_get_hosted_zone_not_found(mock_create_client):
    """Test get_hosted_zone raises ClientError when zone not found."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.get_hosted_zone.side_effect = ClientError(
        {"Error": {"Code": "NoSuchHostedZone", "Message": "Zone not found"}},
        "GetHostedZone",
    )

    try:
        get_hosted_zone("Z9999999999999")
        assert False, "Expected ClientError to be raised"
    except ClientError as e:
        assert_equal(e.response["Error"]["Code"], "NoSuchHostedZone")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_list_resource_record_sets_success(mock_create_client):
    """Test list_resource_record_sets retrieves record sets."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.list_resource_record_sets.return_value = {
        "ResourceRecordSets": [
            {
                "Name": "example.com.",
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [{"Value": "192.0.2.1"}],
            },
            {
                "Name": "www.example.com.",
                "Type": "CNAME",
                "TTL": 300,
                "ResourceRecords": [{"Value": "example.com"}],
            },
        ]
    }

    result = list_resource_record_sets("Z1234567890ABC")

    mock_create_client.assert_called_once_with(aws_access_key_id=None, aws_secret_access_key=None)
    mock_client.list_resource_record_sets.assert_called_once_with(HostedZoneId="Z1234567890ABC")
    assert_equal(len(result), 2)
    assert_equal(result[0]["Type"], "A")
    assert_equal(result[1]["Type"], "CNAME")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_list_resource_record_sets_with_credentials(mock_create_client):
    """Test list_resource_record_sets with AWS credentials."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.list_resource_record_sets.return_value = {"ResourceRecordSets": []}

    result = list_resource_record_sets(
        "Z1234567890ABC",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    mock_create_client.assert_called_once_with(aws_access_key_id="test_key", aws_secret_access_key="test_secret")
    assert_equal(result, [])


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_list_resource_record_sets_empty_response(mock_create_client):
    """Test list_resource_record_sets with empty response."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.list_resource_record_sets.return_value = {}

    result = list_resource_record_sets("Z1234567890ABC")

    assert_equal(result, [])


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_change_resource_record_sets_with_comment(mock_create_client):
    """Test change_resource_record_sets with comment."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.change_resource_record_sets.return_value = {"ChangeInfo": {}}

    changes = [{"Action": "DELETE", "ResourceRecordSet": {}}]

    _ = change_resource_record_sets("Z1234567890ABC", changes, comment="Removing old records")

    call_args = mock_client.change_resource_record_sets.call_args[1]
    assert_equal(call_args["ChangeBatch"]["Comment"], "Removing old records")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_change_resource_record_sets_with_credentials(mock_create_client):
    """Test change_resource_record_sets with AWS credentials."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.change_resource_record_sets.return_value = {"ChangeInfo": {}}

    changes = [{"Action": "UPSERT", "ResourceRecordSet": {}}]

    _ = change_resource_record_sets(
        "Z1234567890ABC",
        changes,
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    mock_create_client.assert_called_once_with(aws_access_key_id="test_key", aws_secret_access_key="test_secret")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_get_change_pending(mock_create_client):
    """Test get_change retrieves pending change status."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.get_change.return_value = {
        "ChangeInfo": {
            "Id": "/change/C1234567890ABC",
            "Status": "PENDING",
            "SubmittedAt": "2025-03-15T12:00:00Z",
        }
    }

    result = get_change("C1234567890ABC")

    mock_create_client.assert_called_once_with(aws_access_key_id=None, aws_secret_access_key=None)
    mock_client.get_change.assert_called_once_with(Id="C1234567890ABC")
    assert_equal(result["Status"], "PENDING")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_get_change_insync(mock_create_client):
    """Test get_change retrieves synced change status."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.get_change.return_value = {
        "ChangeInfo": {
            "Id": "/change/C1234567890ABC",
            "Status": "INSYNC",
            "SubmittedAt": "2025-03-15T12:00:00Z",
        }
    }

    result = get_change("C1234567890ABC")

    assert_equal(result["Status"], "INSYNC")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_get_change_with_credentials(mock_create_client):
    """Test get_change with AWS credentials."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.get_change.return_value = {"ChangeInfo": {}}

    _ = get_change(
        "C1234567890ABC",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    mock_create_client.assert_called_once_with(aws_access_key_id="test_key", aws_secret_access_key="test_secret")


@patch("cost_toolkit.scripts.aws_route53_operations.create_route53_client")
def test_get_change_not_found(mock_create_client):
    """Test get_change raises ClientError when change not found."""
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_client.get_change.side_effect = ClientError(
        {"Error": {"Code": "NoSuchChange", "Message": "Change not found"}},
        "GetChange",
    )

    try:
        get_change("C9999999999999")
        assert False, "Expected ClientError to be raised"
    except ClientError as e:
        assert_equal(e.response["Error"]["Code"], "NoSuchChange")
