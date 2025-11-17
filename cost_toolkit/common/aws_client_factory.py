#!/usr/bin/env python3
"""
AWS Client Factory Module
Provides standardized boto3 client creation for AWS services.
"""

import os
from typing import Optional

import boto3
from dotenv import load_dotenv


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
    if os.environ.get("AWS_ENV_FILE"):
        return os.environ["AWS_ENV_FILE"]
    return os.path.expanduser("~/.env")


def load_credentials_from_env(env_path: Optional[str] = None) -> tuple[str, str]:
    """
    Load AWS credentials from .env file and return them as a tuple.

    Args:
        env_path: Optional override path (defaults to ~/.env)

    Returns:
        tuple: (aws_access_key_id, aws_secret_access_key)

    Raises:
        ValueError: If credentials are not found in .env file
    """
    resolved_path = _resolve_env_path(env_path)
    load_dotenv(resolved_path)

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError(f"AWS credentials not found in {resolved_path}")

    print(f"✅ AWS credentials loaded from {resolved_path}")
    return aws_access_key_id, aws_secret_access_key


def create_client(
    service_name: str,
    region: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
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
        aws_access_key_id, aws_secret_access_key = load_credentials_from_env()

    client_kwargs = {
        "aws_access_key_id": aws_access_key_id,
        "aws_secret_access_key": aws_secret_access_key,
    }

    if region is not None:
        client_kwargs["region_name"] = region

    return boto3.client(service_name, **client_kwargs)


# Backward-compatible wrapper functions for existing code
# These now delegate to the generic create_client() function


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


def create_iam_client(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """Create an IAM boto3 client. IAM is a global service accessed through us-east-1."""
    return create_client("iam", "us-east-1", aws_access_key_id, aws_secret_access_key)


def create_cloudwatch_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """Create a CloudWatch boto3 client with credentials."""
    return create_client("cloudwatch", region, aws_access_key_id, aws_secret_access_key)


def create_lambda_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """Create a Lambda boto3 client with credentials."""
    return create_client("lambda", region, aws_access_key_id, aws_secret_access_key)


def create_efs_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """Create an EFS boto3 client with credentials."""
    return create_client("efs", region, aws_access_key_id, aws_secret_access_key)


def create_backup_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """Create an AWS Backup boto3 client with credentials."""
    return create_client("backup", region, aws_access_key_id, aws_secret_access_key)


def create_route53resolver_client(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """Create a Route53 Resolver boto3 client. Route53 Resolver is a global service."""
    return create_client("route53resolver", None, aws_access_key_id, aws_secret_access_key)


if __name__ == "__main__":  # pragma: no cover - script entry point
    pass
