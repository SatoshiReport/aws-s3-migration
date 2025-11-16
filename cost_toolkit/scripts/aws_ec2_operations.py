#!/usr/bin/env python3
"""
AWS EC2 Operations Module
Common EC2 API operations extracted to reduce code duplication.
"""

from typing import Optional

from botocore.exceptions import ClientError

from cost_toolkit.common.aws_common import get_default_regions, get_instance_name
from cost_toolkit.scripts.aws_client_factory import create_ec2_client


def get_all_regions(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> list[str]:
    """
    Get list of all available AWS regions from EC2 API.

    Args:
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        list: List of AWS region names
    """
    try:
        ec2_client = create_ec2_client(
            region="us-east-1",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        response = ec2_client.describe_regions()
        return [region["RegionName"] for region in response["Regions"]]
    except ClientError as e:
        print(f"Error getting regions: {e}")
        return get_default_regions()


def find_resource_region(
    resource_type: str,
    resource_id: str,
    regions: Optional[list[str]] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> Optional[str]:
    """
    Find which AWS region contains a specified resource.

    Args:
        resource_type: Type of resource ('volume', 'snapshot', 'ami', 'instance')
        resource_id: The resource ID to locate
        regions: Optional list of regions to search. If None, searches all regions.
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        Region name if found, None otherwise

    Example:
        >>> region = find_resource_region('volume', 'vol-1234567890abcdef0')
        >>> region = find_resource_region('snapshot', 'snap-abc123', regions=['us-east-1', 'us-west-2'])
    """
    if regions is None:
        regions = get_all_regions(aws_access_key_id, aws_secret_access_key)

    # Map resource types to their describe methods and response keys
    resource_config = {
        "volume": ("describe_volumes", "VolumeIds", "Volumes", "InvalidVolume.NotFound"),
        "snapshot": (
            "describe_snapshots",
            "SnapshotIds",
            "Snapshots",
            "InvalidSnapshot.NotFound",
        ),
        "ami": ("describe_images", "ImageIds", "Images", "InvalidAMIID.NotFound"),
        "instance": (
            "describe_instances",
            "InstanceIds",
            "Reservations",
            "InvalidInstanceID.NotFound",
        ),
    }

    if resource_type not in resource_config:
        raise ValueError(
            f"Unsupported resource type: {resource_type}. "
            f"Supported types: {', '.join(resource_config.keys())}"
        )

    method_name, id_param, response_key, not_found_error = resource_config[resource_type]

    for region in regions:
        try:
            ec2_client = create_ec2_client(
                region=region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )

            # Call the appropriate describe method
            describe_method = getattr(ec2_client, method_name)
            response = describe_method(**{id_param: [resource_id]})

            # Check if resource exists in response
            if response[response_key]:
                return region

        except ClientError as e:
            if not_found_error in str(e):
                continue
            # For other errors, log but continue searching
            print(f"⚠️  Error checking {region} for {resource_id}: {str(e)}")
            continue

    return None


def get_common_regions() -> list[str]:
    """
    Get list of commonly used AWS regions for cost optimization.

    Returns:
        list: List of AWS region names
    """
    # Extended version with eu-west-3 and ap-northeast-1
    regions = get_default_regions()
    regions.extend(["eu-west-3", "ap-northeast-1"])
    return regions


# Re-export get_instance_name from aws_common for backward compatibility
# (this module is widely imported)
__all__ = [
    "get_all_regions",
    "get_common_regions",
    "get_instance_name",
    "describe_instance",
    "find_resource_region",
    "delete_snapshot",
    "terminate_instance",
]


def describe_instance(
    region: str,
    instance_id: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> dict:
    """
    Get detailed information about a single EC2 instance.

    Args:
        region: AWS region name
        instance_id: EC2 instance ID
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        dict: Instance data from describe_instances API

    Raises:
        ClientError: If instance not found or API call fails
    """
    ec2_client = create_ec2_client(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    response = ec2_client.describe_instances(InstanceIds=[instance_id])
    return response["Reservations"][0]["Instances"][0]


def delete_snapshot(
    snapshot_id: str,
    region: str,
    verbose: bool = False,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> bool:
    """
    Delete an EBS snapshot.

    Args:
        snapshot_id: The snapshot ID to delete
        region: AWS region where the snapshot is located
        verbose: If True, print snapshot details before deleting
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ec2_client = create_ec2_client(
            region=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        if verbose:
            # Get snapshot info first
            response = ec2_client.describe_snapshots(SnapshotIds=[snapshot_id])
            snapshot = response["Snapshots"][0]
            size_gb = snapshot.get("VolumeSize", 0)
            description = snapshot.get("Description", "No description")
            start_time = snapshot["StartTime"]

            print(f"🔍 Snapshot to delete: {snapshot_id}")
            print(f"   Size: {size_gb} GB")
            print(f"   Created: {start_time}")
            print(f"   Description: {description}")

        print(f"🗑️  Deleting snapshot: {snapshot_id} in {region}")
        ec2_client.delete_snapshot(SnapshotId=snapshot_id)
        print(f"   ✅ Successfully deleted {snapshot_id}")
        return True

    except ClientError as e:
        print(f"   ❌ Error deleting {snapshot_id}: {e}")
        return False


def terminate_instance(
    region: str,
    instance_id: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> bool:
    """
    Terminate an EC2 instance.

    Args:
        region: AWS region name
        instance_id: EC2 instance ID
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ec2_client = create_ec2_client(
            region=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        print(f"🗑️  Terminating instance: {instance_id}")
        response = ec2_client.terminate_instances(InstanceIds=[instance_id])

        current_state = response["TerminatingInstances"][0]["CurrentState"]["Name"]
        previous_state = response["TerminatingInstances"][0]["PreviousState"]["Name"]

        print(f"   State change: {previous_state} → {current_state}")

    except ClientError as e:
        print(f"   ❌ Failed to terminate {instance_id}: {str(e)}")
        return False
    return True


def disable_termination_protection(
    region: str,
    instance_id: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> bool:
    """
    Disable termination protection on an EC2 instance.

    Args:
        region: AWS region name
        instance_id: EC2 instance ID
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ec2_client = create_ec2_client(
            region=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        print(f"🔓 Disabling termination protection for: {instance_id}")
        ec2_client.modify_instance_attribute(
            InstanceId=instance_id,
            DisableApiTermination={"Value": False},
        )
        print("   ✅ Termination protection disabled")

    except ClientError as e:
        print(f"   ❌ Failed to disable termination protection: {str(e)}")
        return False
    return True


def describe_addresses(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> list[dict]:
    """
    Get all Elastic IP addresses in a region.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        list: List of Elastic IP address dictionaries

    Raises:
        ClientError: If API call fails
    """
    ec2_client = create_ec2_client(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    response = ec2_client.describe_addresses()
    return response.get("Addresses", [])


def describe_network_interfaces(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    filters: Optional[list[dict]] = None,
) -> list[dict]:
    """
    Get network interfaces in a region with optional filters.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key
        filters: Optional list of filter dictionaries

    Returns:
        list: List of network interface dictionaries

    Raises:
        ClientError: If API call fails
    """
    ec2_client = create_ec2_client(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    params = {}
    if filters:
        params["Filters"] = filters

    response = ec2_client.describe_network_interfaces(**params)
    return response.get("NetworkInterfaces", [])


def describe_security_groups(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    group_ids: Optional[list[str]] = None,
) -> list[dict]:
    """
    Get security groups in a region.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key
        group_ids: Optional list of security group IDs to filter

    Returns:
        list: List of security group dictionaries

    Raises:
        ClientError: If API call fails
    """
    ec2_client = create_ec2_client(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    params = {}
    if group_ids:
        params["GroupIds"] = group_ids

    response = ec2_client.describe_security_groups(**params)
    return response.get("SecurityGroups", [])


def delete_security_group(
    region: str,
    group_id: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> bool:
    """
    Delete a security group.

    Args:
        region: AWS region name
        group_id: Security group ID
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ec2_client = create_ec2_client(
            region=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        ec2_client.delete_security_group(GroupId=group_id)
        print(f"   ✅ Deleted security group: {group_id}")

    except ClientError as e:
        print(f"   ❌ Failed to delete security group {group_id}: {str(e)}")
        return False
    return True


def describe_snapshots(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    owner_ids: Optional[list[str]] = None,
    snapshot_ids: Optional[list[str]] = None,
) -> list[dict]:
    """
    Get EBS snapshots in a region.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key
        owner_ids: Optional list of owner IDs to filter (e.g., ['self'])
        snapshot_ids: Optional list of snapshot IDs to filter

    Returns:
        list: List of snapshot dictionaries

    Raises:
        ClientError: If API call fails
    """
    ec2_client = create_ec2_client(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    params = {}
    if owner_ids:
        params["OwnerIds"] = owner_ids
    if snapshot_ids:
        params["SnapshotIds"] = snapshot_ids

    response = ec2_client.describe_snapshots(**params)
    return response.get("Snapshots", [])


def describe_volumes(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    filters: Optional[list[dict]] = None,
) -> list[dict]:
    """
    Get EBS volumes in a region.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key
        filters: Optional list of filter dictionaries

    Returns:
        list: List of volume dictionaries

    Raises:
        ClientError: If API call fails
    """
    ec2_client = create_ec2_client(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    params = {}
    if filters:
        params["Filters"] = filters

    response = ec2_client.describe_volumes(**params)
    return response.get("Volumes", [])


if __name__ == "__main__":  # pragma: no cover - script entry point
    pass
