#!/usr/bin/env python3
"""
AWS Export Recovery Script
Checks if stuck exports have actually completed in S3 despite AWS showing 'active' status.
This addresses the known AWS issue where exports get stuck at 80% progress with 'converting' status.
"""

import os
import time
from datetime import datetime

import boto3
from dotenv import load_dotenv

EXPORT_STABILITY_MINUTES = 10


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")  # noqa: TRY003

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def check_active_exports(  # noqa: PLR0912, PLR0915
    region, aws_access_key_id, aws_secret_access_key
):  # noqa: PLR0912, PLR0915
    """Check all active export tasks in a region"""
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

    print(f"\n🔍 Checking active exports in {region}...")

    response = ec2_client.describe_export_image_tasks()
    active_exports = []

    for task in response["ExportImageTasks"]:
        if task["Status"] == "active":
            active_exports.append(task)

    if not active_exports:
        print(f"   ✅ No active exports found in {region}")
        return []

    print(f"   📊 Found {len(active_exports)} active export(s)")

    recovered_exports = []

    for task in active_exports:
        export_task_id = task["ExportImageTaskId"]
        ami_id = task.get("ImageId", "unknown")
        progress = task.get("Progress", "N/A")
        status_msg = task.get("StatusMessage", "")

        print(f"\n   🔍 Checking export {export_task_id}:")
        print(f"      AMI: {ami_id}")
        print(f"      Progress: {progress}%")
        print(f"      Status Message: {status_msg}")

        # Check if this is the classic 80% stuck scenario
        if progress == "80" and status_msg == "converting":
            print(f"      ⚠️  Classic 80% stuck scenario detected!")

            # Try to find the S3 file
            s3_location = task.get("S3ExportLocation", {})
            bucket_name = s3_location.get("S3Bucket", "")
            s3_prefix = s3_location.get("S3Prefix", "")

            if bucket_name:
                # Construct expected S3 key
                s3_key = f"{s3_prefix}{export_task_id}.vmdk"

                print(f"      🔍 Checking S3: s3://{bucket_name}/{s3_key}")

                try:
                    # Check if S3 file exists
                    response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
                    file_size_bytes = response["ContentLength"]
                    file_size_gb = file_size_bytes / (1024**3)
                    last_modified = response["LastModified"]

                    print(f"      ✅ S3 file exists!")
                    print(f"      📏 Size: {file_size_gb:.2f} GB ({file_size_bytes:,} bytes)")
                    print(f"      📅 Last modified: {last_modified}")

                    # Check if file is stable (not being written to)
                    time_since_modified = datetime.now(last_modified.tzinfo) - last_modified
                    minutes_since_modified = time_since_modified.total_seconds() / 60

                    if minutes_since_modified > EXPORT_STABILITY_MINUTES:
                        print(
                            f"      ✅ File appears stable (last modified {minutes_since_modified:.1f} minutes ago)"
                        )
                        print(f"      🎉 EXPORT LIKELY COMPLETED SUCCESSFULLY!")

                        recovered_exports.append(
                            {
                                "export_task_id": export_task_id,
                                "ami_id": ami_id,
                                "bucket_name": bucket_name,
                                "s3_key": s3_key,
                                "size_gb": file_size_gb,
                                "status": "recovered",
                            }
                        )
                    else:
                        print(
                            f"      ⏳ File still being written (modified {minutes_since_modified:.1f} minutes ago)"
                        )

                except s3_client.exceptions.NoSuchKey:
                    print(f"      ❌ S3 file not found - export may have genuinely failed")
                except Exception as e:
                    print(f"      ❌ Error checking S3: {e}")
            else:
                print(f"      ❌ No S3 bucket information found in export task")
        else:
            print(f"      ℹ️  Not the classic stuck scenario - continuing to monitor")

    return recovered_exports


def main():
    """Main recovery function"""
    print("AWS Export Recovery Script")
    print("=" * 50)
    print("Checking for stuck exports that may have actually completed...")

    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    # Check common regions where exports might be running
    regions_to_check = ["us-east-2", "eu-west-2", "us-east-1", "us-west-2"]

    all_recovered = []

    for region in regions_to_check:
        try:
            recovered = check_active_exports(region, aws_access_key_id, aws_secret_access_key)
            all_recovered.extend(recovered)
        except Exception as e:
            print(f"\n❌ Error checking {region}: {e}")

    print("\n" + "=" * 50)
    print("🎯 RECOVERY SUMMARY")
    print("=" * 50)

    if all_recovered:
        print(f"✅ Found {len(all_recovered)} likely completed export(s):")

        total_size_gb = 0
        for export in all_recovered:
            print(f"\n   📦 Export: {export['export_task_id']}")
            print(f"      AMI: {export['ami_id']}")
            print(f"      S3: s3://{export['bucket_name']}/{export['s3_key']}")
            print(f"      Size: {export['size_gb']:.2f} GB")
            total_size_gb += export["size_gb"]

        print(f"\n💾 Total recovered data: {total_size_gb:.2f} GB")

        # Calculate cost savings
        ebs_monthly_cost = total_size_gb * 0.05
        s3_monthly_cost = total_size_gb * 0.023
        monthly_savings = ebs_monthly_cost - s3_monthly_cost

        print(f"💰 Monthly savings: ${monthly_savings:.2f}")
        print(f"💰 Annual savings: ${monthly_savings * 12:.2f}")

        print(f"\n📝 Next Steps:")
        print(f"1. Verify files in S3 console")
        print(f"2. Test restore process if needed")
        print(f"3. Clean up temporary AMIs")
        print(f"4. Delete original EBS snapshots")

    else:
        print("❌ No completed exports found")
        print("   All active exports are still genuinely in progress")


if __name__ == "__main__":
    main()
