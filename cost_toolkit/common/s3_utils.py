"""
Shared S3 utilities to reduce code duplication.

Common S3 operations used across multiple scripts.
"""

import logging

from cost_toolkit.scripts import aws_s3_operations


def get_bucket_location(bucket_name: str, aws_access_key_id: str | None = None, aws_secret_access_key: str | None = None):
    """Proxy to the shared get_bucket_location for easier patching."""
    if aws_access_key_id is None and aws_secret_access_key is None:
        return aws_s3_operations.get_bucket_location(bucket_name)

    return aws_s3_operations.get_bucket_location(
        bucket_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def get_bucket_region(bucket_name, verbose=True, location_getter=None):
    """
    Get the region where an S3 bucket is located.

    Canonical wrapper that delegates to get_bucket_location() from aws_s3_operations.py.

    Args:
        bucket_name: Name of the S3 bucket
        verbose: If True, print region information
        location_getter: Optional function to get bucket location (for testing)

    Returns:
        str: AWS region name

    Raises:
        ValueError: If bucket_name is None or empty
        ClientError: If bucket not found or API call fails
    """
    if not bucket_name:
        raise ValueError("bucket_name is required")

    resolver = location_getter or get_bucket_location

    region = resolver(bucket_name)

    if verbose:
        logging.info("    Region: %s", region)
        print(f"    Region: {region}")
    return region


def create_s3_bucket_with_region(s3_client, bucket_name, region):
    """
    Create S3 bucket with proper region configuration.

    Args:
        s3_client: Boto3 S3 client
        bucket_name: Name of the bucket to create
        region: AWS region name

    Note:
        us-east-1 requires different API call than other regions
    """
    if region == "us-east-1":
        s3_client.create_bucket(Bucket=bucket_name)
    else:
        s3_client.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region})
    logging.info("   ✅ Created S3 bucket: %s", bucket_name)
