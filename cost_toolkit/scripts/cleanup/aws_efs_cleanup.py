#!/usr/bin/env python3
"""
AWS EFS Cleanup Script
Deletes all EFS file systems and mount targets to eliminate any potential costs.
"""

import time

import boto3
from botocore.exceptions import ClientError

from cost_toolkit.scripts import aws_utils


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    aws_utils.setup_aws_credentials()


def _delete_mount_targets(efs_client, file_system_id):
    """Delete all mount targets for a file system."""
    mount_targets_response = efs_client.describe_mount_targets(FileSystemId=file_system_id)
    mount_targets = mount_targets_response["MountTargets"]
    deleted_count = 0

    for mt in mount_targets:
        mount_target_id = mt["MountTargetId"]
        print(f"  Deleting mount target: {mount_target_id}")
        efs_client.delete_mount_target(MountTargetId=mount_target_id)
        deleted_count += 1

    return deleted_count


def _wait_for_mount_targets_deletion(efs_client, file_system_id):
    """Wait for mount targets to be fully deleted."""
    print("  Waiting for mount targets to be deleted...")
    for _retry_count in range(6):
        time.sleep(10)
        try:
            current_mts = efs_client.describe_mount_targets(FileSystemId=file_system_id)
            if not current_mts["MountTargets"]:
                print(f"  All mount targets deleted for {file_system_id}")
                break
            print(f"  Still waiting... {len(current_mts['MountTargets'])} mount targets remaining")
        except ClientError:
            break


def _delete_single_filesystem(efs_client, fs):
    """Delete a single EFS filesystem and its mount targets."""
    file_system_id = fs["FileSystemId"]
    print(f"Processing EFS file system: {file_system_id}")

    try:
        deleted_mts = _delete_mount_targets(efs_client, file_system_id)

        if deleted_mts > 0:
            _wait_for_mount_targets_deletion(efs_client, file_system_id)

        print(f"  Deleting EFS file system: {file_system_id}")
        efs_client.delete_file_system(FileSystemId=file_system_id)
        print(f"✅ Successfully deleted EFS file system: {file_system_id}")
    except ClientError as e:
        print(f"❌ Failed to delete EFS file system {file_system_id}: {str(e)}")
        return False, 0
    return True, deleted_mts


def _process_region(region):
    """Process EFS resources in a single region."""
    print(f"\n=== Checking EFS resources in {region} ===")

    efs_client = boto3.client("efs", region_name=region)
    response = efs_client.describe_file_systems()
    file_systems = response["FileSystems"]

    if not file_systems:
        print(f"No EFS file systems found in {region}")
        return 0, 0

    print(f"Found {len(file_systems)} EFS file systems in {region}")

    deleted_filesystems = 0
    deleted_mount_targets = 0

    for fs in file_systems:
        success, mts_deleted = _delete_single_filesystem(efs_client, fs)
        if success:
            deleted_filesystems += 1
            deleted_mount_targets += mts_deleted

    return deleted_filesystems, deleted_mount_targets


def delete_efs_resources():
    """Delete all EFS file systems and mount targets across regions"""
    setup_aws_credentials()

    regions = ["us-east-1", "us-east-2"]

    total_deleted_filesystems = 0
    total_deleted_mount_targets = 0

    for region in regions:
        try:
            fs_count, mt_count = _process_region(region)
            total_deleted_filesystems += fs_count
            total_deleted_mount_targets += mt_count
        except ClientError as e:
            print(f"❌ Error accessing EFS in {region}: {str(e)}")

    print("\n=== EFS Cleanup Summary ===")
    print(f"Total EFS file systems deleted: {total_deleted_filesystems}")
    print(f"Total mount targets deleted: {total_deleted_mount_targets}")

    if total_deleted_filesystems > 0 or total_deleted_mount_targets > 0:
        print("✅ EFS cleanup completed successfully!")
        print("💰 This eliminates any potential EFS storage costs.")
    else:
        print("ℹ️ No EFS resources were deleted.")


if __name__ == "__main__":
    print("AWS EFS Cleanup Script")
    print("=" * 50)
    delete_efs_resources()
