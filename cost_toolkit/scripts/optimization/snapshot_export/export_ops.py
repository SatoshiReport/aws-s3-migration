"""Export operations for AMI to S3"""

import os
from datetime import datetime

from botocore.exceptions import ClientError
from dotenv import load_dotenv

MAX_EXPORT_HOURS = 8
MAX_EXPORT_STATUS_ERRORS = 5


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
        return True  # noqa: TRY300
    except:
        try:
            if region == "us-east-1":
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region}
                )
            print(f"   ✅ Created S3 bucket: {bucket_name}")
        except ClientError as e:
            print(f"   ❌ Error creating bucket {bucket_name}: {e}")
            return False

        return True


def setup_s3_bucket_versioning(s3_client, bucket_name):
    """Enable S3 bucket versioning for data protection"""
    try:
        s3_client.put_bucket_versioning(
            Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
        )
        print(f"   ✅ Enabled versioning for {bucket_name}")
    except ClientError as e:
        print(f"   ❌ Error enabling versioning: {e}")
        return False

    return True


def create_ami_from_snapshot(ec2_client, snapshot_id, snapshot_description):
    """Create an AMI from an EBS snapshot"""
    try:
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
            WaiterConfig={"Delay": 30, "MaxAttempts": 40},
        )
        print(f"   ✅ AMI {ami_id} is now available")

    except ClientError as e:
        print(f"   ❌ Error creating AMI from snapshot {snapshot_id}: {e}")
        return None

    return ami_id


def export_ami_to_s3(ec2_client, s3_client, ami_id, bucket_name, region, snapshot_size_gb):
    """Export AMI to S3 bucket with multi-signal completion detection"""
    from .export_helpers import ExportContext, _start_ami_export, monitor_export_status

    try:
        export_task_id = _start_ami_export(ec2_client, ami_id, bucket_name)
        context = ExportContext(
            ec2_client=ec2_client,
            s3_client=s3_client,
            ami_id=ami_id,
            bucket_name=bucket_name,
            export_task_id=export_task_id,
            snapshot_size_gb=snapshot_size_gb,
        )
        return monitor_export_status(
            context,
            max_export_hours=MAX_EXPORT_HOURS,
            max_errors=MAX_EXPORT_STATUS_ERRORS,
        )

    except ClientError as e:
        print(f"   ❌ Error exporting AMI {ami_id}: {e}")
        return None, None
