#!/usr/bin/env python3

import json
import os
import time

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def setup_ssm_and_migrate():
    """Setup SSM permissions and run migration"""
    setup_aws_credentials()

    print("AWS SSM Setup and Migration")
    print("=" * 80)
    print("🔧 Setting up SSM permissions and running migration")
    print()

    ec2 = boto3.client("ec2", region_name="eu-west-2")
    iam = boto3.client("iam", region_name="eu-west-2")
    ssm = boto3.client("ssm", region_name="eu-west-2")

    instance_id = "i-05ad29f28fc8a8fdc"
    bucket_name = "aws-user-files-backup-london"
    role_name = "EC2-SSM-Role"
    instance_profile_name = "EC2-SSM-InstanceProfile"

    try:
        print("🔧 STEP 1: CREATE IAM ROLE FOR SSM")
        print("=" * 50)

        # Create IAM role for EC2 with SSM permissions
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        try:
            iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Role for EC2 to use SSM and S3",
            )
            print(f"✅ Created IAM role: {role_name}")
        except iam.exceptions.EntityAlreadyExistsException:
            print(f"✅ IAM role already exists: {role_name}")

        # Attach SSM managed policy
        try:
            iam.attach_role_policy(
                RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
            )
            print("✅ Attached SSM managed policy")
        except Exception as e:
            print(f"⚠️ Policy attachment: {str(e)}")

        # Attach S3 full access policy
        try:
            iam.attach_role_policy(
                RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess"
            )
            print("✅ Attached S3 full access policy")
        except Exception as e:
            print(f"⚠️ S3 policy attachment: {str(e)}")

        # Create instance profile
        try:
            iam.create_instance_profile(InstanceProfileName=instance_profile_name)
            print(f"✅ Created instance profile: {instance_profile_name}")
        except iam.exceptions.EntityAlreadyExistsException:
            print(f"✅ Instance profile already exists: {instance_profile_name}")

        # Add role to instance profile
        try:
            iam.add_role_to_instance_profile(
                InstanceProfileName=instance_profile_name, RoleName=role_name
            )
            print("✅ Added role to instance profile")
        except Exception as e:
            print(f"⚠️ Role to profile: {str(e)}")

        print()
        print("🔧 STEP 2: ATTACH INSTANCE PROFILE TO EC2")
        print("=" * 50)

        # Stop instance to attach IAM role
        print("🛑 Stopping instance to attach IAM role...")
        ec2.stop_instances(InstanceIds=[instance_id])

        # Wait for instance to stop
        waiter = ec2.get_waiter("instance_stopped")
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})
        print("✅ Instance stopped")

        # Attach instance profile
        try:
            ec2.associate_iam_instance_profile(
                InstanceId=instance_id, IamInstanceProfile={"Name": instance_profile_name}
            )
            print("✅ Attached IAM instance profile")
        except Exception as e:
            print(f"⚠️ Instance profile attachment: {str(e)}")

        # Start instance
        print("🚀 Starting instance...")
        ec2.start_instances(InstanceIds=[instance_id])

        # Wait for instance to start
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})
        print("✅ Instance started")

        # Wait additional time for SSM agent to register
        print("⏳ Waiting for SSM agent to register (60 seconds)...")
        time.sleep(60)

        print()
        print("🔧 STEP 3: RUN MIGRATION VIA SSM")
        print("=" * 50)

        # Create migration script
        migration_script = f"""#!/bin/bash
set -e

echo "🚀 Starting EBS to S3 migration..."
echo "Target bucket: {bucket_name}"
echo "$(date): Migration started"

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

        # Execute migration via SSM
        try:
            response = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": [migration_script], "executionTimeout": ["7200"]},
                TimeoutSeconds=7200,
            )

            command_id = response["Command"]["CommandId"]
            print(f"✅ Migration command sent successfully")
            print(f"📋 Command ID: {command_id}")
            print()

            # Monitor execution
            print("⏳ Monitoring migration progress...")

            for i in range(120):  # Check for up to 20 minutes
                time.sleep(10)

                try:
                    result = ssm.get_command_invocation(
                        CommandId=command_id, InstanceId=instance_id
                    )

                    status = result["Status"]
                    print(f"📊 Status: {status} ({i+1}/120)")

                    if status == "Success":
                        print("✅ Migration completed successfully!")
                        print("\n📄 Final output:")
                        if result.get("StandardOutputContent"):
                            output = result["StandardOutputContent"]
                            print(output[-2000:])  # Last 2000 chars
                        break
                    elif status == "Failed":
                        print("❌ Migration failed!")
                        if result.get("StandardErrorContent"):
                            print("\n❌ Error output:")
                            print(result["StandardErrorContent"][-1000:])
                        break
                    elif status in ["InProgress", "Pending"]:
                        continue
                    else:
                        print(f"⚠️ Unexpected status: {status}")

                except Exception as e:
                    print(f"⚠️ Status check error: {str(e)}")

            print()
            print("📊 Running final verification...")

        except Exception as e:
            print(f"❌ SSM execution error: {str(e)}")

    except Exception as e:
        print(f"❌ Setup error: {str(e)}")


if __name__ == "__main__":
    setup_ssm_and_migrate()
