#!/usr/bin/env python3
"""
AWS EBS Snapshot to S3 Semi-Manual Export Script
This script automates the reliable parts and provides manual commands for the rest:

AUTOMATED:
- Creates AMIs from snapshots (this works reliably)
- Sets up S3 buckets with proper configuration
- Validates prerequisites

MANUAL (with exact commands provided):
- Export AMI to S3 (you run the AWS CLI commands)
- Monitor export progress
- Clean up temporary AMIs after success

This approach gives you control over the problematic AWS export service.
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
        raise ValueError("AWS credentials not found in ~/.env file")  # noqa: TRY003

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def create_s3_bucket_if_not_exists(s3_client, bucket_name, region):
    """Create S3 bucket if it doesn't exist"""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"   ✅ S3 bucket {bucket_name} already exists")
    except s3_client.exceptions.NoSuchBucket:
        print(f"   🔄 Creating S3 bucket {bucket_name}...")
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region}
            )

        # Enable versioning for data protection
        s3_client.put_bucket_versioning(
            Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
        )

        print(f"   ✅ Created S3 bucket {bucket_name} with versioning enabled")
        return True

    else:
        return True


def create_ami_from_snapshot(ec2_client, snapshot_id, snapshot_description):
    """Create an AMI from an EBS snapshot with optimal settings"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ami_name = f"manual-export-{snapshot_id}-{timestamp}"

    print(f"   🔄 Creating AMI from snapshot {snapshot_id}...")

    # Use settings optimized for export compatibility
    response = ec2_client.register_image(
        Name=ami_name,
        Description=f"AMI for manual S3 export from {snapshot_id}: {snapshot_description}",
        Architecture="x86_64",
        RootDeviceName="/dev/sda1",
        BlockDeviceMappings=[
            {
                "DeviceName": "/dev/sda1",
                "Ebs": {
                    "SnapshotId": snapshot_id,
                    "VolumeType": "gp2",  # Use gp2 for better compatibility
                    "DeleteOnTermination": True,
                },
            }
        ],
        VirtualizationType="hvm",
        BootMode="legacy-bios",  # Better compatibility
        EnaSupport=False,  # Disable for compatibility
        SriovNetSupport="simple",
    )

    ami_id = response["ImageId"]
    print(f"   ✅ Created AMI: {ami_id}")

    # Wait for AMI to be available
    print(f"   ⏳ Waiting for AMI {ami_id} to become available...")
    waiter = ec2_client.get_waiter("image_available")
    waiter.wait(ImageIds=[ami_id], WaiterConfig={"Delay": 30, "MaxAttempts": 40})  # 20 minutes max
    print(f"   ✅ AMI {ami_id} is now available and ready for export")

    return ami_id


def prepare_snapshot_for_export(snapshot_info, aws_access_key_id, aws_secret_access_key):
    """Prepare a snapshot for manual export by creating AMI and S3 bucket"""
    snapshot_id = snapshot_info["snapshot_id"]
    region = snapshot_info["region"]
    size_gb = snapshot_info["size_gb"]
    description = snapshot_info["description"]

    print(f"\n🔍 Preparing {snapshot_id} ({size_gb} GB) in {region}...")

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

    # Create S3 bucket
    bucket_name = f"ebs-snapshot-archive-{region}-{datetime.now().strftime('%Y%m%d')}"
    create_s3_bucket_if_not_exists(s3_client, bucket_name, region)

    # Create AMI
    ami_id = create_ami_from_snapshot(ec2_client, snapshot_id, description)

    # Calculate potential savings
    ebs_monthly_cost = size_gb * 0.05
    s3_monthly_cost = size_gb * 0.023
    monthly_savings = ebs_monthly_cost - s3_monthly_cost

    return {
        "snapshot_id": snapshot_id,
        "ami_id": ami_id,
        "bucket_name": bucket_name,
        "region": region,
        "size_gb": size_gb,
        "monthly_savings": monthly_savings,
        "description": description,
    }


def generate_manual_commands(prepared_snapshots):  # noqa: PLR0915
    """Generate the manual AWS CLI commands for exports"""
    print("\n" + "=" * 80)
    print("📋 MANUAL EXPORT COMMANDS")
    print("=" * 80)
    print("The AMIs are ready! Now run these commands manually to export them:")
    print()

    export_commands = []
    monitor_commands = []
    cleanup_commands = []

    for i, prep in enumerate(prepared_snapshots, 1):
        ami_id = prep["ami_id"]
        bucket_name = prep["bucket_name"]
        region = prep["region"]
        snapshot_id = prep["snapshot_id"]

        # Export command
        export_cmd = f"""aws ec2 export-image \\
    --image-id {ami_id} \\
    --disk-image-format VMDK \\
    --s3-export-location S3Bucket={bucket_name},S3Prefix=ebs-snapshots/{ami_id}/ \\
    --description "Manual export of {snapshot_id}" \\
    --region {region}"""

        # Monitor command
        monitor_cmd = f"""# Monitor export progress:
aws ec2 describe-export-image-tasks \\
    --region {region} \\
    --query 'ExportImageTasks[?ImageId==`{ami_id}`].[ExportImageTaskId,Status,Progress,StatusMessage]' \\
    --output table"""

        # S3 check command
        s3_check_cmd = f"""# Check S3 file directly:
aws s3 ls s3://{bucket_name}/ebs-snapshots/{ami_id}/ --recursive --human-readable

# Check S3 file size (most reliable completion check):
aws s3api head-object --bucket {bucket_name} --key ebs-snapshots/{ami_id}/{ami_id}.vmdk"""

        # Cleanup command (run ONLY after successful export)
        cleanup_cmd = f"""# CLEANUP (run only after successful export):
aws ec2 deregister-image --image-id {ami_id} --region {region}"""

        print(f"## Step {i}: Export {snapshot_id} ({prep['size_gb']} GB)")
        print(f"### Export Command:")
        print(export_cmd)
        print()
        print(f"### Monitor Progress:")
        print(monitor_cmd)
        print()
        print(s3_check_cmd)
        print()
        print(f"### Cleanup (ONLY after success):")
        print(cleanup_cmd)
        print()
        print("-" * 60)
        print()

        export_commands.append(export_cmd)
        monitor_commands.append(monitor_cmd)
        cleanup_commands.append(cleanup_cmd)

    # Summary section
    print("📊 EXPORT WORKFLOW:")
    print("1. Run each export command above")
    print("2. Monitor progress with the monitor commands")
    print("3. If export gets stuck at 80%, wait 2-3 hours and check S3 directly")
    print("4. Once S3 file appears and is stable, run cleanup commands")
    print("5. Verify S3 files exist before deleting original snapshots")
    print()

    # Troubleshooting
    print("🔧 TROUBLESHOOTING:")
    print("- If export fails immediately: Try again in 10-15 minutes")
    print("- If stuck at 80%: Check S3 directly - file might be complete")
    print("- If export gets deleted: Try in a different region (eu-west-2 works better)")
    print()
    print("📊 S3 FILE SIZE MONITORING COMMANDS:")
    for prep in prepared_snapshots:
        bucket_name = prep["bucket_name"]
        ami_id = prep["ami_id"]
        print(
            f"aws s3api head-object --bucket {bucket_name} --key ebs-snapshots/{ami_id}/{ami_id}.vmdk"
        )
    print()

    # Cost savings summary
    total_savings = sum(prep["monthly_savings"] for prep in prepared_snapshots)
    print(f"💰 POTENTIAL SAVINGS:")
    print(f"   Monthly: ${total_savings:.2f}")
    print(f"   Annual: ${total_savings * 12:.2f}")

    return export_commands, monitor_commands, cleanup_commands


def main():
    """Main function"""
    print("AWS EBS Snapshot to S3 Semi-Manual Export Script")
    print("=" * 80)
    print("This script will:")
    print("✅ Create AMIs from your snapshots (automated)")
    print("✅ Set up S3 buckets (automated)")
    print("📋 Provide exact manual commands for exports")
    print("📋 Provide monitoring and cleanup commands")
    print()

    # Load credentials
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    # Snapshots to process
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

    total_size_gb = sum(snap["size_gb"] for snap in snapshots)
    total_monthly_savings = total_size_gb * (0.05 - 0.023)

    print(f"🎯 Target: {len(snapshots)} snapshots ({total_size_gb} GB total)")
    print(f"💰 Potential monthly savings: ${total_monthly_savings:.2f}")
    print(f"💰 Potential annual savings: ${total_monthly_savings * 12:.2f}")
    print()

    print("\n🚀 Starting automated preparation...")

    # Prepare all snapshots (create AMIs and S3 buckets)
    prepared_snapshots = []
    for snapshot in snapshots:
        try:
            prepared = prepare_snapshot_for_export(
                snapshot, aws_access_key_id, aws_secret_access_key
            )
            prepared_snapshots.append(prepared)
        except Exception as e:
            print(f"   ❌ Failed to prepare {snapshot['snapshot_id']}: {e}")
            raise

    # Generate manual commands
    export_commands, monitor_commands, cleanup_commands = generate_manual_commands(
        prepared_snapshots
    )

    # Save commands to file for easy reference
    commands_file = f"manual_export_commands_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(commands_file, "w") as f:
        f.write("AWS EBS Snapshot to S3 Manual Export Commands\n")
        f.write("=" * 50 + "\n\n")

        for i, prep in enumerate(prepared_snapshots, 1):
            f.write(f"Step {i}: Export {prep['snapshot_id']} ({prep['size_gb']} GB)\n")
            f.write("-" * 40 + "\n")
            f.write("Export Command:\n")
            f.write(export_commands[i - 1] + "\n\n")
            f.write("Monitor Command:\n")
            f.write(monitor_commands[i - 1] + "\n\n")
            f.write("Cleanup Command:\n")
            f.write(cleanup_commands[i - 1] + "\n\n")

    print(f"\n📄 Commands saved to: {commands_file}")
    print("\n✅ PREPARATION COMPLETE!")
    print("🎯 Next: Run the manual export commands shown above")


if __name__ == "__main__":
    main()
