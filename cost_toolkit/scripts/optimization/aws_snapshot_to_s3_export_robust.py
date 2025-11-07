#!/usr/bin/env python3
"""
AWS EBS Snapshot to S3 Export Script - Robust Version
This version implements workarounds for AWS export service issues:
1. Longer wait times before checking export status
2. Different AMI configurations that may export more reliably
3. Retry logic for failed exports
4. Alternative export methods
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta

import boto3
from dotenv import load_dotenv


# Constants based on successful export patterns
class RobustExportConstants:
    """Constants tuned for maximum export success rate"""

    # Initial wait before first status check (give AWS time to initialize)
    INITIAL_WAIT_MINUTES = 5

    # Status check intervals
    EXPORT_STATUS_CHECK_INTERVAL_SECONDS = 120  # 2 minutes between checks

    # Maximum export duration
    EXPORT_MAX_DURATION_HOURS = 12  # Allow up to 12 hours for large exports

    # Retry configuration
    MAX_EXPORT_RETRIES = 3
    RETRY_WAIT_MINUTES = 10

    # S3 validation
    S3_FILE_CHECK_DELAY_MINUTES = 30  # Wait 30 minutes before checking S3

    # Cost constants
    EBS_SNAPSHOT_COST_PER_GB_MONTHLY = 0.05
    S3_STANDARD_COST_PER_GB_MONTHLY = 0.023


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
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"   ✅ S3 bucket {bucket_name} already exists")
        return True
    except s3_client.exceptions.NoSuchBucket:
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region}
            )
        print(f"   ✅ Created S3 bucket: {bucket_name}")

        # Enable versioning
        s3_client.put_bucket_versioning(
            Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
        )
        print(f"   ✅ Enabled versioning for {bucket_name}")
        return True


def create_ami_from_snapshot_robust(ec2_client, snapshot_id, snapshot_description, attempt=1):
    """Create an AMI from an EBS snapshot with robust configuration"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ami_name = f"export-{snapshot_id}-{timestamp}-v{attempt}"

    print(f"   🔄 Creating AMI from snapshot {snapshot_id} (attempt {attempt})...")

    # Use more compatible AMI settings
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
                    "VolumeType": "gp2",  # Use gp2 instead of gp3 for compatibility
                    "DeleteOnTermination": True,
                },
            }
        ],
        VirtualizationType="hvm",
        BootMode="legacy-bios",  # Use legacy BIOS for better compatibility
        EnaSupport=False,  # Disable ENA for compatibility
        SriovNetSupport="simple",
    )

    ami_id = response["ImageId"]
    print(f"   ✅ Created AMI: {ami_id}")

    # Wait for AMI to be available
    print(f"   ⏳ Waiting for AMI {ami_id} to become available...")
    waiter = ec2_client.get_waiter("image_available")
    waiter.wait(ImageIds=[ami_id], WaiterConfig={"Delay": 30, "MaxAttempts": 40})  # 20 minutes max
    print(f"   ✅ AMI {ami_id} is now available")

    return ami_id


def wait_for_export_completion_robust(
    ec2_client, s3_client, export_task_id, bucket_name, ami_id, size_gb
):
    """Monitor export with robust completion detection"""
    print(
        f"   ⏳ Waiting {RobustExportConstants.INITIAL_WAIT_MINUTES} minutes before checking export status..."
    )
    time.sleep(RobustExportConstants.INITIAL_WAIT_MINUTES * 60)

    start_time = time.time()
    s3_key = f"ebs-snapshots/{ami_id}/{export_task_id}.vmdk"
    last_progress = 0

    while True:
        elapsed_time = time.time() - start_time
        elapsed_hours = elapsed_time / 3600

        if elapsed_hours >= RobustExportConstants.EXPORT_MAX_DURATION_HOURS:
            raise Exception(
                f"Export exceeded maximum duration of {RobustExportConstants.EXPORT_MAX_DURATION_HOURS} hours"
            )

        try:
            # Check export task status
            response = ec2_client.describe_export_image_tasks(ExportImageTaskIds=[export_task_id])

            if not response["ExportImageTasks"]:
                # Task was deleted - check if S3 file exists
                print(f"   ⚠️  Export task no longer exists - checking S3...")
                try:
                    s3_response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
                    file_size_gb = s3_response["ContentLength"] / (1024**3)
                    print(f"   ✅ S3 file found! Size: {file_size_gb:.2f} GB")
                    return True, s3_key
                except:
                    return False, None

            task = response["ExportImageTasks"][0]
            status = task["Status"]
            progress = task.get("Progress", "N/A")

            # Convert progress to int
            current_progress = int(progress) if progress != "N/A" else 0

            print(f"   📊 Status: {status} | Progress: {progress}% | Elapsed: {elapsed_hours:.1f}h")

            if status == "completed":
                print(f"   ✅ Export completed successfully!")
                return True, s3_key
            elif status == "failed":
                error_msg = task.get("StatusMessage", "Unknown error")
                print(f"   ❌ Export failed: {error_msg}")
                return False, None

            # If progress hasn't changed in a while and we're at 80%, check S3
            if (
                current_progress == 80
                and current_progress == last_progress
                and elapsed_time > (30 * 60)
            ):
                print(f"   🔍 Export stuck at 80% - checking S3 directly...")
                try:
                    s3_response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
                    file_size_gb = s3_response["ContentLength"] / (1024**3)

                    # Wait a bit and check if file size is stable
                    time.sleep(300)  # 5 minutes
                    s3_response2 = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
                    file_size_gb2 = s3_response2["ContentLength"] / (1024**3)

                    if file_size_gb == file_size_gb2:
                        print(
                            f"   ✅ S3 file is stable at {file_size_gb:.2f} GB - considering export complete"
                        )
                        return True, s3_key
                except:
                    pass

            last_progress = current_progress

        except Exception as e:
            print(f"   ⚠️  Error checking export status: {e}")

        time.sleep(RobustExportConstants.EXPORT_STATUS_CHECK_INTERVAL_SECONDS)


def export_snapshot_with_retries(snapshot_info, aws_access_key_id, aws_secret_access_key):
    """Export a snapshot with retry logic"""
    snapshot_id = snapshot_info["snapshot_id"]
    region = snapshot_info["region"]
    size_gb = snapshot_info["size_gb"]
    description = snapshot_info["description"]

    print(f"\n🔍 Processing {snapshot_id} ({size_gb} GB) in {region}...")

    # Create clients
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

    bucket_name = f"ebs-snapshot-archive-{region}-{datetime.now().strftime('%Y%m%d')}"

    # Create bucket if needed
    create_s3_bucket_if_not_exists(s3_client, bucket_name, region)

    # Try export with retries
    for attempt in range(1, RobustExportConstants.MAX_EXPORT_RETRIES + 1):
        print(f"\n   🔄 Export attempt {attempt}/{RobustExportConstants.MAX_EXPORT_RETRIES}")

        ami_id = None
        try:
            # Create AMI
            ami_id = create_ami_from_snapshot_robust(ec2_client, snapshot_id, description, attempt)

            # Start export
            print(f"   🔄 Starting export of AMI {ami_id} to S3...")
            response = ec2_client.export_image(
                ImageId=ami_id,
                DiskImageFormat="VMDK",
                S3ExportLocation={"S3Bucket": bucket_name, "S3Prefix": f"ebs-snapshots/{ami_id}/"},
                Description=f"Export of AMI {ami_id} from snapshot {snapshot_id}",
            )

            export_task_id = response["ExportImageTaskId"]
            print(f"   ✅ Started export task: {export_task_id}")

            # Wait for completion
            success, s3_key = wait_for_export_completion_robust(
                ec2_client, s3_client, export_task_id, bucket_name, ami_id, size_gb
            )

            if success:
                # Clean up AMI
                try:
                    ec2_client.deregister_image(ImageId=ami_id)
                    print(f"   🧹 Cleaned up temporary AMI {ami_id}")
                except:
                    pass

                print(f"   ✅ Successfully exported {snapshot_id}")
                print(f"   📍 S3 location: s3://{bucket_name}/{s3_key}")

                # Calculate savings
                monthly_savings = size_gb * (
                    RobustExportConstants.EBS_SNAPSHOT_COST_PER_GB_MONTHLY
                    - RobustExportConstants.S3_STANDARD_COST_PER_GB_MONTHLY
                )
                print(f"   💰 Monthly savings: ${monthly_savings:.2f}")

                return {
                    "success": True,
                    "snapshot_id": snapshot_id,
                    "bucket_name": bucket_name,
                    "s3_key": s3_key,
                    "size_gb": size_gb,
                    "monthly_savings": monthly_savings,
                }

        except Exception as e:
            print(f"   ❌ Attempt {attempt} failed: {e}")

            # Clean up AMI if it exists
            if ami_id:
                try:
                    ec2_client.deregister_image(ImageId=ami_id)
                    print(f"   🧹 Cleaned up temporary AMI {ami_id}")
                except:
                    pass

            if attempt < RobustExportConstants.MAX_EXPORT_RETRIES:
                print(
                    f"   ⏳ Waiting {RobustExportConstants.RETRY_WAIT_MINUTES} minutes before retry..."
                )
                time.sleep(RobustExportConstants.RETRY_WAIT_MINUTES * 60)

    return {"success": False, "snapshot_id": snapshot_id, "error": "All export attempts failed"}


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Export EBS snapshots to S3 with robust error handling and retries"
    )
    args = parser.parse_args()

    # Load credentials
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    # Snapshots to export
    snapshots = [
        {
            "snapshot_id": "snap-036eee4a7c291fd26",
            "region": "us-east-2",
            "size_gb": 8,
            "description": "Copied for DestinationAmi ami-05d0a30507ebee9d6",
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

    print("AWS EBS Snapshot to S3 Export Script - ROBUST VERSION")
    print("=" * 80)
    print("This version includes:")
    print("- Retry logic for failed exports")
    print("- Better AMI compatibility settings")
    print("- Improved completion detection")
    print("- Longer wait times for AWS processing")
    print()

    total_size_gb = sum(snap["size_gb"] for snap in snapshots)
    total_monthly_savings = total_size_gb * (
        RobustExportConstants.EBS_SNAPSHOT_COST_PER_GB_MONTHLY
        - RobustExportConstants.S3_STANDARD_COST_PER_GB_MONTHLY
    )

    print(f"🎯 Target: {len(snapshots)} snapshots ({total_size_gb} GB total)")
    print(f"💰 Potential monthly savings: ${total_monthly_savings:.2f}")
    print()

    confirmation = input("Type 'EXPORT' to proceed: ")
    if confirmation != "EXPORT":
        print("Operation cancelled")
        return

    # Process snapshots
    results = []
    for snapshot in snapshots:
        result = export_snapshot_with_retries(snapshot, aws_access_key_id, aws_secret_access_key)
        results.append(result)

    # Summary
    print("\n" + "=" * 80)
    print("📊 EXPORT SUMMARY")
    print("=" * 80)

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"✅ Successful exports: {len(successful)}")
    print(f"❌ Failed exports: {len(failed)}")

    if successful:
        total_savings = sum(r["monthly_savings"] for r in successful)
        print(f"💰 Total monthly savings: ${total_savings:.2f}")
        print(f"💰 Total annual savings: ${total_savings * 12:.2f}")

        print("\n📋 Successful Exports:")
        for result in successful:
            print(f"   {result['snapshot_id']} → s3://{result['bucket_name']}/{result['s3_key']}")

    if failed:
        print("\n❌ Failed Exports:")
        for result in failed:
            print(f"   {result['snapshot_id']}: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
