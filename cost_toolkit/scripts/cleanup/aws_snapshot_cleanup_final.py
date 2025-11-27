#!/usr/bin/env python3
"""
AWS Final Snapshot Cleanup Script
Deletes the snapshots that were freed after AMI deregistration.
This script targets the 7 specific snapshots that should now be deletable.
"""

import sys
import time

from botocore.exceptions import ClientError

from cost_toolkit.common.aws_client_factory import create_client
from cost_toolkit.common.cli_utils import confirm_action
from cost_toolkit.common.cost_utils import calculate_snapshot_cost
from cost_toolkit.common.credential_utils import setup_aws_credentials


def delete_snapshot(_ec2_client, snapshot_id, region):
    """
    Delete a specific snapshot.
    """
    print(f"🗑️  Deleting snapshot: {snapshot_id} in {region}")
    try:
        _ec2_client.delete_snapshot(SnapshotId=snapshot_id)
        print(f"   ✅ Successfully deleted {snapshot_id}")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "InvalidSnapshot.NotFound":
            print(f"   ℹ️  Snapshot {snapshot_id} not found")
        else:
            print(f"   ❌ Error deleting {snapshot_id}: {e}")
        return False
    return True


def get_snapshots_to_delete():
    """Get list of snapshots to delete after AMI deregistration"""
    return [
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


def print_deletion_warning(snapshots_to_delete):
    """Print warning message about snapshot deletion"""
    print("AWS Final Snapshot Cleanup Script")
    print("=" * 80)
    print("Deleting snapshots freed after AMI deregistration...")
    print()
    print(f"🎯 Target: {len(snapshots_to_delete)} freed snapshots for deletion")
    print()

    total_potential_savings = sum(
        calculate_snapshot_cost(snap["size_gb"]) for snap in snapshots_to_delete
    )

    print("⚠️  FINAL WARNING: This will permanently delete these snapshots!")
    print("   - All snapshot data will be lost")
    print("   - This action cannot be undone")
    print("   - You will lose the ability to restore from these snapshots")
    print(f"   - Total monthly savings: ${total_potential_savings:.2f}")
    print()


def confirm_snapshot_deletion():
    """Prompt user for snapshot deletion confirmation. Delegates to canonical implementation."""
    return confirm_action(
        "Type 'DELETE FREED SNAPSHOTS' to confirm deletion: ", exact_match="DELETE FREED SNAPSHOTS"
    )


def process_snapshot_deletions(snapshots_to_delete, aws_access_key_id, aws_secret_access_key):
    """Process deletion for all snapshots"""
    successful_deletions = 0
    failed_deletions = 0
    total_savings = 0

    for snap_info in snapshots_to_delete:
        snapshot_id = snap_info["snapshot_id"]
        region = snap_info["region"]
        size_gb = snap_info["size_gb"]
        description = snap_info["description"]
        monthly_cost = calculate_snapshot_cost(size_gb)

        print(f"🔍 Processing {snapshot_id}...")
        print(f"   Region: {region}")
        print(f"   Size: {size_gb} GB")
        print(f"   Description: {description}")
        print(f"   Monthly cost: ${monthly_cost:.2f}")

        ec2_client = create_client(
            "ec2",
            region=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        if delete_snapshot(ec2_client, snapshot_id, region):
            successful_deletions += 1
            total_savings += monthly_cost
        else:
            failed_deletions += 1

        print()
        time.sleep(1)

    return successful_deletions, failed_deletions, total_savings


def print_cleanup_summary(successful_deletions, failed_deletions, total_savings):
    """Print summary of cleanup results"""
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


def delete_freed_snapshots():
    """Delete snapshots that were freed after AMI deregistration"""
    aws_access_key_id, aws_secret_access_key = setup_aws_credentials()
    snapshots_to_delete = get_snapshots_to_delete()

    print_deletion_warning(snapshots_to_delete)

    if not confirm_snapshot_deletion():
        print("❌ Operation cancelled by user")
        return

    print()
    print("🚨 Proceeding with freed snapshot deletion...")
    print("=" * 80)

    successful, failed, savings = process_snapshot_deletions(
        snapshots_to_delete, aws_access_key_id, aws_secret_access_key
    )

    print_cleanup_summary(successful, failed, savings)


def main():
    """Main function."""
    try:
        delete_freed_snapshots()
    except ClientError as e:
        print(f"❌ Script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
