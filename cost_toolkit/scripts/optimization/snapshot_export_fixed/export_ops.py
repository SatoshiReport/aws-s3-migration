"""Export operations with fail-fast error handling"""

import os
from datetime import datetime

from dotenv import load_dotenv

from . import constants
from .constants import ExportTaskDeletedException


def load_aws_credentials():
    """Load AWS credentials from .env file - fail fast if missing"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError(  # noqa: TRY003
            "AWS credentials not found in ~/.env file - cannot proceed"
        )
    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def create_s3_bucket_if_not_exists(s3_client, bucket_name, region):
    """Create S3 bucket if it doesn't exist - fail fast on errors"""
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
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ami_name = f"export-{snapshot_id}-{timestamp}"

    print(f"   🔄 Creating AMI from snapshot {snapshot_id}...")

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

    print(f"   ⏳ Waiting for AMI {ami_id} to become available...")
    waiter = ec2_client.get_waiter("image_available")
    waiter.wait(
        ImageIds=[ami_id],
        WaiterConfig={
            "Delay": constants.AMI_CREATION_CHECK_INTERVAL_SECONDS,
            "MaxAttempts": (constants.AMI_CREATION_MAX_WAIT_MINUTES * 60)
            // constants.AMI_CREATION_CHECK_INTERVAL_SECONDS,
        },
    )
    print(f"   ✅ AMI {ami_id} is now available")

    return ami_id


def validate_export_task_exists(ec2_client, export_task_id):
    """Validate that export task still exists - raise exception if deleted"""
    response = ec2_client.describe_export_image_tasks(ExportImageTaskIds=[export_task_id])

    if not response["ExportImageTasks"]:
        raise ExportTaskDeletedException(  # noqa: TRY003
            f"Export task {export_task_id} no longer exists - was deleted"
        )

    return response["ExportImageTasks"][0]
