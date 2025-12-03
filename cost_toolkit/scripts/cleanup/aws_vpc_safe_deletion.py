#!/usr/bin/env python3
"""Safely delete VPC and related resources."""

from threading import Event

import boto3
from botocore.exceptions import ClientError

from cost_toolkit.common import vpc_cleanup_utils

WAIT_EVENT = Event()


def delete_vpc_and_dependencies(vpc_id, region_name):
    """Create an EC2 client and delegate deletion to the shared implementation."""
    try:
        ec2_client = boto3.client("ec2", region_name=region_name)
    except ClientError as exc:
        print(f"❌ Error during VPC deletion process: {exc}")
        return False

    return vpc_cleanup_utils.delete_vpc_and_dependencies(
        vpc_id, region_name=region_name, ec2_client=ec2_client
    )


def delete_vpc_and_dependencies_with_logging(vpc_id, region_name):
    """
    Delete a VPC and all its dependencies using shared utilities.

    Args:
        vpc_id: VPC ID to delete
        region_name: AWS region name

    Returns:
        bool: True if deletion succeeded, False otherwise
    """
    print(f"\n🗑️  Deleting VPC {vpc_id} in {region_name}")
    try:
        result = delete_vpc_and_dependencies(vpc_id, region_name=region_name)
    except ClientError as e:
        print(f"❌ Error during VPC deletion process: {e}")
        return False
    return bool(result)


def get_safe_vpcs():
    """Return list of VPCs safe to delete."""
    return [
        ("vpc-05df0c91efb98a80a", "us-east-1"),
        ("vpc-56008731", "us-east-1"),
        ("vpc-013655b59190e0c16", "us-east-1"),
        ("vpc-0de5c0820b60ba40", "us-west-2"),
    ]


def delete_vpcs(safe_vpcs):
    """Delete all VPCs and return results."""
    deletion_results = []

    for vpc_id, region in safe_vpcs:
        print("\n" + "=" * 80)
        print(f"DELETING VPC {vpc_id} in {region}")
        print("=" * 80)

        success = delete_vpc_and_dependencies_with_logging(vpc_id, region)
        deletion_results.append((vpc_id, region, success))

        if success:
            print(f"✅ VPC {vpc_id} deletion completed successfully")
        else:
            print(f"❌ VPC {vpc_id} deletion failed")

        WAIT_EVENT.wait(2)

    return deletion_results


def print_vpc_deletion_summary(deletion_results):
    """Print VPC deletion summary."""
    print("\n" + "=" * 80)
    print("🎯 DELETION SUMMARY")
    print("=" * 80)

    successful_deletions = [result for result in deletion_results if result[2]]
    failed_deletions = [result for result in deletion_results if not result[2]]

    print(f"✅ Successfully deleted VPCs: {len(successful_deletions)}")
    for vpc_id, region, _ in successful_deletions:
        print(f"  {vpc_id} ({region})")

    if failed_deletions:
        print(f"\n❌ Failed to delete VPCs: {len(failed_deletions)}")
        for vpc_id, region, _ in failed_deletions:
            print(f"  {vpc_id} ({region})")

    print("\n💰 COST IMPACT:")
    if successful_deletions:
        print(f"  Deleted {len(successful_deletions)} unused VPCs and their resources")
        print("  This should reduce infrastructure complexity")
        print("  Main cost savings will come from removing the public IP ($3.60/month)")


def main():
    """Delete specified VPC and all associated resources."""
    print("AWS VPC Safe Deletion")
    print("=" * 80)
    print("Deleting VPCs that have no blocking resources...")

    safe_vpcs = get_safe_vpcs()
    deletion_results = delete_vpcs(safe_vpcs)
    print_vpc_deletion_summary(deletion_results)

    print("\n📋 REMAINING TASKS:")
    print("  1. Remove public IP from instance i-00c39b1ba0eba3e2d (requires stop/start)")
    print("  2. Consider if remaining VPCs with resources are still needed")
    print("  3. Monitor billing to confirm cost reduction")


if __name__ == "__main__":
    main()
