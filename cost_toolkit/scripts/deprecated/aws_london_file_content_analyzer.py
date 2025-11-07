#!/usr/bin/env python3

import json
import os
import time

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def analyze_volume_contents():
    """Start instance and analyze actual file contents of volumes"""
    setup_aws_credentials()

    print("AWS London EBS File Content Analysis")
    print("=" * 80)
    print("🔍 Starting instance and examining actual file contents")
    print("⚠️  ANALYSIS ONLY - NO DELETIONS WILL BE PERFORMED")
    print()

    ec2 = boto3.client("ec2", region_name="eu-west-2")
    instance_id = "i-05ad29f28fc8a8fdc"

    try:
        # Start the instance
        print("🚀 Starting instance for file analysis...")
        ec2.start_instances(InstanceIds=[instance_id])

        # Wait for instance to be running
        print("   Waiting for instance to reach running state...")
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id])

        # Get instance details
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]
        public_ip = instance.get("PublicIpAddress", "No public IP")

        print(f"   ✅ Instance is running at {public_ip}")
        print("   Waiting additional 30 seconds for full initialization...")
        time.sleep(30)

        # Get volume information for the specific volumes we're analyzing
        volume_ids = [
            "vol-0249308257e5fa64d",  # Tars 3 - 64 GB
            "vol-0e07da8b7b7dafa17",  # Tars 2 - 1024 GB
            "vol-089b9ed38099c68f3",  # 384 GB
        ]

        volumes_response = ec2.describe_volumes(VolumeIds=volume_ids)
        volumes = volumes_response["Volumes"]

        print(f"\n📦 Analyzing {len(volumes)} volumes:")

        for volume in volumes:
            vol_id = volume["VolumeId"]
            size = volume["Size"]

            # Get volume name
            name = "No name"
            if "Tags" in volume:
                for tag in volume["Tags"]:
                    if tag["Key"] == "Name":
                        name = tag["Value"]
                        break

            # Get device if attached
            device = "Not attached"
            if volume["Attachments"]:
                device = volume["Attachments"][0]["Device"]

            print(f"   {name} ({vol_id}): {size} GB at {device}")

        print("\n💡 MANUAL FILE ANALYSIS REQUIRED:")
        print("=" * 80)
        print("The instance is now running. To compare file contents:")
        print()
        print("1. SSH into the instance:")
        print(f"   ssh -i your-key.pem ec2-user@{public_ip}")
        print()
        print("2. Check current mounts:")
        print("   df -h")
        print("   lsblk")
        print()
        print("3. Create mount points for comparison:")
        print("   sudo mkdir -p /mnt/tars2 /mnt/vol384")
        print()
        print("4. Mount volumes read-only for safe comparison:")
        print("   # Find the correct device names first")
        print("   lsblk")
        print("   # Then mount (adjust device names as needed)")
        print("   sudo mount -o ro /dev/xvdf /mnt/tars2")
        print("   sudo mount -o ro /dev/xvdg /mnt/vol384")
        print()
        print("5. Compare directory structures:")
        print("   sudo ls -la /mnt/tars2/")
        print("   sudo ls -la /mnt/vol384/")
        print()
        print("6. Compare file counts and sizes:")
        print("   sudo find /mnt/tars2 -type f | wc -l")
        print("   sudo find /mnt/vol384 -type f | wc -l")
        print("   sudo du -sh /mnt/tars2/*")
        print("   sudo du -sh /mnt/vol384/*")
        print()
        print("7. Look for identical directory structures:")
        print("   sudo find /mnt/tars2 -type d | sort > /tmp/tars2_dirs.txt")
        print("   sudo find /mnt/vol384 -type d | sort > /tmp/vol384_dirs.txt")
        print("   diff /tmp/tars2_dirs.txt /tmp/vol384_dirs.txt")
        print()
        print("8. Compare specific files (if structures match):")
        print("   sudo ls -la /mnt/tars2/home/")
        print("   sudo ls -la /mnt/vol384/home/")
        print("   # Compare modification times of key files")
        print()
        print("9. Check for duplicate content:")
        print("   # If you find matching directories, compare file checksums")
        print("   sudo find /mnt/tars2 -type f -exec md5sum {} + | head -20")
        print("   sudo find /mnt/vol384 -type f -exec md5sum {} + | head -20")
        print()
        print("10. When done, unmount and stop instance:")
        print("    sudo umount /mnt/tars2 /mnt/vol384")
        print("    # Then stop the instance from AWS console or CLI")
        print()

        print("🎯 WHAT TO LOOK FOR:")
        print("=" * 80)
        print("• If vol384 has identical directory structure to Tars2 → Likely duplicate")
        print("• If vol384 has subset of Tars2 files → Likely older version")
        print("• If vol384 has completely different files → Keep both")
        print("• If vol384 is mostly empty → Safe to remove")
        print("• Compare modification dates - newer files indicate active volume")
        print()

        print("⚠️  IMPORTANT:")
        print("   The instance is currently RUNNING and incurring charges.")
        print("   Complete your analysis and stop the instance when finished.")
        print(f"   Instance IP: {public_ip}")

        # Don't auto-stop - let user do the analysis
        print("\n🔄 Instance left running for your analysis...")
        print("   Stop it manually when file comparison is complete.")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("\n🛑 Attempting to stop instance to avoid charges...")
        try:
            ec2.stop_instances(InstanceIds=[instance_id])
            print("   ✅ Instance stop initiated")
        except:
            print("   ⚠️  Could not stop instance - check AWS console")


if __name__ == "__main__":
    analyze_volume_contents()
