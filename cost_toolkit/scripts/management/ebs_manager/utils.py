"""
AWS EBS Volume Utility Functions Module
Contains helper functions for region discovery and tag management.
"""

from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError


def get_all_aws_regions() -> List[str]:
    """
    Get all available AWS regions by querying the EC2 service.

    Returns:
        List of AWS region names
    """
    ec2_client = boto3.client("ec2", region_name="us-east-1")
    response = ec2_client.describe_regions()
    return [region["RegionName"] for region in response["Regions"]]


def find_volume_region(volume_id: str) -> Optional[str]:
    """
    Find which region contains the specified volume.

    Args:
        volume_id: The EBS volume ID to locate

    Returns:
        Region name if found, None otherwise
    """
    regions = get_all_aws_regions()

    for region in regions:
        try:
            ec2_client = boto3.client("ec2", region_name=region)
            response = ec2_client.describe_volumes(VolumeIds=[volume_id])
            if response["Volumes"]:
                return region
        except ec2_client.exceptions.ClientError as e:
            if "InvalidVolume.NotFound" in str(e):
                continue
            raise

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

    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                for tag in instance.get("Tags", []):
                    if tag["Key"] == "Name":
                        return tag["Value"]
    except ClientError:
        return "Unknown"

    return "No Name"


def get_volume_tags(volume: Dict) -> Dict[str, str]:
    """
    Extract tags from a volume description.

    Args:
        volume: Volume description from AWS API

    Returns:
        Dictionary of tag key-value pairs
    """
    tags = {}
    for tag in volume.get("Tags", []):
        tags[tag["Key"]] = tag["Value"]
    return tags
