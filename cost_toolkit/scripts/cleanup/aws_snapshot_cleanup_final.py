#!/usr/bin/env python3
"""
AWS Final Snapshot Cleanup Script
Deletes the snapshots that were freed after AMI deregistration.
This script targets the 7 specific snapshots that should now be deletable.
"""

import os
import time
from datetime import datetime

import boto3
from dotenv import load_dotenv


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def delete_snapshot(ec2_client, snapshot_id, region):
    """Delete a specific snapshot"""
    try:
        print(f"🗑️  Deleting snapshot: {snapshot_id} in {region}")
        ec2_client.delete_snapshot(SnapshotId=snapshot_id)
        print(f"   ✅ Successfully deleted {snapshot_id}")
        return True
    except Exception as e:
        print(f"   ❌ Error deleting {snapshot_id}: {e}")
        return False


def delete_freed_snapshots():
    """Delete snapshots that were freed after AMI deregistration"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    # Snapshots that should now be deletable after AMI deregistration
    snapshots_to_delete = [
        {
            "snapshot_id": "snap-09e90c64db692f884",
            "region": "eu-west-2",
            "size_gb": 1024,
            "description": "Tars Image snapshot",
        },
        {
            "snapshot_id": "snap-07c0d4017e24b3240",
            "region": "us-east-1",
            "size_gb": 32,
            "description": "SadTalker snapshot",
        },
        {
            "snapshot_id": "snap-0fbb003580d3dc8ba",
            "region": "us-east-1",
            "size_gb": 64,
            "description": "GPU snapshot",
        },
        {
            "snapshot_id": "snap-024d718f6d670bff2",
            "region": "us-east-1",
            "size_gb": 8,
            "description": "Migration snapshot 1",
        },
        {
            "snapshot_id": "snap-0ac8b88270ff68d4d",
            "region": "us-east-1",
            "size_gb": 8,
            "description": "Migration snapshot 2",
        },
        {
            "snapshot_id": "snap-0700cdc4cdfaaf8fd",
            "region": "us-east-2",
            "size_gb": 8,
            "description": "Migration snapshot 3",
        },
        {
            "snapshot_id": "snap-05a42843f18ba1c5e",
            "region": "us-east-2",
            "size_gb": 8,
            "description": "Mufasa backup snapshot",
        },
    ]

    print("AWS Final Snapshot Cleanup Script")
    print("=" * 80)
    print("Deleting snapshots freed after AMI deregistration...")
    print()
    print(f"🎯 Target: {len(snapshots_to_delete)} freed snapshots for deletion")
    print()

    total_potential_savings = sum(snap["size_gb"] * 0.05 for snap in snapshots_to_delete)

    print("⚠️  FINAL WARNING: This will permanently delete these snapshots!")
    print("   - All snapshot data will be lost")
    print("   - This action cannot be undone")
    print("   - You will lose the ability to restore from these snapshots")
    print(f"   - Total monthly savings: ${total_potential_savings:.2f}")
    print()

    confirmation = input("Type 'DELETE FREED SNAPSHOTS' to confirm deletion: ")

    if confirmation != "DELETE FREED SNAPSHOTS":
        print("❌ Operation cancelled by user")
        return

    print()
    print("🚨 Proceeding with freed snapshot deletion...")
    print("=" * 80)

    successful_deletions = 0
    failed_deletions = 0
    total_savings = 0

    for snap_info in snapshots_to_delete:
        snapshot_id = snap_info["snapshot_id"]
        region = snap_info["region"]
        size_gb = snap_info["size_gb"]
        description = snap_info["description"]
        monthly_cost = size_gb * 0.05

        print(f"🔍 Processing {snapshot_id}...")
        print(f"   Region: {region}")
        print(f"   Size: {size_gb} GB")
        print(f"   Description: {description}")
        print(f"   Monthly cost: ${monthly_cost:.2f}")

        # Create EC2 client for the specific region
        ec2_client = boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        if delete_snapshot(ec2_client, snapshot_id, region):
            successful_deletions += 1
            total_savings += monthly_cost
        else:
            failed_deletions += 1

        print()

        # Small delay between deletions to avoid rate limiting
        time.sleep(1)

    print("=" * 80)
    print("🎯 FINAL CLEANUP SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully deleted: {successful_deletions} snapshots")
    print(f"❌ Failed to delete: {failed_deletions} snapshots")
    print(f"💰 Total monthly savings: ${total_savings:.2f}")
    print(f"💰 Annual savings: ${total_savings * 12:.2f}")
    print()

    if successful_deletions > 0:
        print("🎉 Final snapshot cleanup completed successfully!")
        print("   Your AWS storage costs have been further reduced.")
        print()
        print("📝 Verify final state with:")
        print("   python3 scripts/audit/aws_ebs_audit.py")
    else:
        print("❌ No snapshots were successfully deleted")
        print("   The AMIs may still be processing deregistration")
        print("   Try again in a few minutes")


if __name__ == "__main__":
    try:
        delete_freed_snapshots()
    except Exception as e:
        print(f"❌ Script failed: {e}")
        exit(1)
