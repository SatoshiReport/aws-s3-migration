"""
AWS EBS Volume Utility Functions Module
Contains helper functions for region discovery and tag management.
"""

from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

from cost_toolkit.common.aws_common import (
    get_all_aws_regions,
)
from cost_toolkit.common.aws_common import get_instance_name as _get_instance_name_with_client
from cost_toolkit.common.aws_common import (
    get_resource_tags,
)
from cost_toolkit.scripts.aws_ec2_operations import find_resource_region


def find_volume_region(volume_id: str) -> Optional[str]:
    """
    Find which region contains the specified volume.
    Delegates to canonical implementation in aws_ec2_operations.

    Args:
        volume_id: The EBS volume ID to locate

    Returns:
        Region name if found, None otherwise
    """
    return find_resource_region("volume", volume_id)


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
