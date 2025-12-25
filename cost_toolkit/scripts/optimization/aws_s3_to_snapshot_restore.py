#!/usr/bin/env python3
"""
AWS S3 to EBS Snapshot Restore Script
Restores EBS snapshots from S3 exports when needed.
This script handles the reverse process of importing AMIs from S3 and creating snapshots.
"""

import sys
from datetime import datetime
from threading import Event

import boto3
from botocore.exceptions import ClientError

from cost_toolkit.common.credential_utils import setup_aws_credentials

_WAIT_EVENT = Event()


class S3ExportError(Exception):
    """Raised when S3 export operations fail."""


class AMIImportError(Exception):
    """Raised when AMI import operations fail."""


class SnapshotCreationError(Exception):
    """Raised when snapshot creation from AMI fails."""


def list_s3_exports(s3_client, bucket_name):
    """List available snapshot exports in S3 bucket.

    Raises:
        S3ExportError: If the S3 API call fails.
    """
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="ebs-snapshots/")
    except ClientError as e:
        print(f"   ❌ Error listing S3 exports: {e}")
        raise S3ExportError(f"Failed to list S3 exports in {bucket_name}: {e}") from e

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


def import_ami_from_s3(ec2_client, s3_bucket, s3_key, description):
    """Import AMI from S3 export.

    Raises:
        AMIImportError: If the import fails.
    """
    print(f"   🔄 Importing AMI from s3://{s3_bucket}/{s3_key}...")

    try:
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
    except ClientError as e:
        raise AMIImportError(f"Failed to start AMI import from s3://{s3_bucket}/{s3_key}: {e}") from e

    import_task_id = response["ImportTaskId"]
    print(f"   ✅ Started import task: {import_task_id}")

    # Monitor import progress
    print("   ⏳ Monitoring import progress...")
    while True:
        try:
            status_response = ec2_client.describe_import_image_tasks(ImportTaskIds=[import_task_id])
        except ClientError as e:
            raise AMIImportError(f"Failed to check import status for task {import_task_id}: {e}") from e

        if not status_response["ImportImageTasks"]:
            raise AMIImportError(f"Import task {import_task_id} not found")

        task = status_response["ImportImageTasks"][0]
        status = task["Status"]
        progress = task.get("Progress") or "N/A"

        print(f"   📊 Import status: {status}, Progress: {progress}")

        if status == "completed":
            ami_id = task["ImageId"]
            print(f"   ✅ Import completed! AMI ID: {ami_id}")
            return ami_id

        if status == "deleted" or "failed" in status.lower():
            error_msg = task.get("StatusMessage") or "Unknown error"
            raise AMIImportError(f"Import task {import_task_id} failed: {error_msg}")

        # Wait before checking again
        _WAIT_EVENT.wait(60)


def create_snapshot_from_ami(ec2_client, ami_id, description):
    """Create EBS snapshot from imported AMI.

    Raises:
        SnapshotCreationError: If snapshot creation fails.
    """
    print(f"   🔄 Creating snapshot from AMI {ami_id}...")

    try:
        response = ec2_client.describe_images(ImageIds=[ami_id])
    except ClientError as e:
        raise SnapshotCreationError(f"Failed to describe AMI {ami_id}: {e}") from e

    if not response["Images"]:
        raise SnapshotCreationError(f"AMI {ami_id} not found")

    ami = response["Images"][0]

    # Find root device mapping
    root_device_name = ami["RootDeviceName"]
    root_snapshot_id = None

    for mapping in ami["BlockDeviceMappings"]:
        if mapping["DeviceName"] == root_device_name and "Ebs" in mapping:
            root_snapshot_id = mapping["Ebs"]["SnapshotId"]
            break

    if not root_snapshot_id:
        raise SnapshotCreationError(f"No root snapshot found in AMI {ami_id}")

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
    selection = input("Enter the number of the export to restore (or 'all' for all exports): ").strip()

    if selection.lower() == "all":
        return exports

    try:
        index = int(selection) - 1
    except ValueError as e:
        raise ValueError(f"Invalid selection '{selection}': not a number") from e

    if not 0 <= index < len(exports):
        raise ValueError(f"Selection {selection} out of range (1-{len(exports)})")

    return [exports[index]]


def _process_export_restore(ec2_client, bucket_name, export):
    """Process restore of a single export.

    Returns:
        dict with s3_key, ami_id, snapshot_id on success, None on failure
    """
    s3_key = export["key"]
    print(f"🔍 Processing {s3_key}...")

    description = f"Restored from S3: {s3_key}"

    try:
        ami_id = import_ami_from_s3(ec2_client, bucket_name, s3_key, description)
        snapshot_id = create_snapshot_from_ami(ec2_client, ami_id, description)
    except (AMIImportError, SnapshotCreationError) as e:
        print(f"   ❌ Restore failed: {e}")
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
    """Get exports from S3 and validate user selection.

    Raises:
        ValueError: If user selection is invalid
    """
    print(f"\n🔍 Scanning S3 bucket {bucket_name} for exports...")
    exports = list_s3_exports(s3_client, bucket_name)

    if not exports:
        raise ValueError("No snapshot exports found in the specified bucket")

    return _select_exports(exports)


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
    aws_access_key_id, aws_secret_access_key = setup_aws_credentials()

    print("AWS S3 to EBS Snapshot Restore Script")
    print("=" * 80)
    print("Restoring EBS snapshots from S3 exports...")
    print()

    region, bucket_name = _get_user_inputs()
    if not _validate_user_inputs(region, bucket_name):
        return

    ec2_client, s3_client = _create_aws_clients(aws_access_key_id, aws_secret_access_key, region)

    selected_exports = _get_and_validate_exports(s3_client, bucket_name)

    if not _confirm_restore_operation(selected_exports):
        return

    restore_results = _perform_restores(ec2_client, bucket_name, selected_exports)
    _print_restore_summary(restore_results, selected_exports, region)


def main():
    """Main function."""
    try:
        restore_snapshots_from_s3()
    except (
        ClientError,
        ValueError,
        KeyboardInterrupt,
        S3ExportError,
        AMIImportError,
        SnapshotCreationError,
    ) as e:
        print(f"❌ Script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
