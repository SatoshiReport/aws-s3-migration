#!/usr/bin/env python3
"""
AWS Utilities Module
Shared utilities for AWS credential management and common functions.
"""

import sys
from typing import Optional

import boto3

from cost_toolkit.common import credential_utils
from cost_toolkit.common.aws_client_factory import (
    _resolve_env_path,
)
from cost_toolkit.common.aws_client_factory import (
    load_credentials_from_env as load_aws_credentials_from_env,
)
from cost_toolkit.common.aws_common import get_default_regions


class CredentialLoadError(Exception):
    """Raised when AWS credentials cannot be loaded."""


def load_aws_credentials(env_path: Optional[str] = None) -> None:
    """
    Load AWS credentials from a .env file.

    Args:
        env_path: Optional override path (used mainly for tests)

    Raises:
        CredentialLoadError: If credentials cannot be loaded
    """
    try:
        load_aws_credentials_from_env(env_path)
    except ValueError as exc:
        resolved_path = _resolve_env_path(env_path)
        msg = (
            f"AWS credentials not found. "
            f"Please ensure {resolved_path} contains: "
            "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION"
        )
        raise CredentialLoadError(msg) from exc


def setup_aws_credentials(env_path: Optional[str] = None):
    """
    Load AWS credentials and exit if not found.

    Args:
        env_path: Optional path to .env file containing credentials

    Note:
        This function exits the process if credentials are not found.
        For non-exit behavior, use credential_utils.setup_aws_credentials directly.
    """
    if not credential_utils.setup_aws_credentials(env_path=env_path):
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


if __name__ == "__main__":  # pragma: no cover - script entry point
    load_aws_credentials()
    print("AWS credentials loaded successfully")
