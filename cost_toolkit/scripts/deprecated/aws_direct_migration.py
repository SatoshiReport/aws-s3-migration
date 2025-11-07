#!/usr/bin/env python3

import json
import os
import time

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def run_direct_migration():
    """Run migration using EC2 Instance Connect"""
    setup_aws_credentials()

    print("AWS Direct Migration via Instance Connect")
    print("=" * 80)
    print("🚀 Running migration directly on EC2 instance")
    print()

    ec2 = boto3.client("ec2", region_name="eu-west-2")
    ssm = boto3.client("ssm", region_name="eu-west-2")

    instance_id = "i-05ad29f28fc8a8fdc"
    bucket_name = "aws-user-files-backup-london"

    try:
        # First, install SSM agent if needed
        print("🔧 PREPARING INSTANCE:")
        print("=" * 40)

        # Create a simple migration script
        migration_commands = f"""#!/bin/bash
set -e

echo "🚀 Starting EBS to S3 migration..."
echo "Target bucket: {bucket_name}"
echo "$(date): Migration started"

# Load AWS credentials from ~/.env on the instance
if [ -f "$HOME/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$HOME/.env"
    set +a
else
    echo "Missing ~/.env with AWS credentials" >&2
    exit 1
fi

# Install AWS CLI if not present
if ! command -v aws &> /dev/null; then
    echo "Installing AWS CLI..."
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
    cd /tmp && unzip awscliv2.zip
    sudo ./aws/install
fi

# Create mount points
sudo mkdir -p /mnt/vol384 /mnt/vol64

echo "📦 Available block devices:"
lsblk

echo ""
echo "🔍 Mounting volumes..."

# Find and mount volumes by size
for dev in /dev/nvme1n1 /dev/nvme2n1 /dev/nvme3n1 /dev/xvdf /dev/xvdg /dev/xvdh; do
    if [ -b "$dev" ]; then
        size_bytes=$(lsblk -b -d -o SIZE -n $dev 2>/dev/null || echo "0")
        size_gb=$((size_bytes / 1024 / 1024 / 1024))
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
echo "🔄 Starting S3 sync..."

# Function to sync directory to S3
sync_dir() {{
    local source="$1"
    local s3_path="$2"
    
    if [ -d "$source" ] && [ "$(sudo ls -A $source 2>/dev/null)" ]; then
        echo ""
        echo "🔄 Syncing $source to s3://{bucket_name}/$s3_path/"
        sudo aws s3 sync "$source" "s3://{bucket_name}/$s3_path/" \\
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

echo ""
echo "✅ Migration complete!"
echo "$(date): Migration finished"
"""

        # Try to run via SSM with proper setup
        print("🔄 EXECUTING MIGRATION:")
        print("=" * 40)

        try:
            # Send command via SSM
            response = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={
                    "commands": [migration_commands],
                    "executionTimeout": ["7200"],  # 2 hours timeout
                },
                TimeoutSeconds=7200,
            )

            command_id = response["Command"]["CommandId"]
            print(f"✅ Migration command sent successfully")
            print(f"📋 Command ID: {command_id}")
            print()

            # Monitor command execution
            print("⏳ Monitoring execution...")

            for i in range(60):  # Check for up to 10 minutes
                time.sleep(10)

                try:
                    result = ssm.get_command_invocation(
                        CommandId=command_id, InstanceId=instance_id
                    )

                    status = result["Status"]
                    print(f"📊 Status: {status}")

                    if status == "Success":
                        print("✅ Migration completed successfully!")
                        if result.get("StandardOutputContent"):
                            print("\n📄 Output:")
                            print(result["StandardOutputContent"][-1000:])  # Last 1000 chars
                        break
                    elif status == "Failed":
                        print("❌ Migration failed!")
                        if result.get("StandardErrorContent"):
                            print("\n❌ Error:")
                            print(result["StandardErrorContent"][-1000:])
                        break
                    elif status in ["InProgress", "Pending"]:
                        print(f"⏳ Still running... ({i+1}/60)")
                        continue
                    else:
                        print(f"⚠️ Unexpected status: {status}")

                except Exception as e:
                    print(f"⚠️ Could not get command status: {str(e)}")

            print()
            print("📊 Final check - running monitor script...")

        except Exception as e:
            if "InvalidInstanceId" in str(e):
                print("❌ Instance not ready for SSM commands")
                print("💡 The instance may need SSM agent installation or IAM role")
                print()
                print("🔄 ALTERNATIVE: Manual execution")
                print("=" * 40)
                print("You can run this script manually by:")
                print("1. SSH into the instance")
                print("2. Save the migration script to a file")
                print("3. Run: chmod +x migration.sh && ./migration.sh")
                print()
                print("📝 Migration script saved to local file for reference:")

                with open("migration_script.sh", "w") as f:
                    f.write(migration_commands)
                print("✅ Script saved as: migration_script.sh")

            else:
                print(f"❌ SSM Error: {str(e)}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    run_direct_migration()
