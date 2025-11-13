#!/usr/bin/env python3
"""
AWS VPC Unused Resources Cleanup Script
Cleans up unused VPC resources identified in the comprehensive audit:
- Unused security groups (10 found)
- Empty VPCs with no instances (2 found)

This cleanup improves security hygiene and reduces clutter.
"""

import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Unused security groups identified in the audit
UNUSED_SECURITY_GROUPS = [
    # us-east-1 region
    {
        "group_id": "sg-0423403672ae41d94",
        "name": "security-group-for-outbound-nfs-d-jbqwgqwiy4d",
        "region": "us-east-1",
        "vpc_id": "vpc-da2cc8bf",
    },
    {
        "group_id": "sg-0bf8a0d06a121f4a0",
        "name": "rds-ec2-1",
        "region": "us-east-1",
        "vpc_id": "vpc-da2cc8bf",
    },
    {
        "group_id": "sg-049977ce080d9ab0",
        "name": "security-group-for-inbound-nfs-d-ujcvqjdoyu70",
        "region": "us-east-1",
        "vpc_id": "vpc-da2cc8bf",
    },
    {
        "group_id": "sg-0ac5aa3acaca47fde",
        "name": "launch-wizard-1",
        "region": "us-east-1",
        "vpc_id": "vpc-da2cc8bf",
    },
    {
        "group_id": "sg-044777fbbcdee8f28",
        "name": "ec2-rds-1",
        "region": "us-east-1",
        "vpc_id": "vpc-da2cc8bf",
    },
    {
        "group_id": "sg-0dfa7bedc21d91798",
        "name": "security-group-for-inbound-nfs-d-jbqwgqwiy4d",
        "region": "us-east-1",
        "vpc_id": "vpc-da2cc8bf",
    },
    {
        "group_id": "sg-0b2079934eb55f513",
        "name": "launch-wizard-4",
        "region": "us-east-1",
        "vpc_id": "vpc-da2cc8bf",
    },
    {
        "group_id": "sg-05ec40d14e0fb6fed",
        "name": "security-group-for-outbound-nfs-d-ujcvqjdoyu70",
        "region": "us-east-1",
        "vpc_id": "vpc-da2cc8bf",
    },
    # us-east-2 region
    {
        "group_id": "sg-09e291dc61da97af1",
        "name": "security-group-for-outbound-nfs-d-ki8zr9k0yt95",
        "region": "us-east-2",
        "vpc_id": "vpc-c93f9ea0",
    },
    {
        "group_id": "sg-0dba11de0f5b92f40",
        "name": "security-group-for-inbound-nfs-d-ki8zr9k0yt95",
        "region": "us-east-2",
        "vpc_id": "vpc-c93f9ea0",
    },
]

# Empty VPCs that could potentially be removed (but we'll be cautious)
EMPTY_VPCS = [
    {
        "vpc_id": "vpc-56008731",
        "name": "Non-default VPC",
        "region": "us-east-1",
        "is_default": False,
    },
    {
        "vpc_id": "vpc-0de5c0820b60ba40",
        "name": "Unnamed",
        "region": "us-west-2",
        "is_default": False,
    },
]


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")  # noqa: TRY003

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def delete_security_group(ec2_client, group_id, group_name, _region):
    """Delete a specific security group"""
    try:
        print(f"   🗑️  Deleting security group: {group_id} ({group_name})")
        ec2_client.delete_security_group(GroupId=group_id)
        print(f"   ✅ Successfully deleted {group_id}")
    except ClientError as e:
        print(f"   ❌ Error deleting {group_id}: {e}")
        return False

    return True


def print_cleanup_intro():
    """Print introduction and warning messages for the cleanup operation"""
    print("AWS VPC Unused Resources Cleanup")
    print("=" * 50)
    print("Cleaning up unused VPC resources for better security hygiene...")
    print()
    print(f"🎯 Target: {len(UNUSED_SECURITY_GROUPS)} unused security groups")
    print(f"🏠 Review: {len(EMPTY_VPCS)} empty VPCs")
    print()

    print("⚠️  IMPORTANT NOTES:")
    print("   - Unused security groups will be permanently deleted")
    print("   - Empty VPCs will be reviewed but not automatically deleted")
    print("   - This cleanup improves security hygiene")
    print("   - No cost savings but reduces clutter and security risks")
    print()


def clean_security_groups(aws_access_key_id, aws_secret_access_key):
    """Clean up unused security groups and return success/failure counts"""
    print("🔶 Cleaning up unused security groups...")
    print()

    successful_deletions = 0
    failed_deletions = 0

    for sg_info in UNUSED_SECURITY_GROUPS:
        group_id = sg_info["group_id"]
        group_name = sg_info["name"]
        region = sg_info["region"]
        vpc_id = sg_info["vpc_id"]

        print(f"🔍 Processing {group_id} in {region}...")
        print(f"   Name: {group_name}")
        print(f"   VPC: {vpc_id}")

        ec2_client = boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        if delete_security_group(ec2_client, group_id, group_name, region):
            successful_deletions += 1
        else:
            failed_deletions += 1

        print()

    return successful_deletions, failed_deletions


def review_empty_vpcs():
    """Review empty VPCs and provide manual deletion commands"""
    print("🏠 Reviewing empty VPCs...")
    print()

    for vpc_info in EMPTY_VPCS:
        vpc_id = vpc_info["vpc_id"]
        vpc_name = vpc_info["name"]
        region = vpc_info["region"]
        is_default = vpc_info["is_default"]

        print(f"🔍 Empty VPC found: {vpc_id} ({vpc_name}) in {region}")
        print(f"   Default VPC: {is_default}")
        print("   Status: Empty (no instances)")

        if not is_default:
            print("   💡 Consider: This non-default VPC could be deleted if no longer needed")
            print(f"   🔧 Manual command: aws ec2 delete-vpc --vpc-id {vpc_id} --region {region}")
        else:
            print("   ⚠️  Default VPC: Keep for potential future use")

        print()


def print_cleanup_summary(successful_deletions, failed_deletions):
    """Print summary of cleanup results and next steps"""
    print("=" * 50)
    print("🎯 VPC CLEANUP SUMMARY")
    print("=" * 50)
    print(f"✅ Successfully deleted: {successful_deletions} security groups")
    print(f"❌ Failed to delete: {failed_deletions} security groups")
    print(f"🏠 Empty VPCs reviewed: {len(EMPTY_VPCS)}")
    print()

    if successful_deletions > 0:
        print("🎉 VPC cleanup completed successfully!")
        print("   Your AWS account now has better security hygiene.")
        print("   Unused security groups have been removed.")
        print()
        print("📝 Benefits:")
        print("   • Reduced security group clutter")
        print("   • Improved security posture")
        print("   • Cleaner AWS console experience")
        print("   • Easier compliance auditing")

    if len(EMPTY_VPCS) > 0:
        print()
        print("💡 Next Steps for Empty VPCs:")
        print("   • Review if the empty VPCs are still needed")
        print("   • Non-default VPCs can be safely deleted if unused")
        print("   • Default VPCs are typically kept for convenience")


def cleanup_unused_vpc_resources():
    """Clean up unused VPC resources identified in the audit"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    print_cleanup_intro()

    confirmation = input("Type 'CLEANUP VPC RESOURCES' to proceed: ")

    if confirmation != "CLEANUP VPC RESOURCES":
        print("❌ Operation cancelled by user")
        return

    print()
    print("🚨 Proceeding with VPC resource cleanup...")
    print("=" * 50)

    successful_deletions, failed_deletions = clean_security_groups(
        aws_access_key_id, aws_secret_access_key
    )

    review_empty_vpcs()

    print_cleanup_summary(successful_deletions, failed_deletions)


def main():
    """Main function."""
    try:
        cleanup_unused_vpc_resources()
    except ClientError as e:
        print(f"❌ Script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
