#!/usr/bin/env python3
"""
AWS S3 to EBS Snapshot Restore Script
Restores EBS snapshots from S3 exports when needed.
This script handles the reverse process of importing AMIs from S3 and creating snapshots.
"""

import json
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


def list_s3_exports(s3_client, bucket_name):
    """List available snapshot exports in S3 bucket"""
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="ebs-snapshots/")

        exports = []
        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["Key"].endswith(".vmdk") or obj["Key"].endswith(".raw"):
                    exports.append(
                        {
                            "key": obj["Key"],
                            "size": obj["Size"],
                            "last_modified": obj["LastModified"],
                        }
                    )

        return exports
    except Exception as e:
        print(f"❌ Error listing S3 exports: {e}")
        return []


def import_ami_from_s3(ec2_client, s3_bucket, s3_key, description):
    """Import AMI from S3 export"""
    try:
        print(f"   🔄 Importing AMI from s3://{s3_bucket}/{s3_key}...")

        # Start import task
        response = ec2_client.import_image(
            Description=description,
            DiskContainers=[
                {
                    "Description": f"Restored from S3: {s3_key}",
                    "Format": "VMDK",  # or 'RAW', 'VHD' depending on export format
                    "UserBucket": {"S3Bucket": s3_bucket, "S3Key": s3_key},
                }
            ],
        )

        import_task_id = response["ImportTaskId"]
        print(f"   ✅ Started import task: {import_task_id}")

        # Monitor import progress
        print(f"   ⏳ Monitoring import progress...")
        while True:
            try:
                status_response = ec2_client.describe_import_image_tasks(
                    ImportTaskIds=[import_task_id]
                )

                if status_response["ImportImageTasks"]:
                    task = status_response["ImportImageTasks"][0]
                    status = task["Status"]
                    progress = task.get("Progress", "N/A")

                    print(f"   📊 Import status: {status}, Progress: {progress}")

                    if status == "completed":
                        ami_id = task["ImageId"]
                        print(f"   ✅ Import completed! AMI ID: {ami_id}")
                        return ami_id
                    elif status == "deleted" or "failed" in status.lower():
                        error_msg = task.get("StatusMessage", "Unknown error")
                        print(f"   ❌ Import failed: {error_msg}")
                        return None

                    # Wait before checking again
                    time.sleep(60)  # Check every minute
                else:
                    print(f"   ❌ Import task not found")
                    return None

            except Exception as e:
                print(f"   ❌ Error checking import status: {e}")
                time.sleep(60)

    except Exception as e:
        print(f"   ❌ Error importing from S3: {e}")
        return None


def create_snapshot_from_ami(ec2_client, ami_id, description):
    """Create EBS snapshot from imported AMI"""
    try:
        print(f"   🔄 Creating snapshot from AMI {ami_id}...")

        # Get AMI details to find the root snapshot
        response = ec2_client.describe_images(ImageIds=[ami_id])
        if not response["Images"]:
            print(f"   ❌ AMI {ami_id} not found")
            return None

        ami = response["Images"][0]

        # Find root device mapping
        root_device_name = ami.get("RootDeviceName", "/dev/sda1")
        root_snapshot_id = None

        for mapping in ami.get("BlockDeviceMappings", []):
            if mapping["DeviceName"] == root_device_name and "Ebs" in mapping:
                root_snapshot_id = mapping["Ebs"]["SnapshotId"]
                break

        if root_snapshot_id:
            print(f"   ✅ Found root snapshot: {root_snapshot_id}")

            # Add tags to the snapshot for identification
            try:
                ec2_client.create_tags(
                    Resources=[root_snapshot_id],
                    Tags=[
                        {
                            "Key": "Name",
                            "Value": f'Restored-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
                        },
                        {"Key": "Source", "Value": "S3-Import"},
                        {"Key": "OriginalDescription", "Value": description},
                    ],
                )
                print(f"   ✅ Tagged snapshot {root_snapshot_id}")
            except Exception as e:
                print(f"   ⚠️  Warning: Could not tag snapshot: {e}")

            return root_snapshot_id
        else:
            print(f"   ❌ No root snapshot found in AMI")
            return None

    except Exception as e:
        print(f"   ❌ Error creating snapshot from AMI: {e}")
        return None


def restore_snapshots_from_s3():
    """Main function to restore EBS snapshots from S3"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    print("AWS S3 to EBS Snapshot Restore Script")
    print("=" * 80)
    print("Restoring EBS snapshots from S3 exports...")
    print()

    # Get bucket information from user
    print("📋 Available regions with potential S3 exports:")
    print("   - eu-west-2 (London)")
    print("   - us-east-1 (N. Virginia)")
    print("   - us-east-2 (Ohio)")
    print()

    region = input("Enter the AWS region where your S3 exports are stored: ").strip()
    if not region:
        print("❌ Region is required")
        return

    bucket_name = input("Enter the S3 bucket name containing exports: ").strip()
    if not bucket_name:
        print("❌ Bucket name is required")
        return

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

    # List available exports
    print(f"\n🔍 Scanning S3 bucket {bucket_name} for exports...")
    exports = list_s3_exports(s3_client, bucket_name)

    if not exports:
        print("❌ No snapshot exports found in the specified bucket")
        return

    print(f"✅ Found {len(exports)} export(s):")
    for i, export in enumerate(exports, 1):
        size_mb = export["size"] / (1024 * 1024)
        print(f"   {i}. {export['key']} ({size_mb:.1f} MB, {export['last_modified']})")

    print()
    selection = input(
        "Enter the number of the export to restore (or 'all' for all exports): "
    ).strip()

    if selection.lower() == "all":
        selected_exports = exports
    else:
        try:
            index = int(selection) - 1
            if 0 <= index < len(exports):
                selected_exports = [exports[index]]
            else:
                print("❌ Invalid selection")
                return
        except ValueError:
            print("❌ Invalid selection")
            return

    print(f"\n🎯 Restoring {len(selected_exports)} export(s)...")
    print()

    confirmation = input("Type 'RESTORE FROM S3' to proceed: ")
    if confirmation != "RESTORE FROM S3":
        print("❌ Operation cancelled")
        return

    print("\n🚨 Proceeding with S3 restore...")
    print("=" * 80)

    successful_restores = 0
    failed_restores = 0
    restore_results = []

    for export in selected_exports:
        s3_key = export["key"]
        print(f"🔍 Processing {s3_key}...")

        # Extract description from key if possible
        description = f"Restored from S3: {s3_key}"

        # Import AMI from S3
        ami_id = import_ami_from_s3(ec2_client, bucket_name, s3_key, description)

        if ami_id:
            # Create snapshot from AMI
            snapshot_id = create_snapshot_from_ami(ec2_client, ami_id, description)

            if snapshot_id:
                successful_restores += 1
                restore_results.append(
                    {"s3_key": s3_key, "ami_id": ami_id, "snapshot_id": snapshot_id}
                )
                print(f"   ✅ Successfully restored to snapshot: {snapshot_id}")
            else:
                failed_restores += 1
                print(f"   ❌ Failed to create snapshot from AMI")
        else:
            failed_restores += 1
            print(f"   ❌ Failed to import AMI from S3")

        print()

    print("=" * 80)
    print("🎯 RESTORE SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully restored: {successful_restores} snapshots")
    print(f"❌ Failed to restore: {failed_restores} exports")

    if restore_results:
        print("\n📋 Restore Results:")
        for result in restore_results:
            print(f"   {result['s3_key']} → {result['snapshot_id']}")

        print("\n📝 Next Steps:")
        print("1. Verify restored snapshots in EC2 console")
        print("2. Test snapshot functionality by creating volumes")
        print("3. Clean up temporary AMIs if no longer needed")
        print("\n🔧 Cleanup Commands (optional):")
        for result in restore_results:
            print(f"   aws ec2 deregister-image --image-id {result['ami_id']} --region {region}")


if __name__ == "__main__":
    try:
        restore_snapshots_from_s3()
    except Exception as e:
        print(f"❌ Script failed: {e}")
        exit(1)
