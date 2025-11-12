"""
Shared S3 utilities to reduce code duplication.

Common S3 operations used across multiple scripts.
"""


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
