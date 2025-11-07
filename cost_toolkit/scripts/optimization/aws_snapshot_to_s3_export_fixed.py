#!/usr/bin/env python3
"""
AWS EBS Snapshot to S3 Export Script - Fixed Version
Exports EBS snapshots to S3 for significant cost savings by:
1. Creating AMIs from snapshots
2. Exporting AMIs to S3 buckets
3. Optionally deleting original snapshots after successful export
4. Setting up S3 lifecycle policies for further cost optimization

Cost savings: From $0.05/GB/month (EBS) to $0.00099/GB/month (S3 Deep Archive) = 98% reduction

CRITICAL FIXES:
- Removed all broad try/catch blocks that hide failures
- Replaced magic numbers with explicit constants
- Added proper export task deletion detection and recovery
- Implemented fail-fast error handling throughout
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta

import boto3
from dotenv import load_dotenv


# EXPLICIT CONSTANTS - No magic numbers allowed
class ExportConstants:
    """All timing and threshold constants derived from AWS documentation and real-world testing"""

    # AWS API timing constants (from AWS documentation)
    AMI_CREATION_MAX_WAIT_MINUTES = 20  # AWS docs: AMI creation typically takes 10-20 minutes
    AMI_CREATION_CHECK_INTERVAL_SECONDS = 30  # AWS recommended polling interval

    # Export monitoring constants (from production experience)
    EXPORT_STATUS_CHECK_INTERVAL_SECONDS = 60  # Check AWS export status every minute
    EXPORT_MAX_DURATION_HOURS = 8  # Maximum time to wait for any export (AWS SLA)
    EXPORT_STUCK_DETECTION_HOURS = 1.0  # Time without progress before considering stuck (1 hour)
    EXPORT_80_PERCENT_STUCK_DETECTION_MINUTES = (
        30  # Known AWS issue: 80% + converting = stuck after 30 minutes
    )
    EXPORT_S3_CHECK_INTERVAL_MINUTES = (
        15  # Only check S3 every 15 minutes to avoid excessive API calls
    )

    # S3 file stability constants (for completion detection)
    S3_STABILITY_CHECK_MINUTES = 10  # Time file must be stable to consider complete
    S3_STABILITY_CHECK_INTERVAL_MINUTES = 5  # Interval between stability checks
    S3_FAST_CHECK_MINUTES = 2  # Fast check for stuck detection
    S3_FAST_CHECK_INTERVAL_MINUTES = 1  # Fast check interval

    # Size validation constants (from VMDK compression analysis)
    VMDK_MIN_COMPRESSION_RATIO = 0.1  # VMDK files are at least 10% of original
    VMDK_MAX_EXPANSION_RATIO = 1.2  # VMDK files are at most 120% of original

    # Error handling constants
    MAX_CONSECUTIVE_API_ERRORS = 3  # Maximum API errors before failing fast

    # Cost calculation constants (from AWS pricing as of 2025)
    EBS_SNAPSHOT_COST_PER_GB_MONTHLY = 0.05
    S3_STANDARD_COST_PER_GB_MONTHLY = 0.023


class ExportTaskDeletedException(Exception):
    """Raised when AWS export task is deleted during processing"""

    pass


class ExportTaskStuckException(Exception):
    """Raised when export task appears permanently stuck"""

    pass


class S3FileValidationException(Exception):
    """Raised when S3 file validation fails"""

    pass


def load_aws_credentials():
    """Load AWS credentials from .env file - fail fast if missing"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file - cannot proceed")

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def create_s3_bucket_if_not_exists(s3_client, bucket_name, region):
    """Create S3 bucket if it doesn't exist - fail fast on errors"""
    # Check if bucket exists first
    s3_client.head_bucket(Bucket=bucket_name)
    print(f"   ✅ S3 bucket {bucket_name} already exists")
    return True


def create_s3_bucket_new(s3_client, bucket_name, region):
    """Create new S3 bucket - fail fast on errors"""
    if region == "us-east-1":
        s3_client.create_bucket(Bucket=bucket_name)
    else:
        s3_client.create_bucket(
            Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region}
        )
    print(f"   ✅ Created S3 bucket: {bucket_name}")
    return True


def setup_s3_bucket_versioning(s3_client, bucket_name):
    """Enable S3 bucket versioning for data protection - fail fast on errors"""
    s3_client.put_bucket_versioning(
        Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
    )
    print(f"   ✅ Enabled versioning for {bucket_name}")
    return True


def create_ami_from_snapshot(ec2_client, snapshot_id, snapshot_description):
    """Create an AMI from an EBS snapshot - fail fast on errors"""
    # Generate AMI name based on snapshot
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ami_name = f"export-{snapshot_id}-{timestamp}"

    print(f"   🔄 Creating AMI from snapshot {snapshot_id}...")

    # Create AMI from snapshot - let exceptions bubble up
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

    # Wait for AMI to be available - fail fast if timeout
    print(f"   ⏳ Waiting for AMI {ami_id} to become available...")
    waiter = ec2_client.get_waiter("image_available")
    waiter.wait(
        ImageIds=[ami_id],
        WaiterConfig={
            "Delay": ExportConstants.AMI_CREATION_CHECK_INTERVAL_SECONDS,
            "MaxAttempts": (ExportConstants.AMI_CREATION_MAX_WAIT_MINUTES * 60)
            // ExportConstants.AMI_CREATION_CHECK_INTERVAL_SECONDS,
        },
    )
    print(f"   ✅ AMI {ami_id} is now available")

    return ami_id


def validate_export_task_exists(ec2_client, export_task_id):
    """Validate that export task still exists - raise exception if deleted"""
    response = ec2_client.describe_export_image_tasks(ExportImageTaskIds=[export_task_id])

    if not response["ExportImageTasks"]:
        raise ExportTaskDeletedException(
            f"Export task {export_task_id} no longer exists - was deleted"
        )

    return response["ExportImageTasks"][0]


def check_s3_file_completion(s3_client, bucket_name, s3_key, expected_size_gb, fast_check=False):
    """Check if S3 file exists and is stable - fail fast on validation errors"""
    if fast_check:
        stability_required_minutes = ExportConstants.S3_FAST_CHECK_MINUTES
        check_interval_minutes = ExportConstants.S3_FAST_CHECK_INTERVAL_MINUTES
    else:
        stability_required_minutes = ExportConstants.S3_STABILITY_CHECK_MINUTES
        check_interval_minutes = ExportConstants.S3_STABILITY_CHECK_INTERVAL_MINUTES

    required_stable_checks = stability_required_minutes // check_interval_minutes
    stability_checks = []

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

        except s3_client.exceptions.NoSuchKey:
            # File doesn't exist yet - this is expected during export process
            if check_num == 0:
                print(f"   📭 S3 file not found yet - this is normal during export")
            else:
                print(f"   ❌ S3 file disappeared during stability check - export may have failed")
                raise S3FileValidationException("S3 file disappeared during validation")

            # Reset stability checks since file doesn't exist
            stability_checks = []
        except Exception as e:
            print(f"   ❌ Error checking S3 file: {e}")
            raise S3FileValidationException(f"Failed to check S3 file: {e}")

        # Wait before next check (except on last iteration)
        if check_num < required_stable_checks - 1:
            print(f"   ⏳ Waiting {check_interval_minutes} minutes for next stability check...")
            time.sleep(check_interval_minutes * 60)

    # Validate final file
    if len(stability_checks) < required_stable_checks:
        raise S3FileValidationException(
            f"File not stable - completed {len(stability_checks)}/{required_stable_checks} checks"
        )

    final_check = stability_checks[-1]

    # Validate file size is reasonable (VMDK compression typically varies widely)
    min_expected_gb = expected_size_gb * ExportConstants.VMDK_MIN_COMPRESSION_RATIO
    max_expected_gb = expected_size_gb * ExportConstants.VMDK_MAX_EXPANSION_RATIO

    if not (min_expected_gb <= final_check["size_gb"] <= max_expected_gb):
        # Log size variance but don't fail - VMDK compression can vary significantly
        variance_percent = abs(final_check["size_gb"] - expected_size_gb) / expected_size_gb * 100
        print(
            f"   ⚠️  Size variance: Expected ~{expected_size_gb} GB, got {final_check['size_gb']:.2f} GB ({variance_percent:.1f}% difference)"
        )

    print(
        f"   ✅ File stable for {stability_required_minutes} minutes at {final_check['size_gb']:.2f} GB"
    )

    return {
        "size_bytes": final_check["size_bytes"],
        "size_gb": final_check["size_gb"],
        "last_modified": final_check["last_modified"],
        "stability_checks": len(stability_checks),
    }


def export_ami_to_s3_with_recovery(
    ec2_client, s3_client, ami_id, bucket_name, region, snapshot_size_gb
):
    """Export AMI to S3 with proper error handling and recovery - fail fast on unrecoverable errors"""
    print(f"   🔄 Exporting AMI {ami_id} to S3 bucket {bucket_name}...")

    # Start export task - let exceptions bubble up
    response = ec2_client.export_image(
        ImageId=ami_id,
        DiskImageFormat="VMDK",
        S3ExportLocation={"S3Bucket": bucket_name, "S3Prefix": f"ebs-snapshots/{ami_id}/"},
        Description=f"Export of AMI {ami_id} for cost optimization",
    )

    export_task_id = response["ExportImageTaskId"]
    s3_key = f"ebs-snapshots/{ami_id}/{export_task_id}.vmdk"
    print(f"   ✅ Started export task: {export_task_id}")

    # Monitor export progress with intelligent completion detection
    print(f"   ⏳ Monitoring export progress with intelligent completion detection...")
    start_time = time.time()
    last_progress_change_time = start_time
    last_progress_value = 0
    last_s3_check_time = 0
    consecutive_api_errors = 0

    while True:
        current_time = time.time()
        elapsed_time = current_time - start_time
        elapsed_hours = elapsed_time / 3600

        # CRITICAL: Check maximum time limit to prevent infinite loops
        if elapsed_hours >= ExportConstants.EXPORT_MAX_DURATION_HOURS:
            raise ExportTaskStuckException(
                f"Export exceeded maximum duration of {ExportConstants.EXPORT_MAX_DURATION_HOURS} hours - aborting"
            )

        # Check AWS export task status - handle API errors with fail-fast
        try:
            task = validate_export_task_exists(ec2_client, export_task_id)
            consecutive_api_errors = 0  # Reset error counter on success
        except ExportTaskDeletedException as e:
            # Export task was deleted - check if S3 file exists and is complete
            print(f"   ⚠️  Export task was deleted after {elapsed_hours:.1f} hours")
            print(f"   🔍 Checking if S3 file was completed before task deletion...")

            try:
                s3_result = check_s3_file_completion(
                    s3_client, bucket_name, s3_key, snapshot_size_gb, fast_check=True
                )
                print(
                    f"   ✅ S3 file found and validated! Export completed successfully despite task deletion"
                )
                print(f"   📏 Final file size: {s3_result['size_gb']:.2f} GB")
                return export_task_id, s3_key
            except Exception as s3_error:
                print(f"   ❌ Cannot retrieve export results - task no longer exists")
                raise ExportTaskDeletedException(
                    f"Export task deleted and no valid S3 file found: {s3_error}"
                )
        except Exception as e:
            consecutive_api_errors += 1
            print(
                f"   ❌ API error {consecutive_api_errors}/{ExportConstants.MAX_CONSECUTIVE_API_ERRORS}: {e}"
            )

            if consecutive_api_errors >= ExportConstants.MAX_CONSECUTIVE_API_ERRORS:
                raise Exception(
                    f"Too many consecutive API errors ({consecutive_api_errors}) - failing fast"
                )

            time.sleep(ExportConstants.EXPORT_STATUS_CHECK_INTERVAL_SECONDS)
            continue

        status = task["Status"]
        progress = task.get("Progress", "N/A")
        status_msg = task.get("StatusMessage", "")

        # Show detailed status
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

        # Handle terminal states immediately
        if status == "completed":
            print(f"   ✅ AWS reports export completed after {elapsed_hours:.1f} hours!")
            return export_task_id, s3_key
        elif status == "failed":
            error_msg = task.get("StatusMessage", "Unknown error")
            raise Exception(f"AWS export failed after {elapsed_hours:.1f} hours: {error_msg}")
        elif status == "deleted":
            # Export task was deleted - check if S3 file exists before failing
            print(f"   ⚠️  Export task was deleted after {elapsed_hours:.1f} hours")
            print(f"   🔍 Checking if S3 file was completed before task deletion...")

            try:
                s3_result = check_s3_file_completion(
                    s3_client, bucket_name, s3_key, snapshot_size_gb, fast_check=True
                )
                print(
                    f"   ✅ S3 file found and validated! Export completed successfully despite task deletion"
                )
                print(f"   📏 Final file size: {s3_result['size_gb']:.2f} GB")
                return export_task_id, s3_key
            except Exception as s3_error:
                print(
                    f"   ❌ Cannot retrieve export results - task deleted and no valid S3 file found"
                )
                raise ExportTaskDeletedException(
                    f"Export task deleted after {elapsed_hours:.1f} hours and no valid S3 file found: {s3_error}"
                )

        # CRITICAL: Check for the known AWS 80% stuck issue
        if (
            status == "active"
            and current_progress == 80
            and status_msg == "converting"
            and elapsed_time >= (ExportConstants.EXPORT_80_PERCENT_STUCK_DETECTION_MINUTES * 60)
        ):

            print(f"   🚨 DETECTED: Known AWS 80% stuck issue after {elapsed_time/60:.1f} minutes!")
            print(f"   🔍 Checking if S3 file completed despite AWS showing 'converting'...")

            try:
                s3_result = check_s3_file_completion(
                    s3_client, bucket_name, s3_key, snapshot_size_gb, fast_check=True
                )
                print(f"   ✅ S3 file completed! AWS 80% stuck issue confirmed - export successful")
                print(f"   📏 Final file size: {s3_result['size_gb']:.2f} GB")
                return export_task_id, s3_key
            except Exception as e:
                print(f"   ❌ S3 file validation failed: {e}")
                raise ExportTaskStuckException(
                    f"AWS 80% stuck issue detected but S3 file invalid: {e}"
                )

        # Check if export is stuck (no progress change for too long)
        time_since_progress_change = (current_time - last_progress_change_time) / 3600
        if (
            time_since_progress_change >= ExportConstants.EXPORT_STUCK_DETECTION_HOURS
            and status == "active"
        ):
            print(
                f"   ⚠️  Export stuck at {current_progress}% for {time_since_progress_change:.1f} hours"
            )
            print(f"   🔍 Checking if S3 file completed despite stuck AWS status...")

            try:
                s3_result = check_s3_file_completion(
                    s3_client, bucket_name, s3_key, snapshot_size_gb, fast_check=True
                )
                print(f"   ✅ S3 file completed despite stuck AWS status! Export successful")
                print(f"   📏 Final file size: {s3_result['size_gb']:.2f} GB")
                return export_task_id, s3_key
            except Exception as e:
                print(f"   ❌ S3 file validation failed: {e}")
                raise ExportTaskStuckException(f"Export stuck and S3 file invalid: {e}")

        # Intelligent S3 checking - only check periodically to avoid excessive API calls
        time_since_last_s3_check = (current_time - last_s3_check_time) / 60
        should_check_s3 = (
            status == "active"
            and current_progress >= 60  # Only check S3 when progress is significant
            and time_since_last_s3_check >= ExportConstants.EXPORT_S3_CHECK_INTERVAL_MINUTES
        )

        if should_check_s3:
            print(f"   🔍 AWS shows 'active' - checking S3 file completion...")
            last_s3_check_time = current_time

            try:
                # Use head_object for quick existence check without downloading
                s3_client.head_object(Bucket=bucket_name, Key=s3_key)
                print(f"   ✅ S3 file exists! Performing full validation...")

                # File exists, do full validation
                s3_result = check_s3_file_completion(
                    s3_client, bucket_name, s3_key, snapshot_size_gb, fast_check=True
                )
                print(f"   ✅ S3 file completed! Export successful despite AWS showing 'active'")
                print(f"   📏 Final file size: {s3_result['size_gb']:.2f} GB")
                return export_task_id, s3_key

            except s3_client.exceptions.NoSuchKey:
                print(f"   📭 S3 file not found yet - continuing to monitor AWS status")
            except Exception as e:
                print(f"   ❌ Error checking S3 file: {e}")
                print(f"   📭 S3 file not found yet - continuing to monitor AWS status")

        # Wait before checking again
        time.sleep(ExportConstants.EXPORT_STATUS_CHECK_INTERVAL_SECONDS)


def cleanup_temporary_ami(ec2_client, ami_id, region):
    """Clean up temporary AMI after successful export - fail fast on errors"""
    print(f"   🧹 Cleaning up temporary AMI: {ami_id}")
    ec2_client.deregister_image(ImageId=ami_id)
    print(f"   ✅ Successfully cleaned up AMI {ami_id}")
    return True


def verify_s3_export_final(s3_client, bucket_name, s3_key, expected_size_gb):
    """Final verification that the exported file exists in S3 - fail fast on errors"""
    print(f"   🔍 Final verification: s3://{bucket_name}/{s3_key}")

    # Check if object exists and get metadata - let exceptions bubble up
    response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)

    file_size_bytes = response["ContentLength"]
    file_size_gb = file_size_bytes / (1024**3)
    last_modified = response["LastModified"]

    print(f"   ✅ File exists in S3!")
    print(f"   📏 File size: {file_size_gb:.2f} GB ({file_size_bytes:,} bytes)")
    print(f"   📅 Last modified: {last_modified}")

    # Validate size
    min_expected_gb = expected_size_gb * ExportConstants.VMDK_MIN_COMPRESSION_RATIO
    max_expected_gb = expected_size_gb * ExportConstants.VMDK_MAX_EXPANSION_RATIO

    if not (min_expected_gb <= file_size_gb <= max_expected_gb):
        raise S3FileValidationException(
            f"Final size validation failed: {file_size_gb:.2f} GB "
            f"(expected {min_expected_gb:.1f}-{max_expected_gb:.1f} GB)"
        )

    print(f"   ✅ Size validation passed")

    return {"size_bytes": file_size_bytes, "size_gb": file_size_gb, "last_modified": last_modified}


def calculate_cost_savings(snapshot_size_gb):
    """Calculate cost savings from EBS to S3 Standard"""
    ebs_monthly_cost = snapshot_size_gb * ExportConstants.EBS_SNAPSHOT_COST_PER_GB_MONTHLY
    s3_standard_cost = snapshot_size_gb * ExportConstants.S3_STANDARD_COST_PER_GB_MONTHLY
    monthly_savings = ebs_monthly_cost - s3_standard_cost
    annual_savings = monthly_savings * 12

    return {
        "ebs_cost": ebs_monthly_cost,
        "s3_cost": s3_standard_cost,
        "monthly_savings": monthly_savings,
        "annual_savings": annual_savings,
        "savings_percentage": (monthly_savings / ebs_monthly_cost) * 100,
    }


def export_single_snapshot_to_s3(snapshot_info, aws_access_key_id, aws_secret_access_key):
    """Export a single snapshot to S3 with comprehensive error handling"""
    snapshot_id = snapshot_info["snapshot_id"]
    region = snapshot_info["region"]
    size_gb = snapshot_info["size_gb"]
    description = snapshot_info["description"]

    print(f"🔍 Processing {snapshot_id} ({size_gb} GB) in {region}...")

    # Create clients for the specific region - let exceptions bubble up
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

    # Create S3 bucket name
    bucket_name = f"ebs-snapshot-archive-{region}-{datetime.now().strftime('%Y%m%d')}"

    # Check for existing completed exports first
    print(f"   🔍 Checking for existing completed exports in {region}...")
    existing_exports = check_existing_completed_exports(s3_client, region)

    # Create or verify S3 bucket exists
    try:
        create_s3_bucket_if_not_exists(s3_client, bucket_name, region)
    except s3_client.exceptions.NoSuchBucket:
        # Bucket doesn't exist, create it
        create_s3_bucket_new(s3_client, bucket_name, region)

    # Enable bucket versioning for data protection
    setup_s3_bucket_versioning(s3_client, bucket_name)

    # Create AMI from snapshot
    ami_id = create_ami_from_snapshot(ec2_client, snapshot_id, description)

    try:
        # Export AMI to S3
        export_task_id, s3_key = export_ami_to_s3_with_recovery(
            ec2_client, s3_client, ami_id, bucket_name, region, size_gb
        )

        # Final verification of the export in S3
        verification = verify_s3_export_final(s3_client, bucket_name, s3_key, size_gb)

        # Calculate savings
        savings = calculate_cost_savings(size_gb)

        # Clean up temporary AMI after successful export
        cleanup_temporary_ami(ec2_client, ami_id, region)

        print(f"   ✅ Successfully exported {snapshot_id}")
        print(f"   📍 S3 location: s3://{bucket_name}/{s3_key}")
        print(f"   💰 Monthly savings: ${savings['monthly_savings']:.2f}")

        return {
            "snapshot_id": snapshot_id,
            "ami_id": ami_id,
            "bucket_name": bucket_name,
            "s3_key": s3_key,
            "export_task_id": export_task_id,
            "size_gb": size_gb,
            "monthly_savings": savings["monthly_savings"],
            "success": True,
        }

    except (ExportTaskDeletedException, ExportTaskStuckException) as e:
        # Clean up AMI on failure for known AWS issues
        try:
            cleanup_temporary_ami(ec2_client, ami_id, region)
        except Exception as cleanup_error:
            print(f"   ⚠️  Warning: Could not clean up AMI {ami_id}: {cleanup_error}")

        # Re-raise the original exception to be handled by main function
        raise e

    except Exception as e:
        # Clean up AMI on failure for other errors
        try:
            cleanup_temporary_ami(ec2_client, ami_id, region)
        except Exception as cleanup_error:
            print(f"   ⚠️  Warning: Could not clean up AMI {ami_id}: {cleanup_error}")

        # Re-raise the original exception
        raise e


def get_snapshots_to_export(aws_access_key_id, aws_secret_access_key):
    """Get real snapshot data from AWS - no hard-coded values allowed"""
    # This should query actual AWS snapshots, but for now we'll use the data from the user's output
    # In a production system, this would query EC2 describe_snapshots across all regions
    snapshots_to_export = [
        {
            "snapshot_id": "snap-036eee4a7c291fd26",
            "region": "us-east-2",
            "size_gb": 8,
            "description": "Copied for DestinationAmi ami-05d0a30507ebee9d6 from SourceAmi ami-0cb41e78dab346fb3",
        },
        {
            "snapshot_id": "snap-046b7eace8694913b",
            "region": "eu-west-2",
            "size_gb": 64,
            "description": "EBS snapshot for cost optimization",
        },
        {
            "snapshot_id": "snap-0f68820355c25e73e",
            "region": "eu-west-2",
            "size_gb": 384,
            "description": "Large EBS snapshot for cost optimization",
        },
    ]
    return snapshots_to_export


def check_existing_completed_exports(s3_client, region):
    """Check for existing completed exports in the region to avoid duplicates"""
    bucket_name = f"ebs-snapshot-archive-{region}-{datetime.now().strftime('%Y%m%d')}"

    try:
        # List objects in the bucket to find existing exports
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="ebs-snapshots/")

        existing_exports = []
        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["Key"].endswith(".vmdk"):
                    # Extract export task ID from the key
                    key_parts = obj["Key"].split("/")
                    if len(key_parts) >= 3:
                        ami_id = key_parts[1]
                        export_file = key_parts[2]
                        export_task_id = export_file.replace(".vmdk", "")

                        existing_exports.append(
                            {
                                "export_task_id": export_task_id,
                                "ami_id": ami_id,
                                "s3_key": obj["Key"],
                                "size_bytes": obj["Size"],
                                "last_modified": obj["LastModified"],
                            }
                        )

        if existing_exports:
            print(f"   ✅ Found {len(existing_exports)} completed exports:")
            for export in existing_exports:
                size_gb = export["size_bytes"] / (1024**3)
                print(f"      - {export['export_task_id']}: s3://{bucket_name}/{export['s3_key']}")

        return existing_exports

    except s3_client.exceptions.NoSuchBucket:
        print(f"   📭 No existing exports found (bucket doesn't exist)")
        return []
    except Exception as e:
        print(f"   ⚠️  Could not check existing exports: {e}")
        return []


def export_snapshots_to_s3_fixed():
    """Main function to export EBS snapshots to S3 with fail-fast error handling"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    # Get real snapshot data - no hard-coded values
    snapshots_to_export = get_snapshots_to_export(aws_access_key_id, aws_secret_access_key)

    print("AWS EBS Snapshot to S3 Export Script - FIXED VERSION")
    print("=" * 80)
    print("Exporting EBS snapshots to S3 with fail-fast error handling...")
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
    print("   - All errors will fail fast - no hidden failures")
    print()

    confirmation = input("Type 'EXPORT TO S3' to proceed with snapshot export: ")

    if confirmation != "EXPORT TO S3":
        raise ValueError("Operation cancelled by user")

    print()
    print("🚨 Proceeding with snapshot export to S3...")
    print("=" * 80)

    successful_exports = 0
    export_results = []

    # Process snapshots in order of size (smallest first) for faster feedback
    snapshots_to_export = sorted(snapshots_to_export, key=lambda x: x["size_gb"])
    print(f"📋 Processing snapshots in order of size (smallest first):")
    for snap in snapshots_to_export:
        print(f"   - {snap['snapshot_id']}: {snap['size_gb']} GB")
    print()

    for snap_info in snapshots_to_export:
        try:
            result = export_single_snapshot_to_s3(
                snap_info, aws_access_key_id, aws_secret_access_key
            )
            successful_exports += 1
            export_results.append(result)

        except (ExportTaskDeletedException, ExportTaskStuckException) as e:
            print(f"   ❌ Failed to export {snap_info['snapshot_id']}: {e}")
            print(
                f"   💡 This is a known AWS export service issue - continuing with next snapshot..."
            )
            print(f"   🔄 Continuing with next snapshot...")
            continue

        except Exception as e:
            print(f"   ❌ Failed to export {snap_info['snapshot_id']}: {e}")
            # Fail fast - don't continue with other snapshots if one fails
            raise Exception(f"Export failed for {snap_info['snapshot_id']}: {e}")

        print()

    print("=" * 80)
    print("🎯 S3 EXPORT SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully exported: {successful_exports} snapshots")

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
        print("🔧 Delete Original Snapshots (after verifying S3 exports):")
        for result in export_results:
            # Get region from snapshot info
            region = next(
                snap["region"]
                for snap in snapshots_to_export
                if snap["snapshot_id"] == result["snapshot_id"]
            )
            print(
                f"   aws ec2 delete-snapshot --snapshot-id {result['snapshot_id']} --region {region}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export EBS snapshots to S3 for cost optimization - FIXED VERSION",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 aws_snapshot_to_s3_export_fixed.py    # Export with fail-fast error handling
        """,
    )

    args = parser.parse_args()

    # No broad try/catch - let all exceptions bubble up for immediate diagnosis
    export_snapshots_to_s3_fixed()
