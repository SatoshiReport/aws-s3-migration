#!/usr/bin/env python3
"""
AWS EFS Cleanup Script
Deletes all EFS file systems and mount targets to eliminate any potential costs.
"""

import os
import time

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def delete_efs_resources():
    """Delete all EFS file systems and mount targets across regions"""
    setup_aws_credentials()

    # Regions where EFS resources were detected
    regions = ["us-east-1", "us-east-2"]

    total_deleted_filesystems = 0
    total_deleted_mount_targets = 0

    for region in regions:
        print(f"\n=== Checking EFS resources in {region} ===")

        try:
            efs_client = boto3.client("efs", region_name=region)

            # List all file systems in this region
            response = efs_client.describe_file_systems()
            file_systems = response["FileSystems"]

            if not file_systems:
                print(f"No EFS file systems found in {region}")
                continue

            print(f"Found {len(file_systems)} EFS file systems in {region}")

            for fs in file_systems:
                file_system_id = fs["FileSystemId"]
                print(f"Processing EFS file system: {file_system_id}")

                try:
                    # First, delete all mount targets for this file system
                    mount_targets_response = efs_client.describe_mount_targets(
                        FileSystemId=file_system_id
                    )
                    mount_targets = mount_targets_response["MountTargets"]

                    for mt in mount_targets:
                        mount_target_id = mt["MountTargetId"]
                        print(f"  Deleting mount target: {mount_target_id}")
                        efs_client.delete_mount_target(MountTargetId=mount_target_id)
                        total_deleted_mount_targets += 1

                    # Wait for mount targets to be deleted before deleting file system
                    if mount_targets:
                        print(f"  Waiting for mount targets to be deleted...")
                        # Wait longer for mount targets to fully delete
                        for i in range(6):  # Wait up to 60 seconds
                            time.sleep(10)
                            try:
                                current_mts = efs_client.describe_mount_targets(
                                    FileSystemId=file_system_id
                                )
                                if not current_mts["MountTargets"]:
                                    print(f"  All mount targets deleted for {file_system_id}")
                                    break
                                else:
                                    print(
                                        f"  Still waiting... {len(current_mts['MountTargets'])} mount targets remaining"
                                    )
                            except:
                                break

                    # Now delete the file system
                    print(f"  Deleting EFS file system: {file_system_id}")
                    efs_client.delete_file_system(FileSystemId=file_system_id)
                    print(f"✅ Successfully deleted EFS file system: {file_system_id}")
                    total_deleted_filesystems += 1

                except Exception as e:
                    print(f"❌ Failed to delete EFS file system {file_system_id}: {str(e)}")

        except Exception as e:
            print(f"❌ Error accessing EFS in {region}: {str(e)}")

    print(f"\n=== EFS Cleanup Summary ===")
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
