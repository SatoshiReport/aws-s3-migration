"""Tests for cost_toolkit/common/aws_common.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cost_toolkit.common.aws_client_factory import (
    create_ec2_client,
    create_s3_client,
)
from cost_toolkit.common.aws_common import (
    create_ec2_and_s3_clients,
    get_default_regions,
    get_instance_name,
)
from cost_toolkit.scripts.aws_ec2_operations import terminate_instance
from tests.assertions import assert_equal


@patch("boto3.client")
def test_create_ec2_client(mock_boto_client):
    """Test create_ec2_client creates EC2 client."""
    mock_client = MagicMock()
    mock_boto_client.return_value = mock_client

    result = create_ec2_client("us-east-1", "test_key", "test_secret")

    assert_equal(result, mock_client)
    mock_boto_client.assert_called_once_with(
        "ec2",
        region_name="us-east-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("boto3.client")
def test_create_s3_client(mock_boto_client):
    """Test create_s3_client creates S3 client."""
    mock_client = MagicMock()
    mock_boto_client.return_value = mock_client

    result = create_s3_client("eu-west-1", "test_key", "test_secret")

    assert_equal(result, mock_client)
    mock_boto_client.assert_called_once_with(
        "s3",
        region_name="eu-west-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("cost_toolkit.common.aws_common.create_s3_client")
@patch("cost_toolkit.common.aws_common.create_ec2_client")
def test_create_ec2_and_s3_clients(mock_create_ec2, mock_create_s3):
    """Test create_ec2_and_s3_clients creates both clients."""
    mock_ec2_client = MagicMock()
    mock_s3_client = MagicMock()
    mock_create_ec2.return_value = mock_ec2_client
    mock_create_s3.return_value = mock_s3_client

    ec2, s3 = create_ec2_and_s3_clients("us-west-2", "test_key", "test_secret")

    assert_equal(ec2, mock_ec2_client)
    assert_equal(s3, mock_s3_client)
    mock_create_ec2.assert_called_once_with(
        region="us-west-2", aws_access_key_id="test_key", aws_secret_access_key="test_secret"
    )
    mock_create_s3.assert_called_once_with(
        region="us-west-2", aws_access_key_id="test_key", aws_secret_access_key="test_secret"
    )


@patch("builtins.print")
@patch("cost_toolkit.scripts.aws_ec2_operations.create_ec2_client")
def test_terminate_instance(mock_create_ec2, _mock_print):
    """Test terminate_instance calls terminate_instances."""
    mock_ec2 = MagicMock()
    mock_create_ec2.return_value = mock_ec2
    mock_ec2.terminate_instances.return_value = {
        "TerminatingInstances": [
            {"CurrentState": {"Name": "shutting-down"}, "PreviousState": {"Name": "running"}}
        ]
    }

    result = terminate_instance("us-east-1", "i-1234567890abcdef0", "test_key", "test_secret")

    mock_create_ec2.assert_called_once_with(
        region="us-east-1", aws_access_key_id="test_key", aws_secret_access_key="test_secret"
    )
    mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=["i-1234567890abcdef0"])
    assert result is True


def test_get_instance_name_with_name_tag():
    """Test get_instance_name returns Name tag value."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"Tags": [{"Key": "Name", "Value": "test-instance"}]}]}]
    }

    result = get_instance_name(mock_ec2, "i-1234567890abcdef0")

    assert_equal(result, "test-instance")
    mock_ec2.describe_instances.assert_called_once_with(InstanceIds=["i-1234567890abcdef0"])


def test_get_instance_name_without_name_tag():
    """Test get_instance_name returns None when Name tag missing."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"Tags": [{"Key": "Env", "Value": "prod"}]}]}]
    }

    result = get_instance_name(mock_ec2, "i-1234567890abcdef0")

    assert_equal(result, None)


def test_get_instance_name_no_tags():
    """Test get_instance_name returns None when no tags present."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {"Reservations": [{"Instances": [{}]}]}

    result = get_instance_name(mock_ec2, "i-1234567890abcdef0")

    assert_equal(result, None)


def test_get_default_regions():
    """Test get_default_regions returns expected region list."""
    regions = get_default_regions()

    # Should return a list of regions
    assert isinstance(regions, list)
    assert len(regions) > 0
    # Should include common regions
    assert "us-east-1" in regions
    assert "us-west-2" in regions
