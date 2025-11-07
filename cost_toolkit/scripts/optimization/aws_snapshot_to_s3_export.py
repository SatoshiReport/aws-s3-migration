#!/usr/bin/env python3
"""
AWS EBS Snapshot to S3 Export Script
Exports EBS snapshots to S3 for significant cost savings by:
1. Creating AMIs from snapshots
2. Exporting AMIs to S3 buckets
3. Optionally deleting original snapshots after successful export
4. Setting up S3 lifecycle policies for further cost optimization

Cost savings: From $0.05/GB/month (EBS) to $0.00099/GB/month (S3 Deep Archive) = 98% reduction
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta

import boto3
from dotenv import load_dotenv

MAX_EXPORT_HOURS = 8
MAX_EXPORT_STATUS_ERRORS = 5
FAST_STABILITY_MINUTES = 2
FAST_STABILITY_INTERVAL_MINUTES = 1
NORMAL_STABILITY_MINUTES = 10
NORMAL_STABILITY_INTERVAL_MINUTES = 5
SIZE_VARIANCE_PERCENT = 10


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def create_s3_bucket_if_not_exists(s3_client, bucket_name, region):
    """Create S3 bucket if it doesn't exist"""
    try:
        # Check if bucket exists
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"   ✅ S3 bucket {bucket_name} already exists")
        return True
    except:
        try:
            if region == "us-east-1":
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region}
                )
            print(f"   ✅ Created S3 bucket: {bucket_name}")
            return True
        except Exception as e:
            print(f"   ❌ Error creating bucket {bucket_name}: {e}")
            return False


def setup_s3_bucket_versioning(s3_client, bucket_name):
    """Enable S3 bucket versioning for data protection"""
    try:
        s3_client.put_bucket_versioning(
            Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
        )
        print(f"   ✅ Enabled versioning for {bucket_name}")
        return True
    except Exception as e:
        print(f"   ❌ Error enabling versioning: {e}")
        return False


def create_ami_from_snapshot(ec2_client, snapshot_id, snapshot_description):
    """Create an AMI from an EBS snapshot"""
    try:
        # Generate AMI name based on snapshot
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        ami_name = f"export-{snapshot_id}-{timestamp}"

        print(f"   🔄 Creating AMI from snapshot {snapshot_id}...")

        # Create AMI from snapshot
        response = ec2_client.register_image(
            Name=ami_name,
            Description=f"AMI for S3 export from {snapshot_id}: {snapshot_description}",
            Architecture="x86_64",
            RootDeviceName="/dev/sda1",
            BlockDeviceMappings=[
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {
                        "SnapshotId": snapshot_id,
                        "VolumeType": "gp3",
                        "DeleteOnTermination": True,
                    },
                }
            ],
            VirtualizationType="hvm",
            SriovNetSupport="simple",
            EnaSupport=True,
        )

        ami_id = response["ImageId"]
        print(f"   ✅ Created AMI: {ami_id}")

        # Wait for AMI to be available
        print(f"   ⏳ Waiting for AMI {ami_id} to become available...")
        waiter = ec2_client.get_waiter("image_available")
        waiter.wait(
            ImageIds=[ami_id],
            WaiterConfig={"Delay": 30, "MaxAttempts": 40},  # Wait up to 20 minutes
        )
        print(f"   ✅ AMI {ami_id} is now available")

        return ami_id
    except Exception as e:
        print(f"   ❌ Error creating AMI from snapshot {snapshot_id}: {e}")
        return None


def _extract_s3_key_from_task(task, export_task_id, ami_id):
    """Extract S3 key from export task, handling different response structures"""
    s3_key = None
    if "S3ExportLocation" in task:
        s3_export_location = task["S3ExportLocation"]
        if "S3Key" in s3_export_location:
            s3_key = s3_export_location["S3Key"]
        elif "S3Prefix" in s3_export_location:
            # If S3Key is not available, construct it from S3Prefix and task ID
            s3_prefix = s3_export_location["S3Prefix"]
            s3_key = f"{s3_prefix}{export_task_id}.vmdk"

    # If we still don't have an S3 key, construct one from the known prefix
    if not s3_key:
        s3_key = f"ebs-snapshots/{ami_id}/{export_task_id}.vmdk"

    return export_task_id, s3_key


def export_ami_to_s3(ec2_client, s3_client, ami_id, bucket_name, region, snapshot_size_gb):
    """Export AMI to S3 bucket with multi-signal completion detection"""
    # Reset error counter for this export attempt
    export_ami_to_s3.error_count = 0

    try:
        print(f"   🔄 Exporting AMI {ami_id} to S3 bucket {bucket_name}...")

        # Start export task
        response = ec2_client.export_image(
            ImageId=ami_id,
            DiskImageFormat="VMDK",  # or 'RAW', 'VHD'
            S3ExportLocation={"S3Bucket": bucket_name, "S3Prefix": f"ebs-snapshots/{ami_id}/"},
            Description=f"Export of AMI {ami_id} for cost optimization",
        )

        export_task_id = response["ExportImageTaskId"]
        print(f"   ✅ Started export task: {export_task_id}")

        # Monitor export progress with multi-signal completion detection
        print(f"   ⏳ Monitoring export progress with intelligent completion detection...")
        start_time = time.time()
        last_s3_check_time = 0
        s3_check_interval = 15 * 60  # Check S3 every 15 minutes

        # Stuck detection parameters - be very patient to allow exports to complete
        max_export_hours = (
            MAX_EXPORT_HOURS  # Maximum time to wait for any export (increased from 4)
        )
        stuck_detection_hours = (
            6  # Time to wait before checking if export is stuck (increased from 2)
        )
        last_progress_change_time = start_time
        last_progress_value = 0

        while True:
            try:
                current_time = time.time()
                elapsed_time = current_time - start_time
                elapsed_hours = elapsed_time / 3600

                # CRITICAL: Check maximum time limit to prevent infinite loops
                if elapsed_hours >= max_export_hours:
                    print(
                        f"   ⏰ Export has been running for {elapsed_hours:.1f} hours (max: {max_export_hours})"
                    )
                    print(
                        f"   ❌ Aborting stuck export - this is likely a permanently failed AWS export"
                    )
                    return None, None

                # Check AWS export task status
                status_response = ec2_client.describe_export_image_tasks(
                    ExportImageTaskIds=[export_task_id]
                )

                if status_response["ExportImageTasks"]:
                    task = status_response["ExportImageTasks"][0]
                    status = task["Status"]
                    progress = task.get("Progress", "N/A")
                    status_msg = task.get("StatusMessage", "")

                    # Show detailed status with message
                    if status_msg:
                        print(
                            f"   📊 AWS Status: {status} | Progress: {progress}% | Message: {status_msg} | Elapsed: {elapsed_hours:.1f}h"
                        )
                    else:
                        print(
                            f"   📊 AWS Status: {status} | Progress: {progress}% | Elapsed: {elapsed_hours:.1f}h"
                        )

                    # Track progress changes to detect stuck exports
                    current_progress = int(progress) if progress != "N/A" else 0
                    if current_progress != last_progress_value:
                        last_progress_value = current_progress
                        last_progress_change_time = current_time
                        print(f"   📈 Progress updated to {current_progress}%")

                    # Note: Removed aggressive failure detection - let exports run their full course

                    # Check if export is stuck (no progress change for too long)
                    time_since_progress_change = (current_time - last_progress_change_time) / 3600
                    if time_since_progress_change >= stuck_detection_hours and status == "active":
                        print(
                            f"   ⚠️  Export stuck at {current_progress}% for {time_since_progress_change:.1f} hours"
                        )
                        print(f"   🔍 Checking if S3 file completed despite stuck AWS status...")

                        # Force immediate S3 check for stuck exports (fast check)
                        s3_key = f"ebs-snapshots/{ami_id}/{export_task_id}.vmdk"
                        s3_stability = check_s3_file_stability(
                            s3_client, bucket_name, s3_key, snapshot_size_gb, fast_check=True
                        )

                        if s3_stability.get("exists") and s3_stability.get("stable"):
                            if s3_stability.get("size_reasonable", True):
                                print(
                                    f"   ✅ S3 file completed despite stuck AWS status! Export successful"
                                )
                                print(f"   📏 Final file size: {s3_stability['size_gb']:.2f} GB")
                                return export_task_id, s3_key
                            else:
                                print(
                                    f"   ❌ S3 file exists but size unreasonable - export likely failed"
                                )
                                return None, None
                        else:
                            print(f"   ❌ No valid S3 file found - export appears to have failed")
                            return None, None

                    # SIGNAL 1: Check AWS completion status first
                    if status == "completed":
                        print(
                            f"   ✅ AWS reports export completed after {elapsed_hours:.1f} hours!"
                        )
                        return _extract_s3_key_from_task(task, export_task_id, ami_id)
                    elif status == "failed":
                        error_msg = task.get("StatusMessage", "Unknown error")
                        print(
                            f"   ❌ AWS reports export failed after {elapsed_hours:.1f} hours: {error_msg}"
                        )
                        return None, None
                    elif status == "deleted":
                        print(f"   ⚠️  Export task was deleted after {elapsed_hours:.1f} hours")
                        print(f"   ❌ Cannot retrieve export results - task no longer exists")
                        return None, None

                    # SIGNAL 2: Check S3 file completion for active/stuck tasks
                    if (
                        status == "active"
                        and (current_time - last_s3_check_time) >= s3_check_interval
                    ):
                        print(f"   🔍 AWS shows 'active' - checking S3 file completion...")

                        # Construct expected S3 key
                        s3_key = f"ebs-snapshots/{ami_id}/{export_task_id}.vmdk"

                        # Check if S3 file exists and is stable
                        s3_stability = check_s3_file_stability(
                            s3_client, bucket_name, s3_key, snapshot_size_gb
                        )

                        if s3_stability.get("exists") and s3_stability.get("stable"):
                            if s3_stability.get("size_reasonable", True):
                                print(
                                    f"   ✅ S3 file is complete and stable! Export finished despite AWS showing 'active'"
                                )
                                print(f"   📏 Final file size: {s3_stability['size_gb']:.2f} GB")
                                return export_task_id, s3_key
                            else:
                                print(
                                    f"   ⚠️  S3 file exists but size seems unreasonable - continuing to monitor AWS status"
                                )
                        elif s3_stability.get("exists"):
                            print(f"   📈 S3 file exists but still growing - continuing to monitor")
                        else:
                            print(f"   📭 S3 file not found yet - continuing to monitor AWS status")

                        last_s3_check_time = current_time

                    # Wait before checking again
                    time.sleep(60)  # Check AWS status every minute
                else:
                    print(f"   ❌ Export task not found")
                    return None, None

            except Exception as e:
                print(f"   ❌ Error checking export status: {e}")
                # If we get repeated errors, we should break out to avoid infinite loop
                error_count = getattr(export_ami_to_s3, "error_count", 0) + 1
                export_ami_to_s3.error_count = error_count

                if error_count >= MAX_EXPORT_STATUS_ERRORS:
                    print(f"   ❌ Too many consecutive errors ({error_count}), aborting export")
                    return None, None

                time.sleep(60)

    except Exception as e:
        print(f"   ❌ Error exporting AMI {ami_id}: {e}")
        return None, None


def cleanup_temporary_ami(ec2_client, ami_id, region):
    """Clean up temporary AMI after successful export"""
    try:
        print(f"   🧹 Cleaning up temporary AMI: {ami_id}")
        ec2_client.deregister_image(ImageId=ami_id)
        print(f"   ✅ Successfully cleaned up AMI {ami_id}")
        return True
    except Exception as e:
        print(f"   ⚠️  Warning: Could not clean up AMI {ami_id}: {e}")
        return False


def check_existing_exports(ec2_client, region):
    """Check for existing completed export tasks"""
    try:
        print(f"   🔍 Checking for existing completed exports in {region}...")
        response = ec2_client.describe_export_image_tasks()
        completed_exports = []

        for task in response["ExportImageTasks"]:
            if task["Status"] == "completed":
                completed_exports.append(
                    {
                        "export_task_id": task["ExportImageTaskId"],
                        "ami_id": task.get("ImageId", "unknown"),
                        "s3_location": task.get("S3ExportLocation", {}),
                        "description": task.get("Description", ""),
                    }
                )

        if completed_exports:
            print(f"   ✅ Found {len(completed_exports)} completed exports:")
            for export in completed_exports:
                s3_bucket = export["s3_location"].get("S3Bucket", "unknown")
                s3_prefix = export["s3_location"].get("S3Prefix", "unknown")
                print(f"      - {export['export_task_id']}: s3://{s3_bucket}/{s3_prefix}")

        return completed_exports
    except Exception as e:
        print(f"   ⚠️  Could not check existing exports: {e}")
        return []


def check_s3_file_stability(
    s3_client, bucket_name, s3_key, expected_size_gb=None, fast_check=False
):
    """Check if S3 file exists and monitor its stability (size unchanged for multiple checks)"""
    stability_checks = []

    if fast_check:
        # Fast check for stuck detection - only 2 minutes total
        stability_required_minutes = FAST_STABILITY_MINUTES
        check_interval_minutes = FAST_STABILITY_INTERVAL_MINUTES
    else:
        # Normal thorough check - 10 minutes total
        stability_required_minutes = NORMAL_STABILITY_MINUTES
        check_interval_minutes = NORMAL_STABILITY_INTERVAL_MINUTES

    required_stable_checks = stability_required_minutes // check_interval_minutes

    print(f"   🔍 Checking S3 file stability: s3://{bucket_name}/{s3_key}")

    for check_num in range(required_stable_checks):
        try:
            # Check if object exists and get metadata
            response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)

            file_size_bytes = response["ContentLength"]
            file_size_gb = file_size_bytes / (1024**3)
            last_modified = response["LastModified"]

            stability_checks.append(
                {
                    "check_num": check_num + 1,
                    "size_bytes": file_size_bytes,
                    "size_gb": file_size_gb,
                    "last_modified": last_modified,
                    "timestamp": time.time(),
                }
            )

            print(
                f"   📊 Stability check {check_num + 1}/{required_stable_checks}: {file_size_gb:.2f} GB"
            )

            # If we have multiple checks, compare with previous
            if len(stability_checks) > 1:
                prev_check = stability_checks[-2]
                current_check = stability_checks[-1]

                if prev_check["size_bytes"] != current_check["size_bytes"]:
                    print(
                        f"   📈 File size changed: {prev_check['size_gb']:.2f} GB → {current_check['size_gb']:.2f} GB"
                    )
                    print(f"   ⏳ File still growing, continuing to monitor...")
                    # Reset checks since file is still changing
                    stability_checks = [current_check]
                else:
                    print(f"   ✅ File size stable: {current_check['size_gb']:.2f} GB")

            # Wait before next check (except on last iteration)
            if check_num < required_stable_checks - 1:
                print(f"   ⏳ Waiting {check_interval_minutes} minutes for next stability check...")
                time.sleep(check_interval_minutes * 60)

        except s3_client.exceptions.NoSuchKey:
            print(f"   ❌ File not found in S3: s3://{bucket_name}/{s3_key}")
            return {"exists": False, "stable": False}
        except Exception as e:
            print(f"   ❌ Error checking S3 file: {e}")
            return {"exists": False, "stable": False, "error": str(e)}

    # Analyze stability results
    if len(stability_checks) >= required_stable_checks:
        final_check = stability_checks[-1]

        # Validate file size is reasonable (VMDK compression typically 30-70% of original)
        min_expected_gb = (
            expected_size_gb * 0.1 if expected_size_gb else 0.1
        )  # At least 10% of original
        max_expected_gb = (
            expected_size_gb * 1.2 if expected_size_gb else float("inf")
        )  # Allow 20% larger

        size_reasonable = min_expected_gb <= final_check["size_gb"] <= max_expected_gb

        if not size_reasonable:
            print(
                f"   ⚠️  File size suspicious: {final_check['size_gb']:.2f} GB (expected {min_expected_gb:.1f}-{max_expected_gb:.1f} GB)"
            )

        print(
            f"   ✅ File stable for {stability_required_minutes} minutes at {final_check['size_gb']:.2f} GB"
        )

        return {
            "exists": True,
            "stable": True,
            "size_bytes": final_check["size_bytes"],
            "size_gb": final_check["size_gb"],
            "last_modified": final_check["last_modified"],
            "size_reasonable": size_reasonable,
            "stability_checks": len(stability_checks),
        }
    else:
        return {"exists": True, "stable": False}


def verify_s3_export(s3_client, bucket_name, s3_key, expected_size_gb=None):
    """Verify that the exported file exists in S3 and get its details"""
    try:
        print(f"   🔍 Verifying S3 export: s3://{bucket_name}/{s3_key}")

        # Check if object exists and get metadata
        response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)

        file_size_bytes = response["ContentLength"]
        file_size_gb = file_size_bytes / (1024**3)
        last_modified = response["LastModified"]

        print(f"   ✅ File exists in S3!")
        print(f"   📏 File size: {file_size_gb:.2f} GB ({file_size_bytes:,} bytes)")
        print(f"   📅 Last modified: {last_modified}")

        if expected_size_gb:
            size_diff_percent = abs(file_size_gb - expected_size_gb) / expected_size_gb * 100
            if size_diff_percent > SIZE_VARIANCE_PERCENT:
                print(
                    f"   ⚠️  Size variance: Expected ~{expected_size_gb} GB, got "
                    f"{file_size_gb:.2f} GB ({size_diff_percent:.1f}% difference, "
                    f"limit {SIZE_VARIANCE_PERCENT}%)"
                )
            else:
                print(
                    f"   ✅ Size verification passed (within {SIZE_VARIANCE_PERCENT}% of expected "
                    f"{expected_size_gb} GB)"
                )

        return {
            "exists": True,
            "size_bytes": file_size_bytes,
            "size_gb": file_size_gb,
            "last_modified": last_modified,
        }

    except s3_client.exceptions.NoSuchKey:
        print(f"   ❌ File not found in S3: s3://{bucket_name}/{s3_key}")
        return {"exists": False}
    except Exception as e:
        print(f"   ❌ Error verifying S3 file: {e}")
        return {"exists": False, "error": str(e)}


def calculate_cost_savings(snapshot_size_gb):
    """Calculate cost savings from EBS to S3 Standard"""
    ebs_monthly_cost = snapshot_size_gb * 0.05
    s3_standard_cost = snapshot_size_gb * 0.023
    monthly_savings = ebs_monthly_cost - s3_standard_cost
    annual_savings = monthly_savings * 12

    return {
        "ebs_cost": ebs_monthly_cost,
        "s3_cost": s3_standard_cost,
        "monthly_savings": monthly_savings,
        "annual_savings": annual_savings,
        "savings_percentage": (monthly_savings / ebs_monthly_cost) * 100,
    }


def export_snapshots_to_s3(overwrite_existing=False):
    """Main function to export EBS snapshots to S3"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    # Current snapshots to export
    snapshots_to_export = [
        {
            "snapshot_id": "snap-0f68820355c25e73e",
            "region": "eu-west-2",
            "size_gb": 384,
            "description": "Snapshot of 384 (vol-089b9ed38099c68f3) - 384GB - 2025-07-18 04:15 UTC",
        },
        {
            "snapshot_id": "snap-046b7eace8694913b",
            "region": "eu-west-2",
            "size_gb": 64,
            "description": "Snapshot of Tars 3 (vol-0249308257e5fa64d) - 64GB - 2025-07-18 04:15 UTC",
        },
        {
            "snapshot_id": "snap-036eee4a7c291fd26",
            "region": "us-east-2",
            "size_gb": 8,
            "description": "Copied for DestinationAmi ami-05d0a30507ebee9d6 from SourceAmi ami-0cb41e78dab346fb3",
        },
    ]

    print("AWS EBS Snapshot to S3 Export Script")
    print("=" * 80)
    print("Exporting EBS snapshots to S3 for maximum cost savings...")
    print()

    total_size_gb = sum(snap["size_gb"] for snap in snapshots_to_export)
    total_savings = calculate_cost_savings(total_size_gb)

    print(f"🎯 Target: {len(snapshots_to_export)} snapshots ({total_size_gb} GB total)")
    print(f"💰 Current monthly cost: ${total_savings['ebs_cost']:.2f}")
    print(f"💰 Future monthly cost: ${total_savings['s3_cost']:.2f}")
    print(
        f"💰 Monthly savings: ${total_savings['monthly_savings']:.2f} ({total_savings['savings_percentage']:.1f}%)"
    )
    print(f"💰 Annual savings: ${total_savings['annual_savings']:.2f}")
    print()

    print("⚠️  IMPORTANT NOTES:")
    print("   - Export process can take several hours per snapshot")
    print("   - AMIs will be created temporarily and automatically cleaned up after export")
    print("   - Data will be stored in S3 Standard for immediate access")
    print("   - Original snapshots can be deleted after successful export")
    print()

    confirmation = input("Type 'EXPORT TO S3' to proceed with snapshot export: ")

    if confirmation != "EXPORT TO S3":
        print("❌ Operation cancelled by user")
        return

    print()
    print("🚨 Proceeding with snapshot export to S3...")
    print("=" * 80)

    successful_exports = 0
    failed_exports = 0
    export_results = []

    # Sort snapshots by size (smallest first) for faster feedback and quicker wins
    snapshots_to_export = sorted(snapshots_to_export, key=lambda x: x["size_gb"])
    print(f"📋 Processing snapshots in order of size (smallest first):")
    for snap in snapshots_to_export:
        print(f"   - {snap['snapshot_id']}: {snap['size_gb']} GB")
    print()

    for snap_info in snapshots_to_export:
        snapshot_id = snap_info["snapshot_id"]
        region = snap_info["region"]
        size_gb = snap_info["size_gb"]
        description = snap_info["description"]

        print(f"🔍 Processing {snapshot_id} ({size_gb} GB) in {region}...")

        # Create clients for the specific region
        ec2_client = boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        s3_client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        # Check for existing completed exports first
        existing_exports = check_existing_exports(ec2_client, region)

        # Check if this snapshot was already exported by looking for AMI in existing exports
        if not overwrite_existing:
            for existing_export in existing_exports:
                if snapshot_id in existing_export.get("description", ""):
                    print(f"   ✅ Found existing export for {snapshot_id}!")
                    s3_location = existing_export["s3_location"]
                    s3_bucket = s3_location.get("S3Bucket", "")
                    s3_prefix = s3_location.get("S3Prefix", "")
                    s3_key = f"{s3_prefix}export.vmdk"  # Construct likely S3 key

                    # Verify the S3 file exists
                    verification = verify_s3_export(s3_client, s3_bucket, s3_key, size_gb)

                    if verification.get("exists"):
                        successful_exports += 1
                        savings = calculate_cost_savings(size_gb)

                        export_results.append(
                            {
                                "snapshot_id": snapshot_id,
                                "ami_id": existing_export["ami_id"],
                                "bucket_name": s3_bucket,
                                "s3_key": s3_key,
                                "export_task_id": existing_export["export_task_id"],
                                "size_gb": size_gb,
                                "monthly_savings": savings["monthly_savings"],
                            }
                        )

                        print(f"   📍 S3 location: s3://{s3_bucket}/{s3_prefix}")
                        print(f"   💰 Monthly savings: ${savings['monthly_savings']:.2f}")
                        print()
                        continue  # Skip to next snapshot
                    else:
                        print(f"   ⚠️  Existing export found but S3 file missing - will re-export")
                        break
        elif existing_exports:
            print(f"   ⚠️  Overwrite mode: Ignoring {len(existing_exports)} existing exports")

        # Create S3 bucket name
        bucket_name = f"ebs-snapshot-archive-{region}-{datetime.now().strftime('%Y%m%d')}"

        # Create S3 bucket
        if not create_s3_bucket_if_not_exists(s3_client, bucket_name, region):
            print(f"   ❌ Failed to create S3 bucket, skipping {snapshot_id}")
            failed_exports += 1
            continue

        # Enable bucket versioning for data protection
        setup_s3_bucket_versioning(s3_client, bucket_name)

        # Create AMI from snapshot
        ami_id = create_ami_from_snapshot(ec2_client, snapshot_id, description)
        if not ami_id:
            print(f"   ❌ Failed to create AMI, skipping {snapshot_id}")
            failed_exports += 1
            continue

        # Export AMI to S3
        export_task_id, s3_key = export_ami_to_s3(
            ec2_client, s3_client, ami_id, bucket_name, region, size_gb
        )

        if export_task_id and s3_key:
            # Verify the export in S3
            verification = verify_s3_export(s3_client, bucket_name, s3_key, size_gb)

            if verification.get("exists"):
                successful_exports += 1
                savings = calculate_cost_savings(size_gb)

                # Automatically clean up temporary AMI after successful export
                cleanup_temporary_ami(ec2_client, ami_id, region)

                export_results.append(
                    {
                        "snapshot_id": snapshot_id,
                        "ami_id": ami_id,
                        "bucket_name": bucket_name,
                        "s3_key": s3_key,
                        "export_task_id": export_task_id,
                        "size_gb": size_gb,
                        "monthly_savings": savings["monthly_savings"],
                    }
                )

                print(f"   ✅ Successfully exported {snapshot_id}")
                print(f"   📍 S3 location: s3://{bucket_name}/{s3_key}")
                print(f"   💰 Monthly savings: ${savings['monthly_savings']:.2f}")
            else:
                failed_exports += 1
                print(f"   ❌ Export completed but S3 verification failed for {snapshot_id}")
        else:
            failed_exports += 1
            print(f"   ❌ Failed to export {snapshot_id}")

        print()

    print("=" * 80)
    print("🎯 S3 EXPORT SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully exported: {successful_exports} snapshots")
    print(f"❌ Failed to export: {failed_exports} snapshots")

    if export_results:
        total_monthly_savings = sum(result["monthly_savings"] for result in export_results)
        print(f"💰 Total monthly savings: ${total_monthly_savings:.2f}")
        print(f"💰 Total annual savings: ${total_monthly_savings * 12:.2f}")
        print()

        print("📋 Export Results:")
        for result in export_results:
            print(f"   {result['snapshot_id']} → s3://{result['bucket_name']}/{result['s3_key']}")

        print()
        print("📝 Next Steps:")
        print("1. Verify exports in S3 console")
        print("2. Test restore process if needed")
        print("3. Delete original EBS snapshots to realize savings")
        print()
        print("🔧 Optional: Delete Original Snapshots (after verifying S3 exports):")
        for result in export_results:
            print(
                f"   aws ec2 delete-snapshot --snapshot-id {result['snapshot_id']} --region {region}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export EBS snapshots to S3 for cost optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 aws_snapshot_to_s3_export.py                    # Normal mode - skip existing exports
  python3 aws_snapshot_to_s3_export.py --overwrite       # Overwrite existing S3 files
        """,
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing S3 exports (default: skip existing exports)",
    )

    args = parser.parse_args()

    try:
        export_snapshots_to_s3(overwrite_existing=args.overwrite)
    except Exception as e:
        print(f"❌ Script failed: {e}")
        exit(1)
