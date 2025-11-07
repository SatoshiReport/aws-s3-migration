#!/usr/bin/env python3

import json
import os
import time

import boto3

MAX_SSM_MONITOR_SECONDS = 7200


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def start_instance_and_migrate():
    """Start EC2 instance and run migration via SSM"""
    setup_aws_credentials()

    print("AWS Instance Startup and Migration")
    print("=" * 80)
    print("🚀 Starting EC2 instance and running EBS to S3 migration")
    print("💻 No SSH required - all remote execution")
    print()

    # Initialize AWS clients
    ec2 = boto3.client("ec2", region_name="eu-west-2")
    ssm = boto3.client("ssm", region_name="eu-west-2")

    instance_id = "i-05ad29f28fc8a8fdc"
    bucket_name = "aws-user-files-backup-london"

    try:
        # Start the instance
        print("🔄 STARTING EC2 INSTANCE:")
        print("=" * 80)
        print(f"Starting instance: {instance_id}")

        ec2.start_instances(InstanceIds=[instance_id])
        print("✅ Start command sent")
        print("⏳ Waiting for instance to be running...")

        # Wait for instance to be running
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})

        print("✅ Instance is now running")
        print("⏳ Waiting additional 60 seconds for SSM agent to be ready...")
        time.sleep(60)
        print()

        # Create the migration command
        migration_command = f"""#!/bin/bash

echo "🚀 Starting EBS to S3 migration via SSM..."
echo "Target bucket: {bucket_name}"
echo "Region: eu-west-2"
echo "$(date): Migration started"
echo ""

# Set AWS region
export AWS_DEFAULT_REGION=eu-west-2

# Create mount points
sudo mkdir -p /mnt/vol384
sudo mkdir -p /mnt/vol64

# Find and mount volumes
echo "📦 Discovering and mounting volumes..."

# List all block devices
echo "Available block devices:"
lsblk

# Find volume devices by size
echo ""
echo "Searching for volumes by size..."

# Look for 384GB volume (approximately 384GB = 412316860416 bytes)
VOL384_DEVICE=""
VOL64_DEVICE=""

for dev in $(lsblk -d -o NAME -n | grep -E "nvme|xvd"); do
    FULL_DEV="/dev/$dev"
    if [ -b "$FULL_DEV" ]; then
        SIZE_BYTES=$(lsblk -b -d -o SIZE -n $FULL_DEV 2>/dev/null)
        SIZE_GB=$((SIZE_BYTES / 1024 / 1024 / 1024))
        
        echo "Device $FULL_DEV: ${{SIZE_GB}}GB"  # type: ignore
        
        # 384GB volume (allow some variance)
        if [ "$SIZE_GB" -gt 350 ] && [ "$SIZE_GB" -lt 450 ]; then
            VOL384_DEVICE=$FULL_DEV
            echo "✅ Found 384GB volume: $VOL384_DEVICE"
        fi
        
        # 64GB volume (allow some variance)
        if [ "$SIZE_GB" -gt 50 ] && [ "$SIZE_GB" -lt 100 ]; then
            VOL64_DEVICE=$FULL_DEV
            echo "✅ Found 64GB volume: $VOL64_DEVICE"
        fi
    fi
done

echo ""
echo "Selected devices:"
echo "384GB device: $VOL384_DEVICE"
echo "64GB device: $VOL64_DEVICE"

# Mount volumes
if [ -n "$VOL384_DEVICE" ]; then
    echo "Mounting 384GB volume..."
    sudo mount $VOL384_DEVICE /mnt/vol384 2>/dev/null && echo "✅ 384GB mounted" || echo "⚠️ 384GB mount failed or already mounted"
fi

if [ -n "$VOL64_DEVICE" ]; then
    echo "Mounting 64GB volume..."
    sudo mount $VOL64_DEVICE /mnt/vol64 2>/dev/null && echo "✅ 64GB mounted" || echo "⚠️ 64GB mount failed or already mounted"
fi

echo ""
echo "📁 Current mounts:"
df -h | grep -E "/mnt/|Filesystem"

echo ""
echo "🔍 Checking directory contents..."

# Check what's actually in the mounted volumes
for mount_point in /mnt/vol384 /mnt/vol64; do
    if [ -d "$mount_point" ]; then
        echo ""
        echo "Contents of $mount_point:"
        ls -la "$mount_point" 2>/dev/null || echo "Cannot list contents"
        
        # Check for common directories
        for dir in home opt var root data; do
            if [ -d "$mount_point/$dir" ]; then
                echo "  📁 $dir/ exists"
                du -sh "$mount_point/$dir" 2>/dev/null || echo "  Cannot get size"
            fi
        done
    fi
done

echo ""
echo "🔄 Starting file sync to S3..."

# Function to sync directory to S3
sync_to_s3() {{
    local source_path="$1"
    local s3_prefix="$2"
    
    if [ -d "$source_path" ]; then
        echo ""
        echo "🔄 Syncing $source_path to s3://{bucket_name}/$s3_prefix/"
        
        # Get directory size first
        DIR_SIZE=$(du -sh "$source_path" 2>/dev/null | cut -f1)
        echo "Directory size: $DIR_SIZE"
        
        aws s3 sync "$source_path" "s3://{bucket_name}/$s3_prefix/" \\
            --region eu-west-2 \\
            --storage-class STANDARD \\
            --exclude "*.tmp" \\
            --exclude "*.log" \\
            --exclude ".cache/*" \\
            --exclude "lost+found/*" \\
            --exclude "proc/*" \\
            --exclude "sys/*" \\
            --exclude "dev/*" \\
            --exclude "*.sock" \\
            --delete
            
        if [ $? -eq 0 ]; then
            echo "✅ Completed: $source_path"
        else
            echo "❌ Failed: $source_path"
        fi
    else
        echo "⚠️  Directory not found: $source_path"
    fi
}}

# Migrate from 384GB volume
if [ -d "/mnt/vol384" ]; then
    echo ""
    echo "📦 Processing 384GB volume..."
    sync_to_s3 "/mnt/vol384/home" "384gb-volume/home"
    sync_to_s3 "/mnt/vol384/opt" "384gb-volume/opt"
    sync_to_s3 "/mnt/vol384/var" "384gb-volume/var"
    sync_to_s3 "/mnt/vol384/data" "384gb-volume/data"
    sync_to_s3 "/mnt/vol384/root" "384gb-volume/root"
    sync_to_s3 "/mnt/vol384/etc" "384gb-volume/etc"
    sync_to_s3 "/mnt/vol384/usr/local" "384gb-volume/usr-local"
fi

# Migrate from 64GB volume
if [ -d "/mnt/vol64" ]; then
    echo ""
    echo "📦 Processing 64GB volume..."
    sync_to_s3 "/mnt/vol64/home" "64gb-volume/home"
    sync_to_s3 "/mnt/vol64/opt" "64gb-volume/opt"
    sync_to_s3 "/mnt/vol64/var" "64gb-volume/var"
    sync_to_s3 "/mnt/vol64/data" "64gb-volume/data"
    sync_to_s3 "/mnt/vol64/root" "64gb-volume/root"
    sync_to_s3 "/mnt/vol64/etc" "64gb-volume/etc"
    sync_to_s3 "/mnt/vol64/usr/local" "64gb-volume/usr-local"
fi

echo ""
echo "📊 Final S3 bucket contents:"
aws s3 ls s3://{bucket_name}/ --recursive --human-readable --summarize

echo ""
echo "✅ Migration complete!"
echo "$(date): Migration finished"
echo "Files are now stored in S3 bucket: {bucket_name}"
echo ""
echo "💰 Next steps:"
echo "1. Verify files in S3 bucket"
echo "2. Consider reducing EBS volume sizes"
echo "3. Potential monthly savings: ~$25.54"
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
                "executionTimeout": ["7200"],  # 2 hour timeout
            },
            Comment="EBS to S3 migration via SSM - automated",
        )

        command_id = response["Command"]["CommandId"]
        print(f"✅ Command sent successfully")
        print(f"Command ID: {command_id}")
        print()

        # Monitor command execution
        print("⏳ MONITORING MIGRATION PROGRESS:")
        print("=" * 80)

        max_wait_time = MAX_SSM_MONITOR_SECONDS  # 2 hours
        wait_interval = 30  # Check every 30 seconds
        elapsed_time = 0

        while elapsed_time < max_wait_time:
            try:
                command_status = ssm.get_command_invocation(
                    CommandId=command_id, InstanceId=instance_id
                )

                status = command_status["Status"]
                print(f"Status: {status} (elapsed: {elapsed_time//60}m {elapsed_time%60}s)")

                if status in ["Success", "Failed", "Cancelled", "TimedOut"]:
                    print()
                    print("📋 MIGRATION OUTPUT:")
                    print("=" * 80)

                    if "StandardOutputContent" in command_status:
                        output = command_status["StandardOutputContent"]
                        # Show last 2000 characters to avoid overwhelming output
                        if len(output) > 2000:
                            print("... (output truncated) ...")
                            print(output[-2000:])
                        else:
                            print(output)

                    if (
                        "StandardErrorContent" in command_status
                        and command_status["StandardErrorContent"]
                    ):
                        print("\nERRORS:")
                        print(command_status["StandardErrorContent"])

                    if status == "Success":
                        print("\n✅ Migration completed successfully!")
                        print("\n🎯 RESULTS:")
                        print("- Files transferred from EBS to S3")
                        print("- S3 bucket: aws-user-files-backup-london")
                        print("- Potential savings: ~$25.54/month")
                    else:
                        print(f"\n❌ Migration failed with status: {status}")

                    break

                time.sleep(wait_interval)
                elapsed_time += wait_interval

            except Exception as e:
                print(f"Error checking status: {str(e)}")
                time.sleep(wait_interval)
                elapsed_time += wait_interval

        if elapsed_time >= max_wait_time:
            print("⏰ Migration timeout reached")

    except Exception as e:
        print(f"❌ Error during execution: {str(e)}")


if __name__ == "__main__":
    start_instance_and_migrate()
