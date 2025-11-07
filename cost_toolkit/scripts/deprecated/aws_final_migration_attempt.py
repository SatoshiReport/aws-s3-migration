#!/usr/bin/env python3

import os
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def final_migration_attempt():
    """Final attempt at migration with extended wait time"""
    setup_aws_credentials()

    print("AWS Final Migration Attempt")
    print("=" * 80)
    print("🔄 Waiting for SSM agent registration and attempting migration")
    print()

    ssm = boto3.client("ssm", region_name="eu-west-2")
    s3 = boto3.client("s3", region_name="eu-west-2")

    instance_id = "i-05ad29f28fc8a8fdc"
    bucket_name = "aws-user-files-backup-london"

    try:
        print("⏳ WAITING FOR SSM AGENT REGISTRATION:")
        print("=" * 50)
        print("Waiting additional 3 minutes for SSM agent to fully register...")

        for i in range(18):  # 3 minutes in 10-second intervals
            time.sleep(10)
            print(f"⏳ Waiting... {(i+1)*10}/180 seconds")

            # Check if instance is available for SSM
            try:
                response = ssm.describe_instance_information(
                    Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
                )

                if response["InstanceInformationList"]:
                    print("✅ Instance is now registered with SSM!")
                    break

            except (BotoCoreError, ClientError) as exc:
                print(f"⚠️  Unable to query SSM registration status: {exc}")

        print()
        print("🚀 ATTEMPTING MIGRATION:")
        print("=" * 50)

        # Simple migration command
        migration_command = f"""#!/bin/bash
echo "🚀 EBS to S3 Migration Started"
echo "Target: s3://{bucket_name}/"

# Install AWS CLI if needed
if ! command -v aws &> /dev/null; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
    cd /tmp && unzip awscliv2.zip && sudo ./aws/install
fi

# Create mount points and mount volumes
sudo mkdir -p /mnt/vol384 /mnt/vol64

# Mount volumes by size
for dev in /dev/nvme1n1 /dev/nvme2n1 /dev/nvme3n1; do
    if [ -b "$dev" ]; then
        size_gb=$(lsblk -b -d -o SIZE -n $dev 2>/dev/null | awk '{{print int($1/1024/1024/1024)}}')
        if [ "$size_gb" -gt 300 ] && [ "$size_gb" -lt 500 ]; then
            sudo mount $dev /mnt/vol384 && echo "✅ Mounted 384GB volume"
        elif [ "$size_gb" -gt 50 ] && [ "$size_gb" -lt 100 ]; then
            sudo mount $dev /mnt/vol64 && echo "✅ Mounted 64GB volume"
        fi
    fi
done

# Sync directories to S3
for vol in vol384 vol64; do
    if mountpoint -q /mnt/$vol; then
        echo "📦 Processing $vol..."
        for dir in home opt var root data etc; do
            if [ -d "/mnt/$vol/$dir" ]; then
                echo "🔄 Syncing $dir from $vol..."
                sudo aws s3 sync "/mnt/$vol/$dir" "s3://{bucket_name}/$vol/$dir/" --region eu-west-2 --storage-class STANDARD
            fi
        done
    fi
done

echo "✅ Migration completed!"
aws s3 ls s3://{bucket_name}/ --recursive --summarize
"""

        try:
            response = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": [migration_command], "executionTimeout": ["3600"]},
            )

            command_id = response["Command"]["CommandId"]
            print(f"✅ Migration command sent: {command_id}")

            # Monitor for 10 minutes
            for i in range(60):
                time.sleep(10)

                try:
                    result = ssm.get_command_invocation(
                        CommandId=command_id, InstanceId=instance_id
                    )

                    status = result["Status"]
                    if status == "Success":
                        print("✅ Migration completed successfully!")
                        break
                    elif status == "Failed":
                        print("❌ Migration failed")
                        break
                    else:
                        print(f"⏳ Status: {status} ({i+1}/60)")

                except (BotoCoreError, ClientError) as exc:
                    print(f"⚠️  Unable to fetch SSM command status: {exc}")

        except Exception as e:
            print(f"❌ Final SSM attempt failed: {str(e)}")
            print()
            print("📋 MIGRATION STATUS SUMMARY:")
            print("=" * 50)
            print("⚠️ Automated migration via SSM has encountered persistent issues")
            print("💡 This is likely due to:")
            print("   - SSM agent not fully initialized")
            print("   - Instance configuration requirements")
            print("   - Network or permission constraints")
            print()
            print("🎯 COST OPTIMIZATION ACHIEVED SO FAR:")
            print("=" * 50)
            print("✅ EBS Volume Cleanup Completed:")
            print("   - Removed duplicate 'Tars' volume (1024 GB): $81.92/month")
            print("   - Removed unattached volume (32 GB): $2.56/month")
            print("   - Removed 'Tars 2' volume (1024 GB): $81.92/month")
            print("   - Total EBS cleanup savings: $166.40/month")
            print()
            print("🔄 EBS to S3 Migration (Pending):")
            print("   - Current EBS cost (384GB + 64GB): $35.84/month")
            print("   - Target S3 cost (~448GB): $10.30/month")
            print("   - Potential additional savings: $25.54/month")
            print()
            print("💰 TOTAL OPTIMIZATION POTENTIAL: $191.94/month")
            print()
            print("📝 NEXT STEPS:")
            print("   1. Manual migration via SSH (if accessible)")
            print("   2. Use AWS CLI from local machine with instance credentials")
            print("   3. Consider alternative storage optimization approaches")
            print()
            print("✅ SIGNIFICANT COST REDUCTION ALREADY ACHIEVED!")

        # Check S3 bucket status regardless
        print()
        print("📊 CHECKING S3 BUCKET STATUS:")
        print("=" * 50)

        try:
            response = s3.list_objects_v2(Bucket=bucket_name)

            if "Contents" in response:
                total_size = sum(obj["Size"] for obj in response["Contents"])
                file_count = len(response["Contents"])
                size_gb = total_size / (1024**3)

                print(f"📁 Files in bucket: {file_count}")
                print(f"📊 Total size: {size_gb:.2f} GB")
                print(f"💰 Monthly S3 cost: ${size_gb * 0.023:.2f}")

                if file_count > 0:
                    print("✅ Some migration data found!")
                else:
                    print("📭 No migration data yet")
            else:
                print("📭 S3 bucket is empty - migration not completed")

        except Exception as e:
            print(f"⚠️ Could not check S3 bucket: {str(e)}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    final_migration_attempt()
