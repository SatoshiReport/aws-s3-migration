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


def create_ec2_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """
    Create an EC2 boto3 client with credentials.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key (loads from env if not provided)
        aws_secret_access_key: Optional AWS secret key (loads from env if not provided)

    Returns:
        boto3.client: Configured EC2 client
    """
    if aws_access_key_id is None or aws_secret_access_key is None:
        aws_access_key_id, aws_secret_access_key = load_credentials_from_env()

    return boto3.client(
        "ec2",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def create_s3_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """
    Create an S3 boto3 client with credentials.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key (loads from env if not provided)
        aws_secret_access_key: Optional AWS secret key (loads from env if not provided)

    Returns:
        boto3.client: Configured S3 client
    """
    if aws_access_key_id is None or aws_secret_access_key is None:
        aws_access_key_id, aws_secret_access_key = load_credentials_from_env()

    return boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def create_rds_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """
    Create an RDS boto3 client with credentials.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key (loads from env if not provided)
        aws_secret_access_key: Optional AWS secret key (loads from env if not provided)

    Returns:
        boto3.client: Configured RDS client
    """
    if aws_access_key_id is None or aws_secret_access_key is None:
        aws_access_key_id, aws_secret_access_key = load_credentials_from_env()

    return boto3.client(
        "rds",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def create_route53_client(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """
    Create a Route53 boto3 client with credentials.
    Route53 is a global service and does not require a region.

    Args:
        aws_access_key_id: Optional AWS access key (loads from env if not provided)
        aws_secret_access_key: Optional AWS secret key (loads from env if not provided)

    Returns:
        boto3.client: Configured Route53 client
    """
    if aws_access_key_id is None or aws_secret_access_key is None:
        aws_access_key_id, aws_secret_access_key = load_credentials_from_env()

    return boto3.client(
        "route53",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def create_cost_explorer_client(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """
    Create a Cost Explorer boto3 client with credentials.
    Cost Explorer is always accessed through us-east-1.

    Args:
        aws_access_key_id: Optional AWS access key (loads from env if not provided)
        aws_secret_access_key: Optional AWS secret key (loads from env if not provided)

    Returns:
        boto3.client: Configured Cost Explorer client
    """
    if aws_access_key_id is None or aws_secret_access_key is None:
        aws_access_key_id, aws_secret_access_key = load_credentials_from_env()

    return boto3.client(
        "ce",
        region_name="us-east-1",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def create_iam_client(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """
    Create an IAM boto3 client with credentials.
    IAM is a global service accessed through us-east-1.

    Args:
        aws_access_key_id: Optional AWS access key (loads from env if not provided)
        aws_secret_access_key: Optional AWS secret key (loads from env if not provided)

    Returns:
        boto3.client: Configured IAM client
    """
    if aws_access_key_id is None or aws_secret_access_key is None:
        aws_access_key_id, aws_secret_access_key = load_credentials_from_env()

    return boto3.client(
        "iam",
        region_name="us-east-1",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def create_cloudwatch_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """
    Create a CloudWatch boto3 client with credentials.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key (loads from env if not provided)
        aws_secret_access_key: Optional AWS secret key (loads from env if not provided)

    Returns:
        boto3.client: Configured CloudWatch client
    """
    if aws_access_key_id is None or aws_secret_access_key is None:
        aws_access_key_id, aws_secret_access_key = load_credentials_from_env()

    return boto3.client(
        "cloudwatch",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def create_lambda_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """
    Create a Lambda boto3 client with credentials.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key (loads from env if not provided)
        aws_secret_access_key: Optional AWS secret key (loads from env if not provided)

    Returns:
        boto3.client: Configured Lambda client
    """
    if aws_access_key_id is None or aws_secret_access_key is None:
        aws_access_key_id, aws_secret_access_key = load_credentials_from_env()

    return boto3.client(
        "lambda",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def create_efs_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """
    Create an EFS boto3 client with credentials.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key (loads from env if not provided)
        aws_secret_access_key: Optional AWS secret key (loads from env if not provided)

    Returns:
        boto3.client: Configured EFS client
    """
    if aws_access_key_id is None or aws_secret_access_key is None:
        aws_access_key_id, aws_secret_access_key = load_credentials_from_env()

    return boto3.client(
        "efs",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def create_backup_client(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """
    Create an AWS Backup boto3 client with credentials.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key (loads from env if not provided)
        aws_secret_access_key: Optional AWS secret key (loads from env if not provided)

    Returns:
        boto3.client: Configured Backup client
    """
    if aws_access_key_id is None or aws_secret_access_key is None:
        aws_access_key_id, aws_secret_access_key = load_credentials_from_env()

    return boto3.client(
        "backup",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def create_route53resolver_client(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """
    Create a Route53 Resolver boto3 client with credentials.
    Route53 Resolver is a global service and does not require a region.

    Args:
        aws_access_key_id: Optional AWS access key (loads from env if not provided)
        aws_secret_access_key: Optional AWS secret key (loads from env if not provided)

    Returns:
        boto3.client: Configured Route53 Resolver client
    """
    if aws_access_key_id is None or aws_secret_access_key is None:
        aws_access_key_id, aws_secret_access_key = load_credentials_from_env()

    return boto3.client(
        "route53resolver",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


if __name__ == "__main__":
    pass
