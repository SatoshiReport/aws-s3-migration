"""Tests for aws_ec2_operations.py - Region and Instance operations"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_ec2_operations import (
    describe_instance,
    disable_termination_protection,
    get_all_regions,
    terminate_instance,
)
from tests.assertions import assert_equal


# Tests for get_all_regions
@patch("cost_toolkit.common.aws_common.create_ec2_client")
def test_get_all_regions_success(mock_create_client):
    """Test get_all_regions returns list of regions from API."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2
    mock_ec2.describe_regions.return_value = {
        "Regions": [
            {"RegionName": "us-east-1"},
            {"RegionName": "us-west-2"},
            {"RegionName": "eu-west-1"},
        ]
    }

    result = get_all_regions()

    assert_equal(result, ["us-east-1", "us-west-2", "eu-west-1"])
    mock_create_client.assert_called_once_with(
        region="us-east-1",
        aws_access_key_id=None,
        aws_secret_access_key=None,
    )
    mock_ec2.describe_regions.assert_called_once()


@patch("cost_toolkit.common.aws_common.create_ec2_client")
def test_get_all_regions_with_credentials(mock_create_client):
    """Test get_all_regions passes credentials to client factory."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2
    mock_ec2.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}

    result = get_all_regions(aws_access_key_id="test_key", aws_secret_access_key="test_secret")

    assert_equal(result, ["us-east-1"])
    mock_create_client.assert_called_once_with(
        region="us-east-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("cost_toolkit.common.aws_common.create_ec2_client")
def test_get_all_regions_client_error(mock_create_client):
    """Test get_all_regions surfaces API failures."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2
    mock_ec2.describe_regions.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedOperation", "Message": "Not authorized"}}, "DescribeRegions"
    )

    with pytest.raises(ClientError):
        get_all_regions()


# Tests for describe_instance
@patch("cost_toolkit.scripts.aws_ec2_operations.create_ec2_client")
def test_describe_instance_success(mock_create_client):
    """Test describe_instance returns instance data."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2
    instance_data = {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t2.micro",
        "State": {"Name": "running"},
    }
    mock_ec2.describe_instances.return_value = {"Reservations": [{"Instances": [instance_data]}]}

    result = describe_instance("us-east-1", "i-1234567890abcdef0")

    assert_equal(result, instance_data)
    mock_create_client.assert_called_once_with(
        region="us-east-1",
        aws_access_key_id=None,
        aws_secret_access_key=None,
    )
    mock_ec2.describe_instances.assert_called_once_with(InstanceIds=["i-1234567890abcdef0"])


@patch("cost_toolkit.scripts.aws_ec2_operations.create_ec2_client")
def test_describe_instance_with_credentials(mock_create_client):
    """Test describe_instance passes credentials to client factory."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2
    instance_data = {"InstanceId": "i-1234567890abcdef0"}
    mock_ec2.describe_instances.return_value = {"Reservations": [{"Instances": [instance_data]}]}

    result = describe_instance(
        "eu-west-1",
        "i-1234567890abcdef0",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    assert_equal(result, instance_data)
    mock_create_client.assert_called_once_with(
        region="eu-west-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("cost_toolkit.scripts.aws_ec2_operations.create_ec2_client")
def test_describe_instance_not_found(mock_create_client):
    """Test describe_instance raises error when instance not found."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2
    mock_ec2.describe_instances.side_effect = ClientError(
        {"Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Instance not found"}},
        "DescribeInstances",
    )

    with pytest.raises(ClientError):
        describe_instance("us-east-1", "i-invalid")


# Tests for terminate_instance
@patch("builtins.print")
@patch("cost_toolkit.scripts.aws_ec2_operations.create_ec2_client")
def test_terminate_instance_success(mock_create_client, mock_print):
    """Test terminate_instance successfully terminates instance."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2
    mock_ec2.terminate_instances.return_value = {
        "TerminatingInstances": [
            {"CurrentState": {"Name": "shutting-down"}, "PreviousState": {"Name": "running"}}
        ]
    }

    result = terminate_instance("us-east-1", "i-1234567890abcdef0")

    assert_equal(result, True)
    mock_create_client.assert_called_once_with(
        region="us-east-1",
        aws_access_key_id=None,
        aws_secret_access_key=None,
    )
    mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=["i-1234567890abcdef0"])
    # Verify print statements were called
    assert mock_print.call_count >= 2


@patch("builtins.print")
@patch("cost_toolkit.scripts.aws_ec2_operations.create_ec2_client")
def test_terminate_instance_with_credentials(mock_create_client, mock_print):
    """Test terminate_instance passes credentials to client factory."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2
    mock_ec2.terminate_instances.return_value = {
        "TerminatingInstances": [
            {"CurrentState": {"Name": "shutting-down"}, "PreviousState": {"Name": "stopped"}}
        ]
    }

    result = terminate_instance(
        "us-west-2",
        "i-1234567890abcdef0",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    assert_equal(result, True)
    mock_create_client.assert_called_once_with(
        region="us-west-2",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )
    # Verify print statements were called
    assert mock_print.call_count >= 2


@patch("builtins.print")
@patch("cost_toolkit.scripts.aws_ec2_operations.create_ec2_client")
def test_terminate_instance_failure(mock_create_client, mock_print):
    """Test terminate_instance returns False on API error."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2
    mock_ec2.terminate_instances.side_effect = ClientError(
        {"Error": {"Code": "OperationNotPermitted", "Message": "Not authorized"}},
        "TerminateInstances",
    )

    result = terminate_instance("us-east-1", "i-1234567890abcdef0")

    assert_equal(result, False)
    # Verify error message was printed
    assert any("Failed to terminate" in str(call) for call in mock_print.call_args_list)


# Tests for disable_termination_protection
@patch("builtins.print")
@patch("cost_toolkit.scripts.aws_ec2_operations.create_ec2_client")
def test_disable_termination_protection_success(mock_create_client, mock_print):
    """Test disable_termination_protection successfully disables protection."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2

    result = disable_termination_protection("us-east-1", "i-1234567890abcdef0")

    assert_equal(result, True)
    mock_create_client.assert_called_once_with(
        region="us-east-1",
        aws_access_key_id=None,
        aws_secret_access_key=None,
    )
    mock_ec2.modify_instance_attribute.assert_called_once_with(
        InstanceId="i-1234567890abcdef0",
        DisableApiTermination={"Value": False},
    )
    # Verify success message was printed
    assert any("Termination protection disabled" in str(call) for call in mock_print.call_args_list)


@patch("builtins.print")
@patch("cost_toolkit.scripts.aws_ec2_operations.create_ec2_client")
def test_disable_termination_protection_with_credentials(mock_create_client, mock_print):
    """Test disable_termination_protection passes credentials."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2

    result = disable_termination_protection(
        "eu-west-1",
        "i-1234567890abcdef0",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    assert_equal(result, True)
    mock_create_client.assert_called_once_with(
        region="eu-west-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )
    # Verify success message was printed
    assert mock_print.call_count >= 1


@patch("builtins.print")
@patch("cost_toolkit.scripts.aws_ec2_operations.create_ec2_client")
def test_disable_termination_protection_failure(mock_create_client, mock_print):
    """Test disable_termination_protection returns False on API error."""
    mock_ec2 = MagicMock()
    mock_create_client.return_value = mock_ec2
    mock_ec2.modify_instance_attribute.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedOperation", "Message": "Not authorized"}},
        "ModifyInstanceAttribute",
    )

    result = disable_termination_protection("us-east-1", "i-1234567890abcdef0")

    assert_equal(result, False)
    # Verify error message was printed
    error_msg = "Failed to disable termination protection"
    assert any(error_msg in str(call) for call in mock_print.call_args_list)
