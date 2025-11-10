#!/usr/bin/env python3
"""
AWS Failed Export AMI Cleanup Script
Cleans up AMIs that were created during failed S3 export attempts.
This script removes the temporary AMIs that were left behind when exports failed.
"""

import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")  # noqa: TRY003

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def cleanup_failed_export_amis():
    """Clean up AMIs created during failed export attempts"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    # AMIs created during the failed export attempt
    failed_amis = [
        {
            "ami_id": "ami-0fb32d09d4167dc8b",
            "region": "eu-west-2",
            "description": "snap-0f68820355c25e73e export AMI",
        },
        {
            "ami_id": "ami-0311aad3c728f520b",
            "region": "eu-west-2",
            "description": "snap-046b7eace8694913b export AMI",
        },
        {
            "ami_id": "ami-0fa8c0016d1e40180",
            "region": "us-east-2",
            "description": "snap-036eee4a7c291fd26 export AMI",
        },
    ]

    print("AWS Failed Export AMI Cleanup")
    print("=" * 40)
    print("Cleaning up AMIs created during failed S3 export attempts...")
    print()

    successful_cleanups = 0
    failed_cleanups = 0

    for ami_info in failed_amis:
        ami_id = ami_info["ami_id"]
        region = ami_info["region"]
        description = ami_info["description"]

        print(f"🔍 Processing {ami_id} in {region}...")
        print(f"   Description: {description}")

        # Create EC2 client for the specific region
        ec2_client = boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        try:
            # Check if AMI still exists
            response = ec2_client.describe_images(ImageIds=[ami_id])
            if not response["Images"]:
                print(f"   ℹ️  AMI {ami_id} no longer exists")
                continue

            # Deregister the AMI
            print(f"   🗑️  Deregistering AMI: {ami_id}")
            ec2_client.deregister_image(ImageId=ami_id)
            print(f"   ✅ Successfully cleaned up {ami_id}")
            successful_cleanups += 1

        except ClientError as e:
            print(f"   ❌ Error cleaning up {ami_id}: {e}")
            failed_cleanups += 1

        print()

    print("=" * 40)
    print("🎯 CLEANUP SUMMARY")
    print("=" * 40)
    print(f"✅ Successfully cleaned up: {successful_cleanups} AMIs")
    print(f"❌ Failed to clean up: {failed_cleanups} AMIs")

    if successful_cleanups > 0:
        print("🎉 Failed export AMI cleanup completed!")
        print("   Temporary AMIs have been removed.")


if __name__ == "__main__":
    try:
        cleanup_failed_export_amis()
    except ClientError as e:
        print(f"❌ Script failed: {e}")
        sys.exit(1)
