"""Robust export operations with retry logic"""

import os
import sys
import time
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Constants tuned for maximum export success rate
INITIAL_WAIT_MINUTES = 5
EXPORT_STATUS_CHECK_INTERVAL_SECONDS = 120
EXPORT_MAX_DURATION_HOURS = 12
MAX_EXPORT_RETRIES = 3
RETRY_WAIT_MINUTES = 10
S3_FILE_CHECK_DELAY_MINUTES = 30
EBS_SNAPSHOT_COST_PER_GB_MONTHLY = 0.05
S3_STANDARD_COST_PER_GB_MONTHLY = 0.023


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")  # noqa: TRY003

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def create_s3_bucket_if_not_exists(s3_client, bucket_name, region):
    """Create S3 bucket if it doesn't exist"""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"   ✅ S3 bucket {bucket_name} already exists")
    except s3_client.exceptions.NoSuchBucket:
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region}
            )
        print(f"   ✅ Created S3 bucket: {bucket_name}")

        s3_client.put_bucket_versioning(
            Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
        )
        print(f"   ✅ Enabled versioning for {bucket_name}")
        return True

    return True


def create_ami_from_snapshot_robust(ec2_client, snapshot_id, snapshot_description, attempt=1):
    """Create an AMI from an EBS snapshot with robust configuration"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ami_name = f"export-{snapshot_id}-{timestamp}-v{attempt}"

    print(f"   🔄 Creating AMI from snapshot {snapshot_id} (attempt {attempt})...")

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
                    "VolumeType": "gp2",
                    "DeleteOnTermination": True,
                },
            }
        ],
        VirtualizationType="hvm",
        BootMode="legacy-bios",
        EnaSupport=False,
        SriovNetSupport="simple",
    )

    ami_id = response["ImageId"]
    print(f"   ✅ Created AMI: {ami_id}")

    print(f"   ⏳ Waiting for AMI {ami_id} to become available...")
    waiter = ec2_client.get_waiter("image_available")
    waiter.wait(ImageIds=[ami_id], WaiterConfig={"Delay": 30, "MaxAttempts": 40})
    print(f"   ✅ AMI {ami_id} is now available")

    return ami_id


def wait_for_export_completion_robust(
    ec2_client, s3_client, export_task_id, bucket_name, ami_id, size_gb
):
    """Monitor export with robust completion detection"""
    from .export_helpers import wait_for_export_completion_robust as wait_helper

    return wait_helper(
        ec2_client, s3_client, export_task_id, bucket_name, ami_id, size_gb, sys.modules[__name__]
    )


def _create_clients_for_export(region, aws_access_key_id, aws_secret_access_key):
    """Create EC2 and S3 clients for export operations"""
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

    return ec2_client, s3_client


def _initiate_export_task(ec2_client, ami_id, bucket_name, snapshot_id):
    """Start the export image task"""
    print(f"   🔄 Starting export of AMI {ami_id} to S3...")
    response = ec2_client.export_image(
        ImageId=ami_id,
        DiskImageFormat="VMDK",
        S3ExportLocation={"S3Bucket": bucket_name, "S3Prefix": f"ebs-snapshots/{ami_id}/"},
        Description=f"Export of AMI {ami_id} from snapshot {snapshot_id}",
    )

    export_task_id = response["ExportImageTaskId"]
    print(f"   ✅ Started export task: {export_task_id}")
    return export_task_id


def _build_success_result(snapshot_id, bucket_name, s3_key, size_gb):
    """Build successful export result dictionary"""
    monthly_savings = size_gb * (EBS_SNAPSHOT_COST_PER_GB_MONTHLY - S3_STANDARD_COST_PER_GB_MONTHLY)

    print(f"   ✅ Successfully exported {snapshot_id}")
    print(f"   📍 S3 location: s3://{bucket_name}/{s3_key}")
    print(f"   💰 Monthly savings: ${monthly_savings:.2f}")

    return {
        "success": True,
        "snapshot_id": snapshot_id,
        "bucket_name": bucket_name,
        "s3_key": s3_key,
        "size_gb": size_gb,
        "monthly_savings": monthly_savings,
    }


def _handle_export_attempt(
    ec2_client, s3_client, snapshot_id, description, bucket_name, size_gb, attempt
):
    """Execute a single export attempt"""
    from .monitoring import cleanup_ami_safe

    ami_id = create_ami_from_snapshot_robust(ec2_client, snapshot_id, description, attempt)
    export_task_id = _initiate_export_task(ec2_client, ami_id, bucket_name, snapshot_id)

    success, s3_key = wait_for_export_completion_robust(
        ec2_client, s3_client, export_task_id, bucket_name, ami_id, size_gb
    )

    cleanup_ami_safe(ec2_client, ami_id)

    if success:
        return _build_success_result(snapshot_id, bucket_name, s3_key, size_gb)

    return None


def export_snapshot_with_retries(snapshot_info, aws_access_key_id, aws_secret_access_key):
    """Export a snapshot with retry logic"""
    from .monitoring import cleanup_ami_safe

    snapshot_id = snapshot_info["snapshot_id"]
    region = snapshot_info["region"]
    size_gb = snapshot_info["size_gb"]
    description = snapshot_info["description"]

    print(f"\n🔍 Processing {snapshot_id} ({size_gb} GB) in {region}...")

    ec2_client, s3_client = _create_clients_for_export(
        region, aws_access_key_id, aws_secret_access_key
    )

    bucket_name = f"ebs-snapshot-archive-{region}-{datetime.now().strftime('%Y%m%d')}"
    create_s3_bucket_if_not_exists(s3_client, bucket_name, region)

    for attempt in range(1, MAX_EXPORT_RETRIES + 1):
        print(f"\n   🔄 Export attempt {attempt}/{MAX_EXPORT_RETRIES}")

        ami_id = None
        try:
            result = _handle_export_attempt(
                ec2_client, s3_client, snapshot_id, description, bucket_name, size_gb, attempt
            )

            if result:
                return result

        except ClientError as e:
            print(f"   ❌ Attempt {attempt} failed: {e}")

            if ami_id:
                cleanup_ami_safe(ec2_client, ami_id)

            if attempt < MAX_EXPORT_RETRIES:
                print(f"   ⏳ Waiting {RETRY_WAIT_MINUTES} minutes " "before retry...")
                time.sleep(RETRY_WAIT_MINUTES * 60)

    return {"success": False, "snapshot_id": snapshot_id, "error": "All export attempts failed"}
