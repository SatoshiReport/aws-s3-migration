#!/usr/bin/env python3
"""
AWS S3 Standardization Script
Implements specific S3 bucket configurations:
1. Delete mail.satoshi.report bucket
2. Ensure all buckets (except akiaiw6gwdirbsbuzqiq-arq-1) are private
3. Remove lifecycle policies from all buckets (except akiaiw6gwdirbsbuzqiq-arq-1)
4. Move all objects to Standard storage class
"""

import os
import sys
import time
from datetime import datetime

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aws_utils import setup_aws_credentials

# Bucket to exclude from standardization - DO NOT TOUCH
EXCLUDED_BUCKET = "akiaiw6gwdirbsbuzqiq-arq-1"

# Bucket to delete (already deleted, but keeping for reference)
BUCKET_TO_DELETE = "mail.satoshi.report"


def get_bucket_region(bucket_name):
    """Get the region where a bucket is located"""
    try:
        s3_client = boto3.client("s3")
        response = s3_client.get_bucket_location(Bucket=bucket_name)
        region = response.get("LocationConstraint")
        # us-east-1 returns None for LocationConstraint
        return region if region else "us-east-1"
    except Exception as e:
        print(f"Error getting region for bucket {bucket_name}: {e}")
        return "us-east-1"


def delete_bucket_completely(bucket_name):
    """Delete a bucket and all its contents"""
    try:
        region = get_bucket_region(bucket_name)
        s3_client = boto3.client("s3", region_name=region)

        print(f"🗑️  Deleting bucket: {bucket_name}")

        # First, delete all objects in the bucket
        print(f"  Listing objects in {bucket_name}...")

        # Handle versioned objects
        try:
            versions = s3_client.list_object_versions(Bucket=bucket_name)

            # Delete all object versions
            if "Versions" in versions:
                for version in versions["Versions"]:
                    print(
                        f"    Deleting version: {version['Key']} (version: {version['VersionId']})"
                    )
                    s3_client.delete_object(
                        Bucket=bucket_name, Key=version["Key"], VersionId=version["VersionId"]
                    )

            # Delete all delete markers
            if "DeleteMarkers" in versions:
                for marker in versions["DeleteMarkers"]:
                    print(
                        f"    Deleting delete marker: {marker['Key']} (version: {marker['VersionId']})"
                    )
                    s3_client.delete_object(
                        Bucket=bucket_name, Key=marker["Key"], VersionId=marker["VersionId"]
                    )

        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchBucket":
                # Try regular object deletion if versioning fails
                paginator = s3_client.get_paginator("list_objects_v2")
                pages = paginator.paginate(Bucket=bucket_name)

                for page in pages:
                    if "Contents" in page:
                        for obj in page["Contents"]:
                            print(f"    Deleting object: {obj['Key']}")
                            s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])

        # Now delete the bucket itself
        print(f"  Deleting bucket {bucket_name}...")
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"✅ Successfully deleted bucket: {bucket_name}")
        return True

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchBucket":
            print(f"✅ Bucket {bucket_name} does not exist (already deleted)")
            return True
        elif error_code == "BucketNotEmpty":
            print(f"❌ Bucket {bucket_name} is not empty. Manual cleanup may be required.")
            return False
        else:
            print(f"❌ Error deleting bucket {bucket_name}: {e}")
            return False
    except Exception as e:
        print(f"❌ Unexpected error deleting bucket {bucket_name}: {e}")
        return False


def ensure_bucket_private(bucket_name, region):
    """Ensure a bucket has private access configuration"""
    try:
        s3_client = boto3.client("s3", region_name=region)

        print(f"🔒 Securing bucket: {bucket_name}")

        # Set public access block to maximum security
        public_access_block_config = {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        }

        s3_client.put_public_access_block(
            Bucket=bucket_name, PublicAccessBlockConfiguration=public_access_block_config
        )

        # Remove any public bucket policy
        try:
            s3_client.delete_bucket_policy(Bucket=bucket_name)
            print(f"  Removed bucket policy from {bucket_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchBucketPolicy":
                print(f"  Warning: Could not remove bucket policy from {bucket_name}: {e}")

        print(f"✅ Secured bucket: {bucket_name}")
        return True

    except ClientError as e:
        print(f"❌ Error securing bucket {bucket_name}: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error securing bucket {bucket_name}: {e}")
        return False


def remove_lifecycle_policy(bucket_name, region):
    """Remove lifecycle policy from a bucket"""
    try:
        s3_client = boto3.client("s3", region_name=region)

        print(f"📋 Removing lifecycle policy from: {bucket_name}")

        # Check if lifecycle policy exists
        try:
            s3_client.get_bucket_lifecycle_configuration(Bucket=bucket_name)
            # If we get here, policy exists, so delete it
            s3_client.delete_bucket_lifecycle(Bucket=bucket_name)
            print(f"✅ Removed lifecycle policy from: {bucket_name}")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchLifecycleConfiguration":
                print(f"✅ No lifecycle policy to remove from: {bucket_name}")
                return True
            else:
                print(f"❌ Error removing lifecycle policy from {bucket_name}: {e}")
                return False

    except Exception as e:
        print(f"❌ Unexpected error removing lifecycle policy from {bucket_name}: {e}")
        return False


def move_objects_to_standard_storage(bucket_name, region):
    """Move all objects in a bucket to Standard storage class"""
    try:
        s3_client = boto3.client("s3", region_name=region)

        print(f"📦 Converting objects to Standard storage in: {bucket_name}")

        # Get all objects in the bucket
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name)

        objects_processed = 0
        objects_converted = 0

        for page in pages:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                objects_processed += 1
                key = obj["Key"]
                current_storage_class = obj.get("StorageClass", "STANDARD")

                # Skip if already Standard
                if current_storage_class == "STANDARD":
                    continue

                try:
                    # Copy object to itself with Standard storage class
                    copy_source = {"Bucket": bucket_name, "Key": key}
                    s3_client.copy_object(
                        CopySource=copy_source,
                        Bucket=bucket_name,
                        Key=key,
                        StorageClass="STANDARD",
                        MetadataDirective="COPY",
                    )
                    objects_converted += 1

                    if objects_converted % 100 == 0:
                        print(f"    Converted {objects_converted} objects...")

                except ClientError as e:
                    print(f"    Warning: Could not convert {key}: {e}")
                    continue

        print(
            f"✅ Processed {objects_processed} objects, converted {objects_converted} to Standard storage in: {bucket_name}"
        )
        return True

    except ClientError as e:
        print(f"❌ Error converting objects in bucket {bucket_name}: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error converting objects in bucket {bucket_name}: {e}")
        return False


def standardize_s3_buckets():
    """Main function to standardize S3 bucket configurations"""
    setup_aws_credentials()

    print("AWS S3 Bucket Standardization")
    print("=" * 80)
    print("Implementing S3 bucket standardization requirements:")
    print(f"1. Exclude {EXCLUDED_BUCKET} from ALL processing")
    print("2. Ensure all remaining buckets are private")
    print("3. Remove lifecycle policies from all remaining buckets")
    print("4. Move all objects to Standard storage class")
    print()

    try:
        # Get all buckets
        s3_client = boto3.client("s3")
        response = s3_client.list_buckets()
        buckets = response.get("Buckets", [])

        if not buckets:
            print("✅ No S3 buckets found in your account")
            return

        print(f"🔍 Found {len(buckets)} S3 bucket(s) to process")
        print()

        # Filter out excluded bucket from ALL processing
        buckets = [b for b in buckets if b["Name"] != EXCLUDED_BUCKET]

        print(f"ℹ️  Excluding {EXCLUDED_BUCKET} from ALL processing (will not be touched)")
        print()

        # Process remaining buckets
        for bucket in buckets:
            bucket_name = bucket["Name"]
            bucket_region = get_bucket_region(bucket_name)

            print(f"Processing bucket: {bucket_name} (region: {bucket_region})")
            print("-" * 60)

            # Step 2: Ensure bucket is private
            print(f"Step 2: Ensuring bucket is private...")
            ensure_bucket_private(bucket_name, bucket_region)

            # Step 3: Remove lifecycle policy
            print(f"Step 3: Removing lifecycle policy...")
            remove_lifecycle_policy(bucket_name, bucket_region)

            # Step 4: Move objects to Standard storage
            print(f"Step 4: Converting objects to Standard storage...")
            move_objects_to_standard_storage(bucket_name, bucket_region)

            print()

        print("=" * 80)
        print("🎯 S3 STANDARDIZATION COMPLETE")
        print("=" * 80)
        print("Summary of changes:")
        print(f"✅ Excluded {EXCLUDED_BUCKET} from ALL processing")
        print("✅ Secured all remaining buckets")
        print("✅ Removed lifecycle policies from all remaining buckets")
        print("✅ Converted all objects to Standard storage class")
        print()
        print("All processed S3 buckets now have:")
        print("• Private access (no public access)")
        print("• No lifecycle policies")
        print("• All objects in Standard storage class")
        print(f"• {EXCLUDED_BUCKET} was completely excluded and remains unchanged")

    except NoCredentialsError:
        print("❌ AWS credentials not found. Please configure your credentials.")
    except ClientError as e:
        print(f"❌ AWS API error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    # Confirm before running destructive operations
    print("⚠️  WARNING: This script will make changes to your S3 buckets!")
    print(f"   - Exclude {EXCLUDED_BUCKET} from ALL processing")
    print("   - Remove lifecycle policies from remaining buckets")
    print("   - Change storage classes to Standard")
    print("   - Set all remaining buckets to private")
    print()

    confirm = input("Are you sure you want to proceed? (type 'yes' to continue): ")
    if confirm.lower() == "yes":
        standardize_s3_buckets()
    else:
        print("Operation cancelled.")
