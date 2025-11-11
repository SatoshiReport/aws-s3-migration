#!/usr/bin/env python3
"""
AWS S3 to EBS Snapshot Restore Script
Restores EBS snapshots from S3 exports when needed.
This script handles the reverse process of importing AMIs from S3 and creating snapshots.
"""

import sys
import time
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from cost_toolkit.common.credential_utils import setup_aws_credentials


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    return setup_aws_credentials()


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

    except ClientError as e:
        print(f"❌ Error listing S3 exports: {e}")
        return []

    return exports


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
        print("   ⏳ Monitoring import progress...")
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
                    if status == "deleted" or "failed" in status.lower():
                        error_msg = task.get("StatusMessage", "Unknown error")
                        print(f"   ❌ Import failed: {error_msg}")
                        return None

                    # Wait before checking again
                    time.sleep(60)  # Check every minute
                else:
                    print("   ❌ Import task not found")
                    return None

            except ClientError as e:
                print(f"   ❌ Error checking import status: {e}")
                time.sleep(60)

    except ClientError as e:
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
            except ClientError as e:
                print(f"   ⚠️  Warning: Could not tag snapshot: {e}")

            return root_snapshot_id

    except ClientError as e:
        print(f"   ❌ Error creating snapshot from AMI: {e}")
        return None

    print("   ❌ No root snapshot found in AMI")
    return None


def _get_user_inputs():
    """Get region and bucket name from user."""
    print("📋 Available regions with potential S3 exports:")
    print("   - eu-west-2 (London)")
    print("   - us-east-1 (N. Virginia)")
    print("   - us-east-2 (Ohio)")
    print()

    region = input("Enter the AWS region where your S3 exports are stored: ").strip()
    if not region:
        return None, None

    bucket_name = input("Enter the S3 bucket name containing exports: ").strip()
    if not bucket_name:
        return region, None

    return region, bucket_name


def _select_exports(exports):
    """Allow user to select which exports to restore."""
    print(f"✅ Found {len(exports)} export(s):")
    for i, export in enumerate(exports, 1):
        size_mb = export["size"] / (1024 * 1024)
        print(f"   {i}. {export['key']} ({size_mb:.1f} MB, {export['last_modified']})")

    print()
    selection = input(
        "Enter the number of the export to restore (or 'all' for all exports): "
    ).strip()

    if selection.lower() == "all":
        return exports

    try:
        index = int(selection) - 1
        if 0 <= index < len(exports):
            return [exports[index]]
    except ValueError:
        pass

    return None


def _process_export_restore(ec2_client, bucket_name, export):
    """Process restore of a single export."""
    s3_key = export["key"]
    print(f"🔍 Processing {s3_key}...")

    description = f"Restored from S3: {s3_key}"

    ami_id = import_ami_from_s3(ec2_client, bucket_name, s3_key, description)
    if not ami_id:
        print("   ❌ Failed to import AMI from S3")
        return None

    snapshot_id = create_snapshot_from_ami(ec2_client, ami_id, description)
    if not snapshot_id:
        print("   ❌ Failed to create snapshot from AMI")
        return None

    print(f"   ✅ Successfully restored to snapshot: {snapshot_id}")
    return {"s3_key": s3_key, "ami_id": ami_id, "snapshot_id": snapshot_id}


def _validate_user_inputs(region, bucket_name):
    """Validate user inputs for region and bucket."""
    if not region:
        print("❌ Region is required")
        return False
    if not bucket_name:
        print("❌ Bucket name is required")
        return False
    return True


def _create_aws_clients(aws_access_key_id, aws_secret_access_key, region):
    """Create EC2 and S3 clients for the specified region."""
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


def _get_and_validate_exports(s3_client, bucket_name):
    """Get exports from S3 and validate user selection."""
    print(f"\n🔍 Scanning S3 bucket {bucket_name} for exports...")
    exports = list_s3_exports(s3_client, bucket_name)

    if not exports:
        print("❌ No snapshot exports found in the specified bucket")
        return None

    selected_exports = _select_exports(exports)
    if not selected_exports:
        print("❌ Invalid selection")
        return None

    return selected_exports


def _confirm_restore_operation(selected_exports):
    """Confirm restore operation with user."""
    print(f"\n🎯 Restoring {len(selected_exports)} export(s)...")
    print()

    confirmation = input("Type 'RESTORE FROM S3' to proceed: ")
    if confirmation != "RESTORE FROM S3":
        print("❌ Operation cancelled")
        return False

    print("\n🚨 Proceeding with S3 restore...")
    print("=" * 80)
    return True


def _perform_restores(ec2_client, bucket_name, selected_exports):
    """Perform restore operations for selected exports."""
    restore_results = []
    for export in selected_exports:
        result = _process_export_restore(ec2_client, bucket_name, export)
        if result:
            restore_results.append(result)
        print()
    return restore_results


def _print_restore_summary(restore_results, selected_exports, region):
    """Print summary of restore operations."""
    print("=" * 80)
    print("🎯 RESTORE SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully restored: {len(restore_results)} snapshots")
    print(f"❌ Failed to restore: {len(selected_exports) - len(restore_results)} exports")

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


def restore_snapshots_from_s3():
    """Main function to restore EBS snapshots from S3"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    print("AWS S3 to EBS Snapshot Restore Script")
    print("=" * 80)
    print("Restoring EBS snapshots from S3 exports...")
    print()

    region, bucket_name = _get_user_inputs()
    if not _validate_user_inputs(region, bucket_name):
        return

    ec2_client, s3_client = _create_aws_clients(aws_access_key_id, aws_secret_access_key, region)

    selected_exports = _get_and_validate_exports(s3_client, bucket_name)
    if not selected_exports:
        return

    if not _confirm_restore_operation(selected_exports):
        return

    restore_results = _perform_restores(ec2_client, bucket_name, selected_exports)
    _print_restore_summary(restore_results, selected_exports, region)


if __name__ == "__main__":
    try:
        restore_snapshots_from_s3()
    except (ClientError, KeyboardInterrupt) as e:
        print(f"❌ Script failed: {e}")
        sys.exit(1)
