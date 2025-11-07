#!/usr/bin/env python3

import base64
import os
import time

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def run_userdata_migration():
    """Use EC2 User Data to run migration on instance startup"""
    setup_aws_credentials()

    print("AWS User Data Migration Setup")
    print("=" * 80)
    print("🚀 Setting up migration via EC2 User Data")
    print("📝 Migration will run automatically on instance startup")
    print()

    ec2 = boto3.client("ec2", region_name="eu-west-2")
    s3 = boto3.client("s3", region_name="eu-west-2")

    instance_id = "i-05ad29f28fc8a8fdc"
    bucket_name = "aws-user-files-backup-london"

    try:
        # Create migration script for User Data
        migration_script = f"""#!/bin/bash

# EBS to S3 Migration Script - User Data
exec > /var/log/migration.log 2>&1

echo "🚀 Starting EBS to S3 migration via User Data..."
echo "Target bucket: {bucket_name}"
echo "$(date): Migration started"

# Load AWS credentials from ~/.env if present
if [ -f "$HOME/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$HOME/.env"
    set +a
else
    echo "Missing ~/.env with AWS credentials" >&2
    exit 1
fi

# Wait for system to be ready
sleep 30

# Install AWS CLI if not present
if ! command -v aws &> /dev/null; then
    echo "Installing AWS CLI..."
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    ./aws/install
fi

# Create mount points
mkdir -p /mnt/vol384 /mnt/vol64

echo "📦 Available block devices:"
lsblk

echo ""
echo "🔍 Mounting volumes..."

# Find and mount volumes by size
for dev in /dev/nvme1n1 /dev/nvme2n1 /dev/nvme3n1 /dev/xvdf /dev/xvdg /dev/xvdh; do
    if [ -b "$dev" ]; then
        size_bytes=$(lsblk -b -d -o SIZE -n $dev 2>/dev/null)
        size_gb=$((size_bytes / 1024 / 1024 / 1024))
        echo "Device $dev: ${{size_gb}}GB"
        
        if [ "$size_gb" -gt 300 ] && [ "$size_gb" -lt 500 ]; then
            echo "Mounting $dev as 384GB volume..."
            mount $dev /mnt/vol384 2>/dev/null && echo "✅ 384GB mounted" || echo "⚠️ Mount failed"
        elif [ "$size_gb" -gt 50 ] && [ "$size_gb" -lt 100 ]; then
            echo "Mounting $dev as 64GB volume..."
            mount $dev /mnt/vol64 2>/dev/null && echo "✅ 64GB mounted" || echo "⚠️ Mount failed"
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
        ls -la "$mount_point" 2>/dev/null | head -10
        
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
            --exclude "dev/*" \\
            --exclude "*.sock"
        
        if [ $? -eq 0 ]; then
            echo "✅ Completed: $source"
        else
            echo "❌ Failed: $source"
        fi
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
echo "📊 Final S3 bucket summary:"
aws s3 ls s3://{bucket_name}/ --recursive --human-readable --summarize

# Upload log to S3
echo ""
echo "📋 Uploading migration log to S3..."
aws s3 cp /var/log/migration.log s3://{bucket_name}/migration-log.txt --region eu-west-2

echo ""
echo "✅ Migration complete!"
echo "$(date): Migration finished"
echo "Log uploaded to s3://{bucket_name}/migration-log.txt"
"""

        # Encode script as base64 for User Data
        user_data_b64 = base64.b64encode(migration_script.encode("utf-8")).decode("utf-8")

        print("🔄 STOPPING INSTANCE:")
        print("=" * 80)
        print(f"Stopping instance: {instance_id}")

        ec2.stop_instances(InstanceIds=[instance_id])
        print("✅ Stop command sent")
        print("⏳ Waiting for instance to stop...")

        # Wait for instance to stop
        waiter = ec2.get_waiter("instance_stopped")
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})

        print("✅ Instance stopped")
        print()

        print("📝 SETTING USER DATA:")
        print("=" * 80)
        print("Configuring migration script as User Data...")

        # Modify instance User Data
        ec2.modify_instance_attribute(InstanceId=instance_id, UserData={"Value": user_data_b64})

        print("✅ User Data configured")
        print()

        print("🚀 STARTING INSTANCE:")
        print("=" * 80)
        print("Starting instance with migration script...")

        ec2.start_instances(InstanceIds=[instance_id])
        print("✅ Start command sent")
        print("⏳ Waiting for instance to start...")

        # Wait for instance to start
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})

        print("✅ Instance started")
        print()

        print("📋 MIGRATION STATUS:")
        print("=" * 80)
        print("🔄 Migration is now running automatically via User Data")
        print("⏳ This process may take 10-30 minutes depending on data size")
        print()
        print("📊 To monitor progress:")
        print(f"1. Check S3 bucket: aws s3 ls s3://{bucket_name}/")
        print(f"2. Check migration log: aws s3 cp s3://{bucket_name}/migration-log.txt -")
        print()
        print("💰 Expected results:")
        print("- User files transferred from EBS to S3")
        print("- Monthly savings: ~$25.54")
        print("- Total optimization: ~$192.46/month")
        print()
        print("✅ Setup complete! Migration running in background.")

    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    run_userdata_migration()
