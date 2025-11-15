"""
Bucket analysis functions for S3 audit.
Handles bucket metadata collection and object analysis.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_s3_operations import get_bucket_location


def get_bucket_region(bucket_name):
    """Get the region where a bucket is located"""
    try:
        return get_bucket_location(bucket_name)
    except ClientError as e:
        print(f"Error getting region for bucket {bucket_name}: {e}")
        return "us-east-1"


def _get_bucket_metadata(s3_client, bucket_name, bucket_analysis):
    """Collect bucket-level metadata like versioning, lifecycle, encryption, and public access"""
    # Check bucket versioning
    try:
        versioning_response = s3_client.get_bucket_versioning(Bucket=bucket_name)
        bucket_analysis["versioning_enabled"] = versioning_response.get("Status") == "Enabled"
    except ClientError:
        pass

    # Check lifecycle policy
    try:
        lifecycle_response = s3_client.get_bucket_lifecycle_configuration(Bucket=bucket_name)
        bucket_analysis["lifecycle_policy"] = lifecycle_response.get("Rules", [])
    except ClientError:
        bucket_analysis["lifecycle_policy"] = []

    # Check encryption
    try:
        encryption_response = s3_client.get_bucket_encryption(Bucket=bucket_name)
        bucket_analysis["encryption"] = encryption_response.get("ServerSideEncryptionConfiguration")
    except ClientError:
        pass

    # Check public access
    try:
        public_access_response = s3_client.get_public_access_block(Bucket=bucket_name)
        pab = public_access_response.get("PublicAccessBlockConfiguration", {})
        # If any of these are False, bucket might have public access
        bucket_analysis["public_access"] = not all(
            [
                pab.get("BlockPublicAcls", True),
                pab.get("IgnorePublicAcls", True),
                pab.get("BlockPublicPolicy", True),
                pab.get("RestrictPublicBuckets", True),
            ]
        )
    except ClientError:
        # If we can't get public access block, assume it might be public
        bucket_analysis["public_access"] = True


def _process_object(obj, bucket_analysis, ninety_days_ago, large_object_threshold):
    """Process a single S3 object and update bucket analysis data"""
    bucket_analysis["total_objects"] += 1
    size = obj["Size"]
    bucket_analysis["total_size_bytes"] += size

    # Determine storage class (default to STANDARD if not specified)
    storage_class = obj.get("StorageClass", "STANDARD")
    bucket_analysis["storage_classes"][storage_class]["count"] += 1
    bucket_analysis["storage_classes"][storage_class]["size_bytes"] += size

    # Track oldest and newest objects
    last_modified = obj["LastModified"]
    if (
        not bucket_analysis["last_modified_oldest"]
        or last_modified < bucket_analysis["last_modified_oldest"]
    ):
        bucket_analysis["last_modified_oldest"] = last_modified
    if (
        not bucket_analysis["last_modified_newest"]
        or last_modified > bucket_analysis["last_modified_newest"]
    ):
        bucket_analysis["last_modified_newest"] = last_modified

    # Track large objects (potential for optimization)
    if size > large_object_threshold:
        bucket_analysis["large_objects"].append(
            {
                "key": obj["Key"],
                "size_bytes": size,
                "storage_class": storage_class,
                "last_modified": last_modified,
            }
        )

    # Track old objects (potential for archival)
    if last_modified < ninety_days_ago:
        bucket_analysis["old_objects"].append(
            {
                "key": obj["Key"],
                "size_bytes": size,
                "storage_class": storage_class,
                "last_modified": last_modified,
                "age_days": (datetime.now(timezone.utc) - last_modified).days,
            }
        )


def analyze_bucket_objects(bucket_name, region):
    """Analyze all objects in a bucket for storage classes, sizes, and counts"""
    try:
        s3_client = boto3.client("s3", region_name=region)

        bucket_analysis = {
            "bucket_name": bucket_name,
            "region": region,
            "total_objects": 0,
            "total_size_bytes": 0,
            "storage_classes": defaultdict(lambda: {"count": 0, "size_bytes": 0}),
            "last_modified_oldest": None,
            "last_modified_newest": None,
            "large_objects": [],  # Objects > 100MB
            "old_objects": [],  # Objects > 90 days old
            "versioning_enabled": False,
            "lifecycle_policy": None,
            "encryption": None,
            "public_access": False,
        }

        _get_bucket_metadata(s3_client, bucket_name, bucket_analysis)

        # Paginate through all objects
        paginator = s3_client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=bucket_name)

        ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
        large_object_threshold = 100 * 1024 * 1024  # 100MB in bytes

        for page in page_iterator:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                _process_object(obj, bucket_analysis, ninety_days_ago, large_object_threshold)

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchBucket":
            print(f"⚠️  Bucket {bucket_name} does not exist")
        elif error_code == "AccessDenied":
            print(f"⚠️  Access denied to bucket {bucket_name}")
        else:
            print(f"⚠️  Error analyzing bucket {bucket_name}: {e}")
        return None

    return bucket_analysis


if __name__ == "__main__":
    pass
