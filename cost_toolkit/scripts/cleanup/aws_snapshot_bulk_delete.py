#!/usr/bin/env python3
"""
AWS Snapshot Bulk Deletion Script
Deletes multiple EBS snapshots across regions.
"""

import os
import sys
from datetime import datetime, timezone

import boto3

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aws_utils import setup_aws_credentials


def find_snapshot_region(snapshot_id):
    """
    Find which region contains the specified snapshot.

    Args:
        snapshot_id: The EBS snapshot ID to locate

    Returns:
        Region name if found, None otherwise
    """
    # Common regions to check
    regions = ["eu-west-2", "us-east-1", "us-east-2", "us-west-1", "us-west-2"]

    for region in regions:
        try:
            ec2_client = boto3.client("ec2", region_name=region)
            response = ec2_client.describe_snapshots(SnapshotIds=[snapshot_id])
            if response["Snapshots"]:
                return region
        except ec2_client.exceptions.ClientError as e:
            if "InvalidSnapshot.NotFound" in str(e):
                continue
            # For other errors, print but continue
            print(f"⚠️  Error checking {region} for {snapshot_id}: {str(e)}")
            continue

    return None


def get_snapshot_details(snapshot_id, region):
    """
    Get detailed information about a snapshot.

    Args:
        snapshot_id: The EBS snapshot ID
        region: AWS region where the snapshot is located

    Returns:
        Dictionary containing snapshot information
    """
    try:
        ec2_client = boto3.client("ec2", region_name=region)
        response = ec2_client.describe_snapshots(SnapshotIds=[snapshot_id])

        if response["Snapshots"]:
            snapshot = response["Snapshots"][0]
            return {
                "snapshot_id": snapshot_id,
                "region": region,
                "size_gb": snapshot.get("VolumeSize", 0),
                "state": snapshot["State"],
                "start_time": snapshot["StartTime"],
                "description": snapshot.get("Description", "No description"),
                "encrypted": snapshot.get("Encrypted", False),
            }
    except Exception as e:
        print(f"❌ Error getting details for {snapshot_id}: {str(e)}")
        return None


def delete_snapshot_safely(snapshot_id, region):
    """
    Safely delete an EBS snapshot with proper checks.

    Args:
        snapshot_id: The EBS snapshot ID to delete
        region: AWS region where the snapshot is located

    Returns:
        True if successful, False otherwise
    """
    try:
        ec2_client = boto3.client("ec2", region_name=region)

        # Get snapshot details first
        snapshot_info = get_snapshot_details(snapshot_id, region)
        if not snapshot_info:
            return False

        print(f"🗑️  Deleting snapshot: {snapshot_id}")
        print(f"   Region: {region}")
        print(f"   Size: {snapshot_info['size_gb']} GB")
        print(f"   Created: {snapshot_info['start_time']}")
        print(f"   Description: {snapshot_info['description'][:80]}...")

        # Calculate cost savings
        monthly_savings = snapshot_info["size_gb"] * 0.05  # $0.05 per GB/month

        # Delete the snapshot
        ec2_client.delete_snapshot(SnapshotId=snapshot_id)

        print(f"   ✅ Successfully deleted")
        print(f"   💰 Monthly savings: ${monthly_savings:.2f}")
        print()

        return True

    except Exception as e:
        print(f"   ❌ Error deleting snapshot {snapshot_id}: {str(e)}")
        print()
        return False


def main():
    """Main function to delete specified snapshots."""
    setup_aws_credentials()

    print("AWS Snapshot Bulk Deletion Script")
    print("=" * 80)
    print("Deleting specified EBS snapshots...")
    print()

    # List of snapshots to delete (from user request)
    snapshots_to_delete = [
        "snap-03490193a42293c87",  # 1024 GB - snapshot 2
        "snap-09e90c64db692f884",  # 1024 GB - CreateImage
        "snap-0e4a9793f5a9ac3fb",  # 1024 GB - Final Large Sized Snapshot
        "snap-07c0d4017e24b3240",  # 32 GB - SadTalker
        "snap-0fbb003580d3dc8ba",  # 64 GB - SadTalker
        "snap-04ced16a925e3f820",  # 8 GB - mufasa snapshot
        "snap-024d718f6d670bff2",  # 8 GB - CreateImage
        "snap-0ac8b88270ff68d4d",  # 8 GB - CreateImage
        "snap-036eee4a7c291fd26",  # 8 GB - Copied
        "snap-0700cdc4cdfaaf8fd",  # 8 GB - Copied
        "snap-05a42843f18ba1c5e",  # 8 GB - Copied mufasa snapshot
        "snap-0c81e260dcafb8968",  # 8 GB - Snapshot of Unnamed (mufasa backup)
    ]

    print(f"🎯 Target: {len(snapshots_to_delete)} snapshots for deletion")
    print()

    # Safety confirmation
    print("⚠️  FINAL WARNING: This will permanently delete these snapshots!")
    print("   - All snapshot data will be lost")
    print("   - This action cannot be undone")
    print("   - You will lose the ability to restore from these snapshots")
    print()

    confirmation = input("Type 'DELETE ALL SNAPSHOTS' to confirm bulk deletion: ")
    if confirmation != "DELETE ALL SNAPSHOTS":
        print("❌ Deletion cancelled")
        return

    print()
    print("🚨 Proceeding with bulk snapshot deletion...")
    print("=" * 80)

    # Process each snapshot
    successful_deletions = 0
    failed_deletions = 0
    total_savings = 0

    for snapshot_id in snapshots_to_delete:
        print(f"🔍 Processing {snapshot_id}...")

        # Find which region the snapshot is in
        region = find_snapshot_region(snapshot_id)

        if not region:
            print(f"   ❌ Snapshot {snapshot_id} not found in any region")
            failed_deletions += 1
            print()
            continue

        # Get snapshot details for cost calculation
        snapshot_info = get_snapshot_details(snapshot_id, region)
        if snapshot_info:
            monthly_savings = snapshot_info["size_gb"] * 0.05
            total_savings += monthly_savings

        # Delete the snapshot
        if delete_snapshot_safely(snapshot_id, region):
            successful_deletions += 1
        else:
            failed_deletions += 1

    # Summary
    print("=" * 80)
    print("🎯 BULK DELETION SUMMARY")
    print("=" * 80)

    print(f"✅ Successfully deleted: {successful_deletions} snapshots")
    if failed_deletions > 0:
        print(f"❌ Failed to delete: {failed_deletions} snapshots")

    print(f"💰 Total monthly savings: ${total_savings:.2f}")
    print(f"💰 Annual savings: ${total_savings * 12:.2f}")

    if successful_deletions > 0:
        print()
        print("🎉 Snapshot cleanup completed successfully!")
        print("   Your AWS storage costs have been significantly reduced.")

    print()
    print("📝 Remaining snapshots can be verified with:")
    print("   python3 scripts/audit/aws_ebs_audit.py")


if __name__ == "__main__":
    main()
