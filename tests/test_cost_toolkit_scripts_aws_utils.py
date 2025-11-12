"""Tests for cost_toolkit/scripts/aws_utils.py module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cost_toolkit.scripts.aws_utils import (
    get_aws_regions,
    get_instance_info,
    load_aws_credentials,
    setup_aws_credentials,
)
from tests.assertions import assert_equal


def test_load_aws_credentials_success():
    """Test load_aws_credentials with successful credential loading."""
    with patch("cost_toolkit.scripts.aws_utils.load_aws_credentials_from_env"):
        result = load_aws_credentials()
        assert_equal(result, True)


def test_load_aws_credentials_failure():
    """Test load_aws_credentials when credentials not found."""
    with patch(
        "cost_toolkit.scripts.aws_utils.load_aws_credentials_from_env",
        side_effect=ValueError("Credentials not found"),
    ):
        result = load_aws_credentials()
        assert_equal(result, False)


def test_load_aws_credentials_with_env_path():
    """Test load_aws_credentials with custom env path."""
    with patch("cost_toolkit.scripts.aws_utils.load_aws_credentials_from_env"):
        result = load_aws_credentials(env_path="/custom/.env")
        assert_equal(result, True)


def test_setup_aws_credentials_success():
    """Test setup_aws_credentials with successful credential loading."""
    with patch("cost_toolkit.scripts.aws_utils.load_aws_credentials", return_value=True):
        setup_aws_credentials()  # Should not raise


def test_setup_aws_credentials_failure():
    """Test setup_aws_credentials exits when credentials not found."""
    with (
        patch("cost_toolkit.scripts.aws_utils.load_aws_credentials", return_value=False),
        pytest.raises(SystemExit) as exc_info,
    ):
        setup_aws_credentials()

    assert_equal(exc_info.value.code, 1)


def test_get_aws_regions():
    """Test get_aws_regions returns region list."""
    mock_regions = ["us-east-1", "us-west-2", "eu-west-1"]
    with patch("cost_toolkit.scripts.aws_utils.get_default_regions", return_value=mock_regions):
        result = get_aws_regions()
        assert_equal(result, mock_regions)


def test_get_instance_info():
    """Test get_instance_info retrieves instance data."""
    mock_instance_data = {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t2.micro",
        "State": {"Name": "running"},
    }
    mock_response = {"Reservations": [{"Instances": [mock_instance_data]}]}

    mock_ec2_client = MagicMock()
    mock_ec2_client.describe_instances.return_value = mock_response

    with patch("boto3.client", return_value=mock_ec2_client):
        result = get_instance_info("i-1234567890abcdef0", "us-east-1")

        assert_equal(result["InstanceId"], "i-1234567890abcdef0")
        assert_equal(result["InstanceType"], "t2.micro")
        mock_ec2_client.describe_instances.assert_called_once_with(
            InstanceIds=["i-1234567890abcdef0"]
        )


def test_get_instance_info_with_different_region():
    """Test get_instance_info with different region."""
    mock_instance_data = {"InstanceId": "i-test123", "InstanceType": "t3.medium"}
    mock_response = {"Reservations": [{"Instances": [mock_instance_data]}]}

    mock_ec2_client = MagicMock()
    mock_ec2_client.describe_instances.return_value = mock_response

    with patch("boto3.client", return_value=mock_ec2_client) as mock_boto:
        result = get_instance_info("i-test123", "eu-west-1")

        assert_equal(result["InstanceId"], "i-test123")
        mock_boto.assert_called_once_with("ec2", region_name="eu-west-1")
