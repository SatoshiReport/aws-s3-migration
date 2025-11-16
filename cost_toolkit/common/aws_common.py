"""
Shared AWS client creation utilities.

This module provides common AWS client initialization patterns
to eliminate duplicate client creation code across scripts.
"""

from typing import Optional

import boto3
from botocore.exceptions import ClientError


def create_ec2_and_s3_clients(region, aws_access_key_id, aws_secret_access_key):
    """
    Create both EC2 and S3 boto3 clients with the provided credentials.

    Args:
        region: AWS region name
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key

    Returns:
        tuple: (ec2_client, s3_client)
    """
    ec2_client = boto3.client(
        "ec2",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    s3_client = boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    return ec2_client, s3_client


def get_instance_name(ec2_client, instance_id):
    """
    Get the Name tag of an EC2 instance.

    Args:
        ec2_client: Boto3 EC2 client instance
        instance_id: EC2 instance ID

    Returns:
        str: Instance name from Name tag, or "Unknown" if not found or on error
    """
    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                for tag in instance.get("Tags", []):
                    if tag["Key"] == "Name":
                        return tag["Value"]
    except ClientError:
        return "Unknown"
    return "Unknown"


def get_all_aws_regions():
    """
    Get all available AWS regions by querying the EC2 service.
    Delegates to canonical implementation with error handling.

    Returns:
        list: List of all AWS region names

    Note:
        This makes an API call to AWS. For a static list of common regions,
        use get_default_regions() instead.
    """
    from cost_toolkit.scripts.aws_ec2_operations import get_all_regions

    return get_all_regions()


def get_default_regions():
    """
    Get the default list of AWS regions commonly used for operations.

    Returns:
        list: List of AWS region names

    Note:
        This returns a static list. For all regions via API call,
        use get_all_aws_regions() instead.
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


def extract_tag_value(resource, key, default="Unnamed"):
    """
    Extract a specific tag value from an AWS resource.

    Args:
        resource: AWS resource dict containing 'Tags' key
        key: Tag key to search for
        default: Default value if tag not found (default: "Unnamed")

    Returns:
        str: Tag value if found, otherwise default value
    """
    for tag in resource.get("Tags", []):
        if tag["Key"] == key:
            return tag["Value"]
    return default


def get_resource_tags(resource):
    """
    Extract all tags from an AWS resource as a dictionary.

    Args:
        resource: AWS resource dict containing 'Tags' key

    Returns:
        dict: Dictionary of tag key-value pairs
    """
    return {tag["Key"]: tag["Value"] for tag in resource.get("Tags", [])}


def extract_volumes_from_instance(instance):
    """
    Extract volume information from an EC2 instance.

    Args:
        instance: EC2 instance dict from describe_instances

    Returns:
        list: List of dicts with volume_id, device, and delete_on_termination
    """
    volumes = []
    for bdm in instance.get("BlockDeviceMappings", []):
        if "Ebs" in bdm:
            volumes.append(
                {
                    "volume_id": bdm["Ebs"]["VolumeId"],
                    "device": bdm["DeviceName"],
                    "delete_on_termination": bdm["Ebs"]["DeleteOnTermination"],
                }
            )
    return volumes


def get_instance_details(ec2_client, instance_id):
    """
    Get detailed information about an EC2 instance.

    Args:
        ec2_client: Boto3 EC2 client
        instance_id: The EC2 instance ID

    Returns:
        dict: Instance details or None on error. Contains keys:
            - instance_id: Instance ID
            - name: Instance name from Name tag
            - state: Current instance state
            - instance_type: Instance type
            - launch_time: Launch timestamp
            - availability_zone: AZ where instance is running
            - volumes: List of attached volumes
            - tags: Dict of all instance tags
    """
    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])

        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                return {
                    "instance_id": instance_id,
                    "name": extract_tag_value(instance, "Name"),
                    "state": instance["State"]["Name"],
                    "instance_type": instance["InstanceType"],
                    "launch_time": instance["LaunchTime"],
                    "availability_zone": instance["Placement"]["AvailabilityZone"],
                    "volumes": extract_volumes_from_instance(instance),
                    "tags": get_resource_tags(instance),
                }

    except ClientError as e:
        print(f"Error getting instance details for {instance_id}: {e}")
        return None
    return None


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
    """
    from cost_toolkit.scripts.aws_client_factory import create_ec2_client
    from cost_toolkit.scripts.aws_ec2_operations import get_all_regions

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
