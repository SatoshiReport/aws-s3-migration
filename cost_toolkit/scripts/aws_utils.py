#!/usr/bin/env python3
"""
AWS Utilities Module
Shared utilities for AWS credential management and common functions.
"""

import os
import sys
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


def load_aws_credentials(env_path: Optional[str] = None) -> bool:
    """
    Load AWS credentials from a .env file.

    Args:
        env_path: Optional override path (used mainly for tests)

    Returns:
        bool: True if credentials loaded successfully, False otherwise
    """
    resolved_path = _resolve_env_path(env_path)
    load_dotenv(resolved_path)

    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        print("⚠️  AWS credentials not found in environment variables.")
        print(f"Please ensure {resolved_path} contains:")
        print("  AWS_ACCESS_KEY_ID=your-access-key")
        print("  AWS_SECRET_ACCESS_KEY=your-secret-key")
        print("  AWS_DEFAULT_REGION=us-east-1")
        return False

    print(f"✅ AWS credentials loaded from {resolved_path}")
    return True


def load_aws_credentials_from_env(env_path: Optional[str] = None) -> tuple[str, str]:
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


def setup_aws_credentials(env_path: Optional[str] = None):
    """
    Load AWS credentials and exit if not found.
    This is for scripts that require credentials to function.
    """
    if not load_aws_credentials(env_path=env_path):
        sys.exit(1)


def get_aws_regions():
    """
    Get list of common AWS regions for cost optimization.

    Returns:
        list: List of AWS region names
    """
    return [
        "us-east-1",
        "us-east-2",
        "us-west-1",
        "us-west-2",
        "eu-west-1",
        "eu-west-2",
        "eu-central-1",
        "ap-southeast-1",
        "ap-southeast-2",
    ]


def get_instance_info(instance_id: str, region_name: str) -> dict:
    """
    Get EC2 instance information for a given instance ID.

    Args:
        instance_id: EC2 instance ID
        region_name: AWS region name

    Returns:
        dict: Instance data from describe_instances API call

    Raises:
        ClientError: If instance not found or API call fails
    """
    ec2 = boto3.client("ec2", region_name=region_name)
    response = ec2.describe_instances(InstanceIds=[instance_id])
    instance = response["Reservations"][0]["Instances"][0]
    return instance
