"""
AWS EBS Volume Utility Functions Module
Contains helper functions for region discovery and tag management.
"""

import boto3
from botocore.exceptions import ClientError
from typing import Dict, Optional

from cost_toolkit.common.aws_common import get_default_regions
from cost_toolkit.common.aws_common import get_instance_name as _get_instance_name_with_client
from cost_toolkit.common.aws_common import (
    get_resource_tags,
)
from cost_toolkit.scripts.aws_ec2_operations import find_resource_region

__all__ = ["get_all_aws_regions", "find_volume_region", "get_volume_tags", "get_instance_name"]


def get_all_aws_regions():
    """Get all AWS regions using EC2 describe_regions."""
    try:
        ec2_client = boto3.client("ec2", region_name="us-east-1")
        response = ec2_client.describe_regions()
        return [region["RegionName"] for region in response.get("Regions", [])]
    except ClientError:
        return get_default_regions()


def find_volume_region(volume_id: str) -> Optional[str]:
    """
    Find which region contains the specified volume.

    Args:
        volume_id: The EBS volume ID to locate

    Returns:
        Region name if found, None otherwise
    """
    for region in get_all_aws_regions():
        ec2_client = boto3.client("ec2", region_name=region)
        try:
            response = ec2_client.describe_volumes(VolumeIds=[volume_id])
            if response.get("Volumes"):
                return region
        except ClientError as e:
            if e.response["Error"]["Code"] != "InvalidVolume.NotFound":
                print(f"Warning checking volume {volume_id} in {region}: {e}")
    return None


def get_instance_name(instance_id: str, region: str) -> str:
    """
    Get the Name tag value for an EC2 instance.

    Args:
        instance_id: The EC2 instance ID
        region: AWS region where the instance is located

    Returns:
        Instance name from Name tag, or 'No Name' if not found
    """
    ec2_client = boto3.client("ec2", region_name=region)
    result = _get_instance_name_with_client(ec2_client, instance_id)
    # Convert "Unknown" to "No Name" for compatibility
    return "No Name" if result == "Unknown" else result


def get_volume_tags(volume: Dict) -> Dict[str, str]:
    """
    Extract tags from a volume description.
    Delegates to canonical implementation in aws_common.

    Args:
        volume: Volume description from AWS API

    Returns:
        Dictionary of tag key-value pairs
    """
    return get_resource_tags(volume)


if __name__ == "__main__":  # pragma: no cover - script entry point
    pass
