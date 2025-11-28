#!/usr/bin/env python3
"""
AWS EC2 Operations Module
Common EC2 API operations extracted to reduce code duplication.
"""

from typing import Optional

from botocore.exceptions import ClientError

from cost_toolkit.common.aws_client_factory import create_ec2_client
from cost_toolkit.common.aws_common import find_resource_region as find_resource_region_canonical
from cost_toolkit.common.aws_common import (
    get_all_aws_regions,
    get_common_regions_extended,
    get_instance_name,
)


def get_all_regions(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> list[str]:
    """
    Get list of all available AWS regions from EC2 API.

    Raises:
        ClientError: If the AWS API call fails.
    """
    return get_all_aws_regions(aws_access_key_id, aws_secret_access_key)


def find_resource_region(
    resource_type: str,
    resource_id: str,
    regions: Optional[list[str]] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> Optional[str]:
    """Delegates to canonical implementation in aws_common."""
    return find_resource_region_canonical(
        resource_type, resource_id, regions, aws_access_key_id, aws_secret_access_key
    )


def get_common_regions() -> list[str]:
    """Get list of commonly used AWS regions for cost optimization."""
    return get_common_regions_extended()


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
    """Get detailed information about a single EC2 instance."""
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
    ec2_client=None,
) -> bool:
    """Delete an EBS snapshot."""
    try:
        client = ec2_client or create_ec2_client(
            region=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        if verbose:
            # Get snapshot info first
            response = client.describe_snapshots(SnapshotIds=[snapshot_id])
            snapshot = response["Snapshots"][0]
            size_gb = snapshot["VolumeSize"]
            description = snapshot.get("Description", "No description")  # Description is optional
            start_time = snapshot["StartTime"]

            print(f"🔍 Snapshot to delete: {snapshot_id}")
            print(f"   Size: {size_gb} GB")
            print(f"   Created: {start_time}")
            print(f"   Description: {description}")

        print(f"🗑️  Deleting snapshot: {snapshot_id} in {region}")
        client.delete_snapshot(SnapshotId=snapshot_id)
        print(f"   ✅ Successfully deleted {snapshot_id}")
    except ClientError as e:
        error_code = e.response["Error"].get("Code") if hasattr(e, "response") else None
        if error_code == "InvalidSnapshot.NotFound":
            print(f"   ℹ️  Snapshot {snapshot_id} not found in {region}")
            return False
        print(f"   ❌ Error deleting {snapshot_id}: {e}")
        return False
    return True


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
    return response["Addresses"]


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
    return response["NetworkInterfaces"]


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
    return response["SecurityGroups"]


def delete_security_group(
    region: str,
    group_id: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    group_name: Optional[str] = None,
    ec2_client=None,
) -> bool:
    """
    Delete a security group.

    Args:
        region: AWS region name
        group_id: Security group ID
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key
        group_name: Optional security group name for clearer logging
        ec2_client: Optional pre-configured EC2 client

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = ec2_client or create_ec2_client(
            region=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        target_label = f"{group_id} ({group_name})" if group_name else group_id
        print(f"   🗑️  Deleting security group: {target_label}")
        client.delete_security_group(GroupId=group_id)
        print(f"   ✅ Deleted security group: {target_label}")

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
    return response["Snapshots"]


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
    return response["Volumes"]


if __name__ == "__main__":  # pragma: no cover - script entry point
    pass
