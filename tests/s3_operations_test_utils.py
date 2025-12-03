"""Shared helpers for AWS S3 operations tests."""

from __future__ import annotations


def assert_s3_client_called(
    mock_create_client, region="us-west-2", key="test_key", secret="test_secret"
):
    """Assert S3 client factory was called with expected args."""
    mock_create_client.assert_called_once_with(
        region=region,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
    )
