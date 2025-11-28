#!/usr/bin/env python3
"""
AWS Client Factory Module
Provides standardized boto3 client creation for AWS services.
"""

import os
from pathlib import Path
from typing import Optional

import boto3
from dotenv import load_dotenv


class MissingEnvPathError(ValueError):
    """Raised when no .env file path is configured."""


def _resolve_env_path(env_path: Optional[str] = None) -> str:
    """
    Determine which .env file should be used for AWS credentials.

    Priority order:
      1. Explicit parameter
      2. AWS_ENV_FILE environment variable
      3. ~/.env
    """
    if env_path:
        return env_path
    aws_env_file = os.environ.get("AWS_ENV_FILE")
    if aws_env_file:
        return aws_env_file
    return str(Path.home() / ".env")


def load_credentials_from_env(
    env_path: Optional[str] = None,
) -> tuple[str, str] | tuple[str, str, Optional[str]]:
    """
    Load AWS credentials from .env file and return them as a tuple.

    Args:
        env_path: Optional override path (defaults to ~/.env)

    Returns:
        tuple: (aws_access_key_id, aws_secret_access_key[, aws_session_token])

    Raises:
        ValueError: If credentials are not found in .env file
    """
    resolved_path = _resolve_env_path(env_path)
    load_dotenv(resolved_path)

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token = os.getenv("AWS_SESSION_TOKEN")
    if aws_access_key_id and aws_secret_access_key:
        print(f"✅ AWS credentials loaded from {resolved_path}")
        if aws_session_token:
            return aws_access_key_id, aws_secret_access_key, aws_session_token
        return aws_access_key_id, aws_secret_access_key

    # Fall back to the default boto3 credential provider chain (env, config/SSO, IAM role, etc.)
    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials:
        frozen = credentials.get_frozen_credentials()
        if frozen.token:
            return frozen.access_key, frozen.secret_key, frozen.token
        return frozen.access_key, frozen.secret_key

    raise ValueError(f"AWS credentials not found in {resolved_path} or default provider chain")


def create_client(
    service_name: str,
    region: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
):
    """
    Create a generic boto3 client for any AWS service with credentials.

    This is the primary client creation function that should be used for all AWS services.

    Args:
        service_name: AWS service name (e.g., 'ec2', 's3', 'rds', 'iam', 'ce')
        region: AWS region name (optional, not needed for global services like IAM/Route53)
        aws_access_key_id: Optional AWS access key (loads from env if not provided)
        aws_secret_access_key: Optional AWS secret key (loads from env if not provided)

    Returns:
        boto3.client: Configured AWS service client
    """
    if aws_access_key_id is None or aws_secret_access_key is None:
        loaded = load_credentials_from_env()
        aws_access_key_id, aws_secret_access_key = loaded[0], loaded[1]
        if len(loaded) > 2:
            aws_session_token = loaded[2]

    client_kwargs = {
        "aws_access_key_id": aws_access_key_id,
        "aws_secret_access_key": aws_secret_access_key,
    }

    if aws_session_token:
        client_kwargs["aws_session_token"] = aws_session_token

    if region is not None:
        client_kwargs["region_name"] = region

    return boto3.client(service_name, **client_kwargs)


# Service-specific client factory functions
# These delegate to the generic create_client() function with the appropriate service name


def create_ec2_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """Create an EC2 boto3 client with credentials."""
    return create_client("ec2", region, aws_access_key_id, aws_secret_access_key)


def create_s3_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """Create an S3 boto3 client with credentials."""
    return create_client("s3", region, aws_access_key_id, aws_secret_access_key)


def create_rds_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """Create an RDS boto3 client with credentials."""
    return create_client("rds", region, aws_access_key_id, aws_secret_access_key)


def create_route53_client(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """Create a Route53 boto3 client with credentials. Route53 is a global service."""
    return create_client("route53", None, aws_access_key_id, aws_secret_access_key)


def create_cost_explorer_client(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """Create a Cost Explorer boto3 client. Cost Explorer uses us-east-1."""
    return create_client("ce", "us-east-1", aws_access_key_id, aws_secret_access_key)


def create_route53resolver_client(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """Create a Route53 Resolver boto3 client. Route53 Resolver is a global service."""
    return create_client("route53resolver", None, aws_access_key_id, aws_secret_access_key)


if __name__ == "__main__":  # pragma: no cover - script entry point
    pass
