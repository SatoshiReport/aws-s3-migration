#!/usr/bin/env python3

import json
import os
import time

import boto3

MAX_SSM_MIGRATION_WAIT_SECONDS = 3600


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def run_migration_via_ssm():
    """Run EBS to S3 migration via SSM Run Command from laptop"""
    setup_aws_credentials()

    print("AWS SSM Remote Migration Runner")
    print("=" * 80)
    print("🚀 Running EBS to S3 migration remotely via SSM")
    print("💻 No SSH required - executing from your laptop")
    print()

    # Initialize AWS clients
    ssm = boto3.client("ssm", region_name="eu-west-2")
    ec2 = boto3.client("ec2", region_name="eu-west-2")

    instance_id = "i-05ad29f28fc8a8fdc"
    bucket_name = "aws-user-files-backup-london"

    try:
        # First check if instance is running and SSM is available
        print("🔍 CHECKING INSTANCE STATUS:")
        print("=" * 80)

        instances_response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = instances_response["Reservations"][0]["Instances"][0]
        instance_state = instance["State"]["Name"]

        print(f"Instance: {instance_id}")
        print(f"State: {instance_state}")

        if instance_state != "running":
            print("❌ Instance must be running for SSM commands")
            return

        print("✅ Instance is running")
        print()

        # Create the migration command
        migration_command = f"""#!/bin/bash

echo "🚀 Starting EBS to S3 migration via SSM..."
echo "Target bucket: {bucket_name}"
echo "Region: eu-west-2"
echo ""

# Set AWS region
export AWS_DEFAULT_REGION=eu-west-2

# Create mount points
sudo mkdir -p /mnt/vol384
sudo mkdir -p /mnt/vol64

# Find and mount volumes
echo "📦 Mounting volumes..."

# Find volume devices (they might be nvme devices)
VOL384_DEVICE=$(lsblk -o NAME,SIZE | grep "384G" | awk '{{print "/dev/"$1}}' | head -1)
VOL64_DEVICE=$(lsblk -o NAME,SIZE | grep "64G" | awk '{{print "/dev/"$1}}' | head -1)

if [ -z "$VOL384_DEVICE" ]; then
    # Try common nvme device names
    for dev in /dev/nvme1n1 /dev/nvme2n1 /dev/nvme3n1; do
        if [ -b "$dev" ]; then
            SIZE=$(lsblk -b -o SIZE -n $dev 2>/dev/null | head -1)
            if [ "$SIZE" -gt 400000000000 ]; then  # ~384GB
                VOL384_DEVICE=$dev
                break
            fi
        fi
    done
fi

if [ -z "$VOL64_DEVICE" ]; then
    # Try common nvme device names for 64GB
    for dev in /dev/nvme1n1 /dev/nvme2n1 /dev/nvme3n1; do
        if [ -b "$dev" ] && [ "$dev" != "$VOL384_DEVICE" ]; then
            SIZE=$(lsblk -b -o SIZE -n $dev 2>/dev/null | head -1)
            if [ "$SIZE" -lt 100000000000 ]; then  # ~64GB
                VOL64_DEVICE=$dev
                break
            fi
        fi
    done
fi

echo "384GB device: $VOL384_DEVICE"
echo "64GB device: $VOL64_DEVICE"

# Mount volumes
if [ -n "$VOL384_DEVICE" ]; then
    sudo mount $VOL384_DEVICE /mnt/vol384 2>/dev/null || echo "384GB volume mount failed or already mounted"
fi

if [ -n "$VOL64_DEVICE" ]; then
    sudo mount $VOL64_DEVICE /mnt/vol64 2>/dev/null || echo "64GB volume mount failed or already mounted"
fi

echo ""
echo "📁 Checking mounted volumes..."
df -h | grep "/mnt/"

echo ""
echo "🔄 Starting file sync to S3..."

# Function to sync directory to S3
sync_to_s3() {{
    local source_path="$1"
    local s3_prefix="$2"
    
    if [ -d "$source_path" ]; then
        echo "🔄 Syncing $source_path to s3://{bucket_name}/$s3_prefix/"
        aws s3 sync "$source_path" "s3://{bucket_name}/$s3_prefix/" \\
            --region eu-west-2 \\
            --storage-class STANDARD \\
            --exclude "*.tmp" \\
            --exclude "*.log" \\
            --exclude ".cache/*" \\
            --exclude "lost+found/*" \\
            --exclude "proc/*" \\
            --exclude "sys/*" \\
            --exclude "dev/*"
        echo "✅ Completed: $source_path"
        echo ""
    else
        echo "⚠️  Directory not found: $source_path"
    fi
}}

# Migrate from 384GB volume
if [ -d "/mnt/vol384" ]; then
    echo "📦 Processing 384GB volume..."
    sync_to_s3 "/mnt/vol384/home" "384gb-volume/home"
    sync_to_s3 "/mnt/vol384/opt" "384gb-volume/opt"
    sync_to_s3 "/mnt/vol384/var/www" "384gb-volume/var-www"
    sync_to_s3 "/mnt/vol384/data" "384gb-volume/data"
    sync_to_s3 "/mnt/vol384/root" "384gb-volume/root"
fi

# Migrate from 64GB volume
if [ -d "/mnt/vol64" ]; then
    echo "📦 Processing 64GB volume..."
    sync_to_s3 "/mnt/vol64/home" "64gb-volume/home"
    sync_to_s3 "/mnt/vol64/opt" "64gb-volume/opt"
    sync_to_s3 "/mnt/vol64/var/www" "64gb-volume/var-www"
    sync_to_s3 "/mnt/vol64/data" "64gb-volume/data"
    sync_to_s3 "/mnt/vol64/root" "64gb-volume/root"
fi

echo ""
echo "📊 Migration summary:"
aws s3 ls s3://{bucket_name}/ --recursive --human-readable --summarize

echo ""
echo "✅ Migration complete!"
echo "Files are now stored in S3 bucket: {bucket_name}"
"""

        # Execute the command via SSM
        print("🚀 EXECUTING MIGRATION VIA SSM:")
        print("=" * 80)
        print("Sending migration command to EC2 instance...")

        response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={
                "commands": [migration_command],
                "executionTimeout": ["3600"],  # 1 hour timeout
            },
            Comment="EBS to S3 migration via SSM",
        )

        command_id = response["Command"]["CommandId"]
        print(f"✅ Command sent successfully")
        print(f"Command ID: {command_id}")
        print()

        # Wait for command to complete and show progress
        print("⏳ MONITORING COMMAND EXECUTION:")
        print("=" * 80)

        max_wait_time = MAX_SSM_MIGRATION_WAIT_SECONDS  # 1 hour
        wait_interval = 10  # Check every 10 seconds
        elapsed_time = 0

        while elapsed_time < max_wait_time:
            try:
                # Get command status
                command_status = ssm.get_command_invocation(
                    CommandId=command_id, InstanceId=instance_id
                )

                status = command_status["Status"]
                print(f"Status: {status} (elapsed: {elapsed_time}s)")

                if status in ["Success", "Failed", "Cancelled", "TimedOut"]:
                    print()
                    print("📋 COMMAND OUTPUT:")
                    print("=" * 80)

                    if "StandardOutputContent" in command_status:
                        print(command_status["StandardOutputContent"])

                    if (
                        "StandardErrorContent" in command_status
                        and command_status["StandardErrorContent"]
                    ):
                        print("ERRORS:")
                        print(command_status["StandardErrorContent"])

                    if status == "Success":
                        print("✅ Migration completed successfully!")
                    else:
                        print(f"❌ Migration failed with status: {status}")

                    break

                time.sleep(wait_interval)
                elapsed_time += wait_interval

            except Exception as e:
                print(f"Error checking command status: {str(e)}")
                time.sleep(wait_interval)
                elapsed_time += wait_interval

        if elapsed_time >= max_wait_time:
            print("⏰ Command execution timeout reached")

        print()
        print("🎯 NEXT STEPS:")
        print("=" * 80)
        print("1. Check S3 bucket for migrated files:")
        print(f"   aws s3 ls s3://{bucket_name}/ --recursive")
        print("2. Verify file transfer completed successfully")
        print("3. Consider reducing EBS volume sizes after migration")

    except Exception as e:
        print(f"❌ Error during SSM execution: {str(e)}")


if __name__ == "__main__":
    run_migration_via_ssm()
