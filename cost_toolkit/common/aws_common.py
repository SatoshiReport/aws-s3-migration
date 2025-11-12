"""
Shared AWS client creation utilities.

This module provides common AWS client initialization patterns
to eliminate duplicate client creation code across scripts.
"""

import boto3
from botocore.exceptions import ClientError


def create_ec2_client(region, aws_access_key_id, aws_secret_access_key):
    """
    Create an EC2 boto3 client with the provided credentials.

    Args:
        region: AWS region name
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key

    Returns:
        boto3.client: Configured EC2 client
    """
    return boto3.client(
        "ec2",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def create_s3_client(region, aws_access_key_id, aws_secret_access_key):
    """
    Create an S3 boto3 client with the provided credentials.

    Args:
        region: AWS region name
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key

    Returns:
        boto3.client: Configured S3 client
    """
    return boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


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
    ec2_client = create_ec2_client(region, aws_access_key_id, aws_secret_access_key)
    s3_client = create_s3_client(region, aws_access_key_id, aws_secret_access_key)
    return ec2_client, s3_client


def terminate_instance(region_name, instance_id, aws_access_key_id, aws_secret_access_key):
    """
    Terminate an EC2 instance and return state information.

    Args:
        region_name: AWS region name
        instance_id: EC2 instance ID to terminate
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key

    Returns:
        dict: Response from terminate_instances API call

    Raises:
        Exception: If termination fails
    """
    ec2 = create_ec2_client(region_name, aws_access_key_id, aws_secret_access_key)

    print(f"🗑️  Terminating instance: {instance_id}")
    response = ec2.terminate_instances(InstanceIds=[instance_id])

    current_state = response["TerminatingInstances"][0]["CurrentState"]["Name"]
    previous_state = response["TerminatingInstances"][0]["PreviousState"]["Name"]

    print(f"   Previous state: {previous_state}")
    print(f"   Current state: {current_state}")

    return response


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


def get_default_regions():
    """
    Get the default list of AWS regions commonly used for operations.

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
