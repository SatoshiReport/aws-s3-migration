"""CLI helper functions"""

from datetime import datetime

import boto3

from .export_ops import (
    create_ami_from_snapshot,
    create_s3_bucket_if_not_exists,
    export_ami_to_s3,
    setup_s3_bucket_versioning,
)
from .monitoring import check_existing_exports, cleanup_temporary_ami, verify_s3_export
from .validation import calculate_cost_savings


def _get_snapshots_to_export():
    """Get list of snapshots to export."""
    return [
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
            "description": (
                "Snapshot of Tars 3 (vol-0249308257e5fa64d) - 64GB - 2025-07-18 04:15 UTC"
            ),
        },
        {
            "snapshot_id": "snap-036eee4a7c291fd26",
            "region": "us-east-2",
            "size_gb": 8,
            "description": (
                "Copied for DestinationAmi ami-05d0a30507ebee9d6 "
                "from SourceAmi ami-0cb41e78dab346fb3"
            ),
        },
    ]


def _check_existing_export_match(existing_exports, snapshot_id, s3_client, size_gb):
    """Check if snapshot was already exported in existing exports."""
    for existing_export in existing_exports:
        if snapshot_id in existing_export.get("description", ""):
            print(f"   ✅ Found existing export for {snapshot_id}!")
            s3_location = existing_export["s3_location"]
            s3_bucket = s3_location.get("S3Bucket", "")
            s3_prefix = s3_location.get("S3Prefix", "")
            s3_key = f"{s3_prefix}export.vmdk"

            verification = verify_s3_export(s3_client, s3_bucket, s3_key, size_gb)

            if verification.get("exists"):
                savings = calculate_cost_savings(size_gb)
                result = {
                    "snapshot_id": snapshot_id,
                    "ami_id": existing_export["ami_id"],
                    "bucket_name": s3_bucket,
                    "s3_key": s3_key,
                    "export_task_id": existing_export["export_task_id"],
                    "size_gb": size_gb,
                    "monthly_savings": savings["monthly_savings"],
                }

                print(f"   📍 S3 location: s3://{s3_bucket}/{s3_prefix}")
                print(f"   💰 Monthly savings: ${savings['monthly_savings']:.2f}")
                print()
                return result, True

            print("   ⚠️  Existing export found but S3 file missing - will re-export")
            break

    return None, False


def _create_aws_clients(region, aws_access_key_id, aws_secret_access_key):
    """Create EC2 and S3 clients"""
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


def _setup_bucket_for_export(s3_client, region):
    """Set up S3 bucket for export"""
    bucket_name = f"ebs-snapshot-archive-{region}-{datetime.now().strftime('%Y%m%d')}"

    if not create_s3_bucket_if_not_exists(s3_client, bucket_name, region):
        return None

    setup_s3_bucket_versioning(s3_client, bucket_name)
    return bucket_name


def _perform_export_workflow(
    ec2_client, s3_client, snapshot_id, description, bucket_name, region, size_gb
):
    """Execute the complete export workflow"""
    ami_id = create_ami_from_snapshot(ec2_client, snapshot_id, description)
    if not ami_id:
        print(f"   ❌ Failed to create AMI, skipping {snapshot_id}")
        return None

    export_task_id, s3_key = export_ami_to_s3(
        ec2_client, s3_client, ami_id, bucket_name, region, size_gb
    )

    if not export_task_id or not s3_key:
        print(f"   ❌ Failed to export {snapshot_id}")
        return None

    verification = verify_s3_export(s3_client, bucket_name, s3_key, size_gb)

    if not verification.get("exists"):
        print(f"   ❌ Export completed but S3 verification failed for {snapshot_id}")
        return None

    savings = calculate_cost_savings(size_gb)
    cleanup_temporary_ami(ec2_client, ami_id, region)

    return {
        "ami_id": ami_id,
        "bucket_name": bucket_name,
        "s3_key": s3_key,
        "export_task_id": export_task_id,
        "monthly_savings": savings["monthly_savings"],
    }


def process_single_snapshot_export(
    snap_info, aws_access_key_id, aws_secret_access_key, overwrite_existing
):
    """Process export for a single snapshot."""
    snapshot_id = snap_info["snapshot_id"]
    region = snap_info["region"]
    size_gb = snap_info["size_gb"]
    description = snap_info["description"]

    print(f"🔍 Processing {snapshot_id} ({size_gb} GB) in {region}...")

    ec2_client, s3_client = _create_aws_clients(region, aws_access_key_id, aws_secret_access_key)

    existing_exports = check_existing_exports(ec2_client, region)

    if not overwrite_existing:
        result, skip = _check_existing_export_match(
            existing_exports, snapshot_id, s3_client, size_gb
        )
        if skip:
            return result, True

    if existing_exports and overwrite_existing:
        print(f"   ⚠️  Overwrite mode: Ignoring {len(existing_exports)} existing exports")

    bucket_name = _setup_bucket_for_export(s3_client, region)
    if not bucket_name:
        print(f"   ❌ Failed to create S3 bucket, skipping {snapshot_id}")
        return None, False

    export_result = _perform_export_workflow(
        ec2_client, s3_client, snapshot_id, description, bucket_name, region, size_gb
    )

    if not export_result:
        return None, False

    result = {
        "snapshot_id": snapshot_id,
        "size_gb": size_gb,
        **export_result,
    }

    print(f"   ✅ Successfully exported {snapshot_id}")
    print(f"   📍 S3 location: s3://{bucket_name}/{export_result['s3_key']}")
    print(f"   💰 Monthly savings: ${export_result['monthly_savings']:.2f}")

    return result, False
