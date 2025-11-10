#!/usr/bin/env python3
"""
AWS Volume Cleanup and Management Script
Handles volume tagging, snapshot deletion, and S3 bucket listing.
"""

from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from ..aws_utils import setup_aws_credentials


def tag_volume_with_name(volume_id, name, region):
    """
    Add a Name tag to an EBS volume.

    Args:
        volume_id: The EBS volume ID to tag
        name: The name to assign to the volume
        region: AWS region where the volume is located

    Returns:
        True if successful, False otherwise
    """
    try:
        ec2_client = boto3.client("ec2", region_name=region)

        # Add the Name tag
        ec2_client.create_tags(Resources=[volume_id], Tags=[{"Key": "Name", "Value": name}])

        print(f"✅ Successfully tagged volume {volume_id} with name '{name}' in {region}")

    except ClientError as e:
        print(f"❌ Error tagging volume {volume_id}: {str(e)}")
        return False

    return True


def delete_snapshot(snapshot_id, region):
    """
    Delete an EBS snapshot.

    Args:
        snapshot_id: The snapshot ID to delete
        region: AWS region where the snapshot is located

    Returns:
        True if successful, False otherwise
    """
    try:
        ec2_client = boto3.client("ec2", region_name=region)

        # Get snapshot info first
        response = ec2_client.describe_snapshots(SnapshotIds=[snapshot_id])
        snapshot = response["Snapshots"][0]

        size_gb = snapshot.get("VolumeSize", 0)
        description = snapshot.get("Description", "No description")
        start_time = snapshot["StartTime"]

        print(f"🔍 Snapshot to delete: {snapshot_id}")
        print(f"   Size: {size_gb} GB")
        print(f"   Created: {start_time}")
        print(f"   Description: {description}")

        # Delete the snapshot
        ec2_client.delete_snapshot(SnapshotId=snapshot_id)

        monthly_cost_saved = size_gb * 0.05  # $0.05 per GB/month
        print(f"✅ Successfully deleted snapshot {snapshot_id}")
        print(f"💰 Monthly cost savings: ${monthly_cost_saved:.2f}")

    except ClientError as e:
        print(f"❌ Error deleting snapshot {snapshot_id}: {str(e)}")
        return False

    return True


def get_bucket_region(s3_client, bucket_name):
    """Get the region for an S3 bucket"""
    try:
        location_response = s3_client.get_bucket_location(Bucket=bucket_name)
        region = location_response.get("LocationConstraint", "us-east-1")
        if region is None:
            region = "us-east-1"
        print(f"    Region: {region}")
    except ClientError as e:
        print(f"    Region: Unable to determine ({str(e)})")
        return "Unknown"
    return region


def get_bucket_size_metrics(bucket_name, region):
    """Get bucket size metrics from CloudWatch"""
    try:
        cloudwatch = boto3.client(
            "cloudwatch", region_name=region if region != "Unknown" else "us-east-1"
        )

        end_time = datetime.now(timezone.utc)
        start_time = end_time.replace(day=1)

        metrics_response = cloudwatch.get_metric_statistics(
            Namespace="AWS/S3",
            MetricName="BucketSizeBytes",
            Dimensions=[
                {"Name": "BucketName", "Value": bucket_name},
                {"Name": "StorageType", "Value": "StandardStorage"},
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,
            Statistics=["Average"],
        )

        if metrics_response["Datapoints"]:
            sorted_datapoints = sorted(
                metrics_response["Datapoints"], key=lambda x: x["Timestamp"], reverse=True
            )
            size_bytes = sorted_datapoints[0]["Average"]
            size_gb = size_bytes / (1024**3)

            if size_gb > 1:
                print(f"    Size: {size_gb:.2f} GB")
                monthly_cost = size_gb * 0.023
                print(f"    Est. monthly cost: ${monthly_cost:.2f}")
            else:
                size_mb = size_bytes / (1024**2)
                print(f"    Size: {size_mb:.2f} MB")
                print("    Est. monthly cost: <$0.01")
        else:
            print("    Size: No recent data available")

    except ClientError:
        print("    Size: Unable to determine")


def process_bucket_info(s3_client, bucket):
    """Process and display information for a single bucket"""
    bucket_name = bucket["Name"]
    creation_date = bucket["CreationDate"]

    print(f"  Bucket: {bucket_name}")
    print(f"    Created: {creation_date}")

    region = get_bucket_region(s3_client, bucket_name)
    get_bucket_size_metrics(bucket_name, region)

    print()

    return {"name": bucket_name, "creation_date": creation_date, "region": region}


def list_s3_buckets():
    """
    List all S3 buckets in the account.

    Returns:
        List of bucket information dictionaries
    """
    try:
        s3_client = boto3.client("s3")

        response = s3_client.list_buckets()
        buckets = response.get("Buckets", [])

        print(f"🪣 Found {len(buckets)} S3 bucket(s):")
        print()

        bucket_info = [process_bucket_info(s3_client, bucket) for bucket in buckets]

    except ClientError as e:
        print(f"❌ Error listing S3 buckets: {str(e)}")
        return []

    return bucket_info


def main():
    """Main function to handle the requested operations."""
    setup_aws_credentials()

    print("AWS Volume Cleanup and Management")
    print("=" * 80)
    print()

    # Task 1: Tag vol-062d0da3492e8ceff with name "mufasa"
    print("🏷️  Task 1: Tagging volume with name 'mufasa'")
    print("-" * 50)
    success1 = tag_volume_with_name("vol-062d0da3492e8cef", "mufasa", "us-east-2")
    print()

    # Task 2: Delete automated snapshots
    print("🗑️  Task 2: Deleting automated snapshots")
    print("-" * 50)

    # Delete first automated snapshot
    print("Deleting automated snapshot 1:")
    success2a = delete_snapshot("snap-0b41a960b5d769549", "eu-west-2")
    print()

    # Delete second automated snapshot
    print("Deleting automated snapshot 2:")
    success2b = delete_snapshot("snap-0844382dabe07dd64", "eu-west-2")
    print()

    # Task 3: List S3 buckets
    print("🪣 Task 3: Listing S3 buckets")
    print("-" * 50)
    buckets = list_s3_buckets()

    # Summary
    print("=" * 80)
    print("🎯 SUMMARY")
    print("=" * 80)

    if success1:
        print("✅ Volume vol-062d0da3492e8ceff successfully tagged as 'mufasa'")
    else:
        print("❌ Failed to tag volume")

    if success2a and success2b:
        print("✅ Both automated snapshots successfully deleted")
        print("💰 Total monthly savings: ~$22.40 (384GB + 64GB snapshots)")
    elif success2a or success2b:
        print("⚠️  One automated snapshot deleted, one failed")
    else:
        print("❌ Failed to delete automated snapshots")

    if buckets:
        print(f"✅ Found {len(buckets)} S3 bucket(s)")
    else:
        print("ℹ️  No S3 buckets found or unable to list")

    print()
    print("📝 Note: You can verify changes using:")
    print("   python3 scripts/management/aws_ebs_volume_manager.py info vol-062d0da3492e8cef")
    print("   python3 scripts/audit/aws_ebs_audit.py")


if __name__ == "__main__":
    main()
