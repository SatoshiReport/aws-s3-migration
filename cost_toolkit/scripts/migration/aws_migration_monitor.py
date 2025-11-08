#!/usr/bin/env python3

import os
import time
from datetime import datetime

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def monitor_migration():  # noqa: PLR0915
    """Monitor the EBS to S3 migration progress"""
    setup_aws_credentials()

    print("AWS Migration Monitor")
    print("=" * 80)
    print(f"🕐 Started monitoring at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    s3 = boto3.client("s3", region_name="eu-west-2")
    bucket_name = "aws-user-files-backup-london"

    try:
        print("📊 CHECKING S3 BUCKET CONTENTS:")
        print("=" * 80)

        # List bucket contents
        try:
            response = s3.list_objects_v2(Bucket=bucket_name)

            if "Contents" in response:
                total_size = 0
                file_count = 0

                print("📁 Current files in bucket:")
                for obj in response["Contents"]:
                    size_mb = obj["Size"] / (1024 * 1024)
                    total_size += obj["Size"]
                    file_count += 1

                    # Show key files and directories
                    key = obj["Key"]
                    if any(
                        x in key
                        for x in [
                            "home/",
                            "opt/",
                            "var/",
                            "root/",
                            "data/",
                            "etc/",
                            "migration-log",
                        ]
                    ):
                        print(f"  📄 {key} ({size_mb:.2f} MB)")

                total_size_gb = total_size / (1024 * 1024 * 1024)
                print()
                print(f"📈 SUMMARY:")
                print(f"  Files: {file_count}")
                print(f"  Total size: {total_size_gb:.2f} GB")
                print(f"  Estimated monthly cost: ${total_size_gb * 0.023:.2f}")

            else:
                print("📭 No files found yet - migration may still be starting")

        except Exception as e:
            print(f"⚠️ Could not list bucket contents: {str(e)}")

        print()
        print("📋 CHECKING MIGRATION LOG:")
        print("=" * 80)

        # Try to get migration log
        try:
            log_response = s3.get_object(Bucket=bucket_name, Key="migration-log.txt")
            log_content = log_response["Body"].read().decode("utf-8")

            print("📄 Latest migration log:")
            print("-" * 40)

            # Show last 20 lines of log
            log_lines = log_content.split("\n")
            for line in log_lines[-20:]:
                if line.strip():
                    print(f"  {line}")

        except s3.exceptions.NoSuchKey:
            print("📝 Migration log not yet available - process may still be running")
        except Exception as e:
            print(f"⚠️ Could not read migration log: {str(e)}")

        print()
        print("💰 COST OPTIMIZATION SUMMARY:")
        print("=" * 80)
        print("✅ EBS Volume Cleanup:")
        print("  - Removed duplicate 'Tars' volume (1024 GB): $81.92/month")
        print("  - Removed unattached volume (32 GB): $2.56/month")
        print("  - Removed 'Tars 2' volume (1024 GB): $81.92/month")
        print("  - Subtotal EBS savings: $166.40/month")
        print()
        print("🔄 EBS to S3 Migration (in progress):")
        print("  - Current EBS cost (384GB + 64GB): $35.84/month")
        print("  - Target S3 cost (~448GB): $10.30/month")
        print("  - Expected additional savings: $25.54/month")
        print()
        print("🎯 TOTAL EXPECTED OPTIMIZATION: $191.94/month")

    except Exception as e:
        print(f"❌ Error monitoring migration: {str(e)}")


if __name__ == "__main__":
    monitor_migration()
