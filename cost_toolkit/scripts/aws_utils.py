#!/usr/bin/env python3
"""
AWS Utilities Module
Shared utilities for AWS credential management and common functions.
"""

import sys
from typing import Optional

import boto3

from cost_toolkit.common.aws_common import get_default_regions

# Import canonical credential setup function
from cost_toolkit.common.credential_utils import (
    setup_aws_credentials as setup_aws_credentials_canonical,
)


def load_aws_credentials(env_path: Optional[str] = None) -> bool:
    """
    Load AWS credentials from a .env file.

    Args:
        env_path: Optional override path (used mainly for tests)

    Returns:
        bool: True if credentials loaded successfully, False otherwise
    """
    try:
        setup_aws_credentials_canonical(env_path)
    except ValueError:
        return False

    return True


def setup_aws_credentials(env_path: Optional[str] = None):
    """
    Load AWS credentials and exit if not found.
    This is for scripts that require credentials to function.

    DEPRECATED: Prefer using setup_aws_credentials from credential_utils
    and handling ValueError exceptions instead of process exit.
    """
    if not load_aws_credentials(env_path=env_path):
        from cost_toolkit.scripts.aws_client_factory import _resolve_env_path

        resolved_path = _resolve_env_path(env_path)
        print("⚠️  AWS credentials not found in environment variables.")
        print(f"Please ensure {resolved_path} contains:")
        print("  AWS_ACCESS_KEY_ID=your-access-key")
        print("  AWS_SECRET_ACCESS_KEY=your-secret-key")
        print("  AWS_DEFAULT_REGION=us-east-1")
        sys.exit(1)


def get_aws_regions():
    """
    Get list of common AWS regions for cost optimization.

    Returns:
        list: List of AWS region names
    """
    return get_default_regions()


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


if __name__ == "__main__":
    pass
