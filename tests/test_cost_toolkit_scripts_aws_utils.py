"""Tests for cost_toolkit/scripts/aws_utils.py module."""

# pylint: disable=too-few-public-methods

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_utils import (
    get_aws_regions,
    get_instance_info,
    load_aws_credentials,
    setup_aws_credentials,
)
from tests.assertions import assert_equal


class TestLoadAwsCredentialsSuccess:
    """Test suite for load_aws_credentials successful operations."""

    def test_load_aws_credentials_success(self):
        """Test load_aws_credentials with successful credential loading."""
        with patch("cost_toolkit.scripts.aws_utils.load_aws_credentials_from_env"):
            result = load_aws_credentials()
            assert_equal(result, True)

    def test_load_aws_credentials_with_env_path(self):
        """Test load_aws_credentials with custom env path."""
        with patch("cost_toolkit.scripts.aws_utils.load_aws_credentials_from_env"):
            result = load_aws_credentials(env_path="/custom/.env")
            assert_equal(result, True)

    def test_load_aws_credentials_none_env_path(self):
        """Test load_aws_credentials with None env path."""
        with patch("cost_toolkit.scripts.aws_utils.load_aws_credentials_from_env"):
            result = load_aws_credentials(env_path=None)
            assert_equal(result, True)


class TestLoadAwsCredentialsFailure:
    """Test suite for load_aws_credentials failure handling."""

    def test_load_aws_credentials_failure(self):
        """Test load_aws_credentials when credentials not found."""
        with (
            patch(
                "cost_toolkit.scripts.aws_utils.load_aws_credentials_from_env",
                side_effect=ValueError("Credentials not found"),
            ),
            patch("cost_toolkit.scripts.aws_utils._resolve_env_path", return_value="~/.env"),
        ):
            result = load_aws_credentials()
            assert_equal(result, False)

    def test_load_aws_credentials_failure_prints_message(self, capsys):
        """Test load_aws_credentials prints helpful message on failure."""
        with (
            patch(
                "cost_toolkit.scripts.aws_utils.load_aws_credentials_from_env",
                side_effect=ValueError("Credentials not found"),
            ),
            patch(
                "cost_toolkit.scripts.aws_utils._resolve_env_path",
                return_value="/test/path/.env",
            ),
        ):
            result = load_aws_credentials()
            assert_equal(result, False)

            captured = capsys.readouterr()
            assert "AWS credentials not found" in captured.out
            assert "/test/path/.env" in captured.out
            assert "AWS_ACCESS_KEY_ID" in captured.out
            assert "AWS_SECRET_ACCESS_KEY" in captured.out
            assert "AWS_DEFAULT_REGION" in captured.out

    def test_load_aws_credentials_with_different_error_message(self):
        """Test load_aws_credentials handles different ValueError messages."""
        with (
            patch(
                "cost_toolkit.scripts.aws_utils.load_aws_credentials_from_env",
                side_effect=ValueError("Custom error message"),
            ),
            patch("cost_toolkit.scripts.aws_utils._resolve_env_path", return_value="~/.env"),
        ):
            result = load_aws_credentials()
            assert_equal(result, False)


class TestSetupAwsCredentials:
    """Test suite for setup_aws_credentials function."""

    def test_setup_aws_credentials_success(self):
        """Test setup_aws_credentials with successful credential loading."""
        with patch("cost_toolkit.common.credential_utils.setup_aws_credentials", return_value=True):
            setup_aws_credentials()  # Should not raise

    def test_setup_aws_credentials_failure(self):
        """Test setup_aws_credentials exits when credentials not found."""
        with (
            patch("cost_toolkit.common.credential_utils.setup_aws_credentials", return_value=False),
            pytest.raises(SystemExit) as exc_info,
        ):
            setup_aws_credentials()

        assert_equal(exc_info.value.code, 1)

    def test_setup_aws_credentials_with_env_path(self):
        """Test setup_aws_credentials with custom env path."""
        with patch(
            "cost_toolkit.common.credential_utils.setup_aws_credentials", return_value=True
        ) as mock_load:
            setup_aws_credentials(env_path="/custom/.env")
            mock_load.assert_called_once_with(env_path="/custom/.env")

    def test_setup_aws_credentials_with_none_env_path(self):
        """Test setup_aws_credentials with None env path."""
        with patch(
            "cost_toolkit.common.credential_utils.setup_aws_credentials", return_value=True
        ) as mock_load:
            setup_aws_credentials(env_path=None)
            mock_load.assert_called_once_with(env_path=None)

    def test_setup_aws_credentials_failure_exits_with_code_1(self):
        """Test setup_aws_credentials exits with specific code."""
        with (
            patch("cost_toolkit.common.credential_utils.setup_aws_credentials", return_value=False),
            pytest.raises(SystemExit) as exc_info,
        ):
            setup_aws_credentials()

        assert exc_info.value.code == 1


class TestGetAwsRegions:
    """Test suite for get_aws_regions function."""

    def test_get_aws_regions(self):
        """Test get_aws_regions returns region list."""
        mock_regions = ["us-east-1", "us-west-2", "eu-west-1"]
        with patch("cost_toolkit.scripts.aws_utils.get_default_regions", return_value=mock_regions):
            result = get_aws_regions()
            assert_equal(result, mock_regions)

    def test_get_aws_regions_returns_list(self):
        """Test get_aws_regions returns list type."""
        with patch("cost_toolkit.scripts.aws_utils.get_default_regions", return_value=[]):
            result = get_aws_regions()
            assert isinstance(result, list)

    def test_get_aws_regions_empty_list(self):
        """Test get_aws_regions handles empty list."""
        with patch("cost_toolkit.scripts.aws_utils.get_default_regions", return_value=[]):
            result = get_aws_regions()
            assert_equal(result, [])

    def test_get_aws_regions_multiple_regions(self):
        """Test get_aws_regions with multiple regions."""
        expected = ["us-east-1", "us-west-1", "us-west-2", "eu-central-1", "ap-southeast-1"]
        with patch("cost_toolkit.scripts.aws_utils.get_default_regions", return_value=expected):
            result = get_aws_regions()
            assert_equal(result, expected)
            assert_equal(len(result), 5)


class TestGetInstanceInfoBasicRetrieval:
    """Test suite for get_instance_info basic retrieval functionality."""

    def test_get_instance_info(self):
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

    def test_get_instance_info_multiple_calls(self):
        """Test get_instance_info with multiple sequential calls."""
        mock_instance_1 = {"InstanceId": "i-first", "InstanceType": "t2.micro"}
        mock_instance_2 = {"InstanceId": "i-second", "InstanceType": "t2.small"}

        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_instances.side_effect = [
            {"Reservations": [{"Instances": [mock_instance_1]}]},
            {"Reservations": [{"Instances": [mock_instance_2]}]},
        ]

        with patch("boto3.client", return_value=mock_ec2_client):
            result1 = get_instance_info("i-first", "us-east-1")
            result2 = get_instance_info("i-second", "us-east-1")

            assert_equal(result1["InstanceId"], "i-first")
            assert_equal(result2["InstanceId"], "i-second")
            assert_equal(mock_ec2_client.describe_instances.call_count, 2)


class TestGetInstanceInfoRegionHandling:
    """Test suite for get_instance_info region and client creation."""

    def test_get_instance_info_with_different_region(self):
        """Test get_instance_info with different region."""
        mock_instance_data = {"InstanceId": "i-test123", "InstanceType": "t3.medium"}
        mock_response = {"Reservations": [{"Instances": [mock_instance_data]}]}

        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_instances.return_value = mock_response

        with patch("boto3.client", return_value=mock_ec2_client) as mock_boto:
            result = get_instance_info("i-test123", "eu-west-1")

            assert_equal(result["InstanceId"], "i-test123")
            mock_boto.assert_called_once_with("ec2", region_name="eu-west-1")

    def test_get_instance_info_creates_correct_client(self):
        """Test get_instance_info creates EC2 client with correct parameters."""
        mock_instance_data = {"InstanceId": "i-test", "InstanceType": "t2.micro"}
        mock_response = {"Reservations": [{"Instances": [mock_instance_data]}]}

        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_instances.return_value = mock_response

        with patch("boto3.client", return_value=mock_ec2_client) as mock_boto:
            get_instance_info("i-test", "ap-southeast-1")

            mock_boto.assert_called_once_with("ec2", region_name="ap-southeast-1")


class TestGetInstanceInfoBasicAttributes:
    """Test suite for get_instance_info with basic instance attributes."""

    def test_get_instance_info_with_tags(self):
        """Test get_instance_info retrieves instance with tags."""
        mock_instance_data = {
            "InstanceId": "i-abc123",
            "InstanceType": "t2.small",
            "State": {"Name": "running"},
            "Tags": [{"Key": "Name", "Value": "test-instance"}],
        }
        mock_response = {"Reservations": [{"Instances": [mock_instance_data]}]}

        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_instances.return_value = mock_response

        with patch("boto3.client", return_value=mock_ec2_client):
            result = get_instance_info("i-abc123", "us-west-2")

            assert_equal(result["InstanceId"], "i-abc123")
            assert "Tags" in result
            assert_equal(result["Tags"][0]["Key"], "Name")
            assert_equal(result["Tags"][0]["Value"], "test-instance")

    def test_get_instance_info_with_stopped_state(self):
        """Test get_instance_info with stopped instance."""
        mock_instance_data = {
            "InstanceId": "i-stopped123",
            "InstanceType": "t2.micro",
            "State": {"Name": "stopped", "Code": 80},
        }
        mock_response = {"Reservations": [{"Instances": [mock_instance_data]}]}

        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_instances.return_value = mock_response

        with patch("boto3.client", return_value=mock_ec2_client):
            result = get_instance_info("i-stopped123", "us-east-1")

            assert_equal(result["State"]["Name"], "stopped")
            assert_equal(result["State"]["Code"], 80)


class TestGetInstanceInfoComplexData:
    """Test suite for get_instance_info with complex instance data."""

    def test_get_instance_info_with_complex_data(self):
        """Test get_instance_info with complex instance data."""
        mock_instance_data = {
            "InstanceId": "i-complex123",
            "InstanceType": "m5.large",
            "State": {"Name": "running"},
            "PrivateIpAddress": "10.0.1.100",
            "PublicIpAddress": "54.123.45.67",
            "SecurityGroups": [{"GroupName": "default", "GroupId": "sg-123456"}],
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {"VolumeId": "vol-123456", "Status": "attached"},
                }
            ],
        }
        mock_response = {"Reservations": [{"Instances": [mock_instance_data]}]}

        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_instances.return_value = mock_response

        with patch("boto3.client", return_value=mock_ec2_client):
            result = get_instance_info("i-complex123", "us-east-1")

            assert_equal(result["InstanceId"], "i-complex123")
            assert_equal(result["PrivateIpAddress"], "10.0.1.100")
            assert_equal(result["PublicIpAddress"], "54.123.45.67")
            assert "SecurityGroups" in result
            assert "BlockDeviceMappings" in result


class TestGetInstanceInfoErrorHandling:
    """Test suite for get_instance_info error handling."""

    def test_get_instance_info_client_error_propagates(self):
        """Test get_instance_info propagates ClientError."""
        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_instances.side_effect = ClientError(
            {"Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Instance not found"}},
            "DescribeInstances",
        )

        with (
            patch("boto3.client", return_value=mock_ec2_client),
            pytest.raises(ClientError) as exc_info,
        ):
            get_instance_info("i-nonexistent", "us-east-1")

        assert "InvalidInstanceID.NotFound" in str(exc_info.value)
