#!/usr/bin/env python3

import os
import time

import boto3

MAX_MIGRATION_WAIT_SECONDS = 3600


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def run_simple_migration():
    """Run simplified EBS to S3 migration via SSM"""
    setup_aws_credentials()

    print("AWS Simple EBS to S3 Migration")
    print("=" * 80)
    print("🚀 Running simplified migration via SSM")
    print()

    ssm = boto3.client("ssm", region_name="eu-west-2")
    instance_id = "i-05ad29f28fc8a8fdc"
    bucket_name = "aws-user-files-backup-london"

    try:
        # Simple migration command
        migration_command = f"""#!/bin/bash

echo "🚀 Starting EBS to S3 migration..."
echo "Target bucket: {bucket_name}"
echo "$(date): Migration started"

# Set AWS region
export AWS_DEFAULT_REGION=eu-west-2

# Create mount points
sudo mkdir -p /mnt/vol384 /mnt/vol64

echo "📦 Available block devices:"
lsblk

echo ""
echo "🔍 Mounting volumes..."

# Try to mount common device names
for dev in /dev/nvme1n1 /dev/nvme2n1 /dev/nvme3n1 /dev/xvdf /dev/xvdg; do
    if [ -b "$dev" ]; then
        size_gb=$(lsblk -b -d -o SIZE -n $dev 2>/dev/null | awk '{{print int($1/1024/1024/1024)}}')
        echo "Device $dev: ${{size_gb}}GB"
        
        if [ "$size_gb" -gt 300 ] && [ "$size_gb" -lt 500 ]; then
            echo "Mounting $dev as 384GB volume..."
            sudo mount $dev /mnt/vol384 2>/dev/null && echo "✅ 384GB mounted" || echo "⚠️ Mount failed"
        elif [ "$size_gb" -gt 50 ] && [ "$size_gb" -lt 100 ]; then
            echo "Mounting $dev as 64GB volume..."
            sudo mount $dev /mnt/vol64 2>/dev/null && echo "✅ 64GB mounted" || echo "⚠️ Mount failed"
        fi
    fi
done

echo ""
echo "📁 Current mounts:"
df -h | grep -E "/mnt/|Filesystem"

echo ""
echo "🔍 Checking directory contents..."

for mount_point in /mnt/vol384 /mnt/vol64; do
    if mountpoint -q "$mount_point" 2>/dev/null; then
        echo ""
        echo "Contents of $mount_point:"
        ls -la "$mount_point" 2>/dev/null | head -20
        
        for dir in home opt var root data etc usr; do
            if [ -d "$mount_point/$dir" ]; then
                size=$(du -sh "$mount_point/$dir" 2>/dev/null | cut -f1)
                echo "  📁 $dir/ ($size)"
            fi
        done
    fi
done

echo ""
echo "🔄 Starting S3 sync..."

# Function to sync directory to S3
sync_dir() {{
    local source="$1"
    local s3_path="$2"
    
    if [ -d "$source" ] && [ "$(ls -A $source 2>/dev/null)" ]; then
        echo ""
        echo "🔄 Syncing $source to s3://{bucket_name}/$s3_path/"
        aws s3 sync "$source" "s3://{bucket_name}/$s3_path/" \\
            --region eu-west-2 \\
            --storage-class STANDARD \\
            --exclude "*.tmp" \\
            --exclude "*.log" \\
            --exclude ".cache/*" \\
            --exclude "lost+found/*" \\
            --exclude "proc/*" \\
            --exclude "sys/*" \\
            --exclude "dev/*"
        echo "✅ Completed: $source"
    else
        echo "⚠️ Skipping empty/missing: $source"
    fi
}}

# Sync from both volumes
if mountpoint -q /mnt/vol384 2>/dev/null; then
    echo "📦 Processing 384GB volume..."
    sync_dir "/mnt/vol384/home" "384gb/home"
    sync_dir "/mnt/vol384/opt" "384gb/opt"
    sync_dir "/mnt/vol384/var" "384gb/var"
    sync_dir "/mnt/vol384/root" "384gb/root"
    sync_dir "/mnt/vol384/data" "384gb/data"
    sync_dir "/mnt/vol384/etc" "384gb/etc"
fi

if mountpoint -q /mnt/vol64 2>/dev/null; then
    echo "📦 Processing 64GB volume..."
    sync_dir "/mnt/vol64/home" "64gb/home"
    sync_dir "/mnt/vol64/opt" "64gb/opt"
    sync_dir "/mnt/vol64/var" "64gb/var"
    sync_dir "/mnt/vol64/root" "64gb/root"
    sync_dir "/mnt/vol64/data" "64gb/data"
    sync_dir "/mnt/vol64/etc" "64gb/etc"
fi

echo ""
echo "📊 S3 bucket summary:"
aws s3 ls s3://{bucket_name}/ --recursive --human-readable --summarize

echo ""
echo "✅ Migration complete!"
echo "$(date): Migration finished"
"""

        print("🚀 SENDING MIGRATION COMMAND:")
        print("=" * 80)

        response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [migration_command], "executionTimeout": ["3600"]},
            Comment="Simple EBS to S3 migration",
        )

        command_id = response["Command"]["CommandId"]
        print(f"✅ Command sent: {command_id}")
        print("⏳ Monitoring execution...")
        print()

        # Monitor execution
        max_wait = MAX_MIGRATION_WAIT_SECONDS
        interval = 20
        elapsed = 0

        while elapsed < max_wait:
            try:
                status_response = ssm.get_command_invocation(
                    CommandId=command_id, InstanceId=instance_id
                )

                status = status_response["Status"]
                print(f"Status: {status} ({elapsed//60}m {elapsed%60}s)")

                if status in ["Success", "Failed", "Cancelled", "TimedOut"]:
                    print()
                    print("📋 OUTPUT:")
                    print("=" * 80)

                    if "StandardOutputContent" in status_response:
                        output = status_response["StandardOutputContent"]
                        print(output[-3000:] if len(output) > 3000 else output)

                    if status_response.get("StandardErrorContent"):
                        print("\nERRORS:")
                        print(status_response["StandardErrorContent"])

                    print(f"\n{'✅ SUCCESS' if status == 'Success' else '❌ FAILED'}")
                    break

                time.sleep(interval)
                elapsed += interval

            except Exception as e:
                print(f"Status check error: {str(e)}")
                time.sleep(interval)
                elapsed += interval

        if elapsed >= max_wait:
            print("⏰ Timeout reached")

    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    run_simple_migration()
