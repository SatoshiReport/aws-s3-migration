"""
Shared S3 utilities to reduce code duplication.

Common S3 operations used across multiple scripts.
"""

from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_s3_operations import get_bucket_location


def get_bucket_region(bucket_name, verbose=False, location_getter=None):
    """
    Get the region where an S3 bucket is located.

    Canonical wrapper that delegates to get_bucket_location() from aws_s3_operations.py.
    Provides consistent error handling across all scripts.

    Args:
        bucket_name: Name of the S3 bucket
        verbose: If True, print region information

    Returns:
        str: AWS region name, defaults to "us-east-1" on error
    """
    resolver = location_getter or get_bucket_location

    try:
        region = resolver(bucket_name)
    except ClientError as e:
        error_msg = f"Unable to determine region for {bucket_name}: {str(e)}"
        if verbose:
            print(f"    Region: {error_msg}")
        return "us-east-1"

    if verbose:
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
        s3_client.create_bucket(
            Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region}
        )
    print(f"   ✅ Created S3 bucket: {bucket_name}")
