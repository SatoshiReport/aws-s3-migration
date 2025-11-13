"""Tests for cost_toolkit/scripts/aws_client_factory.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.aws_client_factory import (
    _resolve_env_path,
    create_backup_client,
    create_cloudwatch_client,
    create_cost_explorer_client,
    create_ec2_client,
    create_efs_client,
    create_iam_client,
    create_lambda_client,
    create_rds_client,
    create_route53_client,
    create_route53resolver_client,
    create_s3_client,
)
from tests.assertions import assert_equal


def test_resolve_env_path_with_explicit_path():
    """Test _resolve_env_path returns explicit path when provided."""
    result = _resolve_env_path("/custom/path/.env")
    assert_equal(result, "/custom/path/.env")


@patch("boto3.client")
@patch("cost_toolkit.scripts.aws_client_factory.load_credentials_from_env")
def test_create_ec2_client_without_credentials(mock_load_creds, mock_boto_client):
    """Test create_ec2_client loads credentials when not provided."""
    mock_load_creds.return_value = ("test_key", "test_secret")
    mock_boto_client.return_value = MagicMock()

    _ = create_ec2_client("us-east-1")

    mock_load_creds.assert_called_once()
    mock_boto_client.assert_called_once_with(
        "ec2",
        region_name="us-east-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("boto3.client")
@patch("cost_toolkit.scripts.aws_client_factory.load_credentials_from_env")
def test_create_s3_client_without_credentials(mock_load_creds, mock_boto_client):
    """Test create_s3_client loads credentials when not provided."""
    mock_load_creds.return_value = ("test_key", "test_secret")
    mock_boto_client.return_value = MagicMock()

    _ = create_s3_client("us-west-2")

    mock_load_creds.assert_called_once()
    mock_boto_client.assert_called_once_with(
        "s3",
        region_name="us-west-2",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("boto3.client")
@patch("cost_toolkit.scripts.aws_client_factory.load_credentials_from_env")
def test_create_rds_client_without_credentials(mock_load_creds, mock_boto_client):
    """Test create_rds_client loads credentials when not provided."""
    mock_load_creds.return_value = ("test_key", "test_secret")
    mock_boto_client.return_value = MagicMock()

    _ = create_rds_client("eu-west-1")

    mock_load_creds.assert_called_once()
    mock_boto_client.assert_called_once_with(
        "rds",
        region_name="eu-west-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("boto3.client")
@patch("cost_toolkit.scripts.aws_client_factory.load_credentials_from_env")
def test_create_route53_client_without_credentials(mock_load_creds, mock_boto_client):
    """Test create_route53_client loads credentials when not provided."""
    mock_load_creds.return_value = ("test_key", "test_secret")
    mock_boto_client.return_value = MagicMock()

    _ = create_route53_client()

    mock_load_creds.assert_called_once()
    mock_boto_client.assert_called_once_with(
        "route53",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("boto3.client")
@patch("cost_toolkit.scripts.aws_client_factory.load_credentials_from_env")
def test_create_cost_explorer_client_without_credentials(mock_load_creds, mock_boto_client):
    """Test create_cost_explorer_client loads credentials when not provided."""
    mock_load_creds.return_value = ("test_key", "test_secret")
    mock_boto_client.return_value = MagicMock()

    _ = create_cost_explorer_client()

    mock_load_creds.assert_called_once()
    mock_boto_client.assert_called_once_with(
        "ce",
        region_name="us-east-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("boto3.client")
@patch("cost_toolkit.scripts.aws_client_factory.load_credentials_from_env")
def test_create_iam_client_without_credentials(mock_load_creds, mock_boto_client):
    """Test create_iam_client loads credentials when not provided."""
    mock_load_creds.return_value = ("test_key", "test_secret")
    mock_boto_client.return_value = MagicMock()

    _ = create_iam_client()

    mock_load_creds.assert_called_once()
    mock_boto_client.assert_called_once_with(
        "iam",
        region_name="us-east-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("boto3.client")
@patch("cost_toolkit.scripts.aws_client_factory.load_credentials_from_env")
def test_create_cloudwatch_client_without_credentials(mock_load_creds, mock_boto_client):
    """Test create_cloudwatch_client loads credentials when not provided."""
    mock_load_creds.return_value = ("test_key", "test_secret")
    mock_boto_client.return_value = MagicMock()

    _ = create_cloudwatch_client("ap-southeast-1")

    mock_load_creds.assert_called_once()
    mock_boto_client.assert_called_once_with(
        "cloudwatch",
        region_name="ap-southeast-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("boto3.client")
@patch("cost_toolkit.scripts.aws_client_factory.load_credentials_from_env")
def test_create_lambda_client_without_credentials(mock_load_creds, mock_boto_client):
    """Test create_lambda_client loads credentials when not provided."""
    mock_load_creds.return_value = ("test_key", "test_secret")
    mock_boto_client.return_value = MagicMock()

    _ = create_lambda_client("us-east-2")

    mock_load_creds.assert_called_once()
    mock_boto_client.assert_called_once_with(
        "lambda",
        region_name="us-east-2",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("boto3.client")
@patch("cost_toolkit.scripts.aws_client_factory.load_credentials_from_env")
def test_create_efs_client_without_credentials(mock_load_creds, mock_boto_client):
    """Test create_efs_client loads credentials when not provided."""
    mock_load_creds.return_value = ("test_key", "test_secret")
    mock_boto_client.return_value = MagicMock()

    _ = create_efs_client("ca-central-1")

    mock_load_creds.assert_called_once()
    mock_boto_client.assert_called_once_with(
        "efs",
        region_name="ca-central-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("boto3.client")
@patch("cost_toolkit.scripts.aws_client_factory.load_credentials_from_env")
def test_create_backup_client_without_credentials(mock_load_creds, mock_boto_client):
    """Test create_backup_client loads credentials when not provided."""
    mock_load_creds.return_value = ("test_key", "test_secret")
    mock_boto_client.return_value = MagicMock()

    _ = create_backup_client("us-west-1")

    mock_load_creds.assert_called_once()
    mock_boto_client.assert_called_once_with(
        "backup",
        region_name="us-west-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("boto3.client")
@patch("cost_toolkit.scripts.aws_client_factory.load_credentials_from_env")
def test_create_route53resolver_client_without_credentials(mock_load_creds, mock_boto_client):
    """Test create_route53resolver_client loads credentials when not provided."""
    mock_load_creds.return_value = ("test_key", "test_secret")
    mock_boto_client.return_value = MagicMock()

    _ = create_route53resolver_client()

    mock_load_creds.assert_called_once()
    mock_boto_client.assert_called_once_with(
        "route53resolver",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )
