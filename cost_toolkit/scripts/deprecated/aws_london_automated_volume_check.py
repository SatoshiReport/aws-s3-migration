#!/usr/bin/env python3

import json
import os
import time

import boto3

SSM_STATUS_MAX_ATTEMPTS = 30


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def run_volume_analysis():
    """Run automated volume analysis using AWS Systems Manager"""
    setup_aws_credentials()

    print("AWS London Automated Volume Duplicate Check")
    print("=" * 80)
    print("🔍 Running automated analysis of the 3 remaining EBS volumes")
    print("⚠️  ANALYSIS ONLY - NO DELETIONS WILL BE PERFORMED")
    print()

    ssm = boto3.client("ssm", region_name="eu-west-2")
    instance_id = "i-05ad29f28fc8a8fdc"

    # Command to analyze volumes
    analysis_command = """
# Basic system info
echo "=== VOLUME DUPLICATE ANALYSIS ==="
echo "Instance: $(curl -s http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo 'Unknown')"
echo "Date: $(date)"
echo

# Show current mounts and block devices
echo "=== CURRENT SYSTEM STATE ==="
echo "Mounted filesystems:"
df -h
echo
echo "Block devices:"
lsblk
echo

# Analyze each volume
echo "=== VOLUME ANALYSIS ==="

echo "--- Volume /dev/sda1 (Tars 3 - 64GB Boot Volume) ---"
sudo file -s /dev/sda1
if mount | grep -q /dev/sda1; then
    echo "Volume is currently mounted"
    mount_point=$(mount | grep /dev/sda1 | awk '{print $3}' | head -1)
    echo "Mount point: $mount_point"
    echo "Contents:"
    ls -la $mount_point/ 2>/dev/null | head -15
    echo "Disk usage:"
    du -sh $mount_point/* 2>/dev/null | sort -hr | head -10
else
    echo "Volume not currently mounted - attempting read-only mount"
    sudo mkdir -p /tmp/check_sda1
    if sudo mount -o ro /dev/sda1 /tmp/check_sda1 2>/dev/null; then
        echo "Successfully mounted for analysis"
        echo "Contents:"
        sudo ls -la /tmp/check_sda1/ | head -15
        echo "Disk usage:"
        sudo du -sh /tmp/check_sda1/* 2>/dev/null | sort -hr | head -10
        sudo umount /tmp/check_sda1
    else
        echo "Could not mount - checking raw device"
        sudo hexdump -C /dev/sda1 | head -3
    fi
fi
echo

echo "--- Volume /dev/sde (Tars 2 - 1024GB Data Volume) ---"
sudo file -s /dev/sde
if mount | grep -q /dev/sde; then
    echo "Volume is currently mounted"
    mount_point=$(mount | grep /dev/sde | awk '{print $3}' | head -1)
    echo "Mount point: $mount_point"
    echo "Contents:"
    ls -la $mount_point/ 2>/dev/null | head -15
    echo "Disk usage:"
    du -sh $mount_point/* 2>/dev/null | sort -hr | head -10
else
    echo "Volume not currently mounted - attempting read-only mount"
    sudo mkdir -p /tmp/check_sde
    if sudo mount -o ro /dev/sde /tmp/check_sde 2>/dev/null; then
        echo "Successfully mounted for analysis"
        echo "Contents:"
        sudo ls -la /tmp/check_sde/ | head -15
        echo "Disk usage:"
        sudo du -sh /tmp/check_sde/* 2>/dev/null | sort -hr | head -10
        sudo umount /tmp/check_sde
    else
        echo "Could not mount - checking raw device"
        sudo hexdump -C /dev/sde | head -3
    fi
fi
echo

echo "--- Volume /dev/sdd (384GB Data Volume) ---"
sudo file -s /dev/sdd
if mount | grep -q /dev/sdd; then
    echo "Volume is currently mounted"
    mount_point=$(mount | grep /dev/sdd | awk '{print $3}' | head -1)
    echo "Mount point: $mount_point"
    echo "Contents:"
    ls -la $mount_point/ 2>/dev/null | head -15
    echo "Disk usage:"
    du -sh $mount_point/* 2>/dev/null | sort -hr | head -10
else
    echo "Volume not currently mounted - attempting read-only mount"
    sudo mkdir -p /tmp/check_sdd
    if sudo mount -o ro /dev/sdd /tmp/check_sdd 2>/dev/null; then
        echo "Successfully mounted for analysis"
        echo "Contents:"
        sudo ls -la /tmp/check_sdd/ | head -15
        echo "Disk usage:"
        sudo du -sh /tmp/check_sdd/* 2>/dev/null | sort -hr | head -10
        sudo umount /tmp/check_sdd
    else
        echo "Could not mount - checking raw device"
        sudo hexdump -C /dev/sdd | head -3
    fi
fi
echo

echo "=== DUPLICATE ANALYSIS SUMMARY ==="
echo "Review the above output for:"
echo "1. Similar directory structures between volumes"
echo "2. Similar file sizes and types"
echo "3. Overlapping content that might indicate duplicates"
echo "4. Different purposes (boot vs data vs backup)"
echo
echo "Analysis complete - review output above for duplicate indicators"
"""

    try:
        print("📡 Sending analysis command to instance via AWS Systems Manager...")

        response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [analysis_command], "executionTimeout": ["300"]},
        )

        command_id = response["Command"]["CommandId"]
        print(f"   Command ID: {command_id}")
        print("   Waiting for command execution...")

        # Wait for command to complete
        max_attempts = SSM_STATUS_MAX_ATTEMPTS
        attempt = 0

        while attempt < max_attempts:
            try:
                result = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)

                status = result["Status"]
                print(f"   Status: {status}")

                if status in ["Success", "Failed", "Cancelled", "TimedOut"]:
                    break

                time.sleep(5)
                attempt += 1

            except Exception as e:
                if "InvocationDoesNotExist" in str(e):
                    time.sleep(5)
                    attempt += 1
                    continue
                else:
                    raise e

        if status == "Success":
            print("   ✅ Command executed successfully!")
            print()
            print("📋 VOLUME ANALYSIS RESULTS:")
            print("=" * 80)
            print(result["StandardOutputContent"])

            if result.get("StandardErrorContent"):
                print("⚠️  Errors/Warnings:")
                print(result["StandardErrorContent"])

        else:
            print(f"   ❌ Command failed with status: {status}")
            if result.get("StandardErrorContent"):
                print(f"   Error: {result['StandardErrorContent']}")

    except Exception as e:
        print(f"❌ Error running analysis: {str(e)}")
        print()
        print("💡 Alternative: Manual SSH analysis is available")
        print("   The instance is running at IP: 18.132.211.58")
        print("   Use the SSH commands provided earlier for manual analysis")


if __name__ == "__main__":
    run_volume_analysis()
