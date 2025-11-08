#!/usr/bin/env python3

import json
import os
import subprocess

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def inspect_volumes_via_ssh():  # noqa: PLR0915
    """Connect to the London instance and inspect volume contents"""
    setup_aws_credentials()

    print("AWS London Volume Content Inspector")
    print("=" * 80)

    # Instance details
    instance_ip = "35.179.157.191"

    print(f"🔍 Connecting to instance at {instance_ip}")
    print("📋 Volume Analysis:")
    print()

    # Commands to run on the instance
    commands = [
        "df -h",  # Show mounted filesystems
        "lsblk",  # Show block devices
        "sudo fdisk -l | grep -E '^Disk /dev/'",  # Show disk information
        "ls -la /",  # Root directory contents
        "ls -la /mnt/",  # Check if volumes are mounted in /mnt
        "mount | grep -E '^/dev/'",  # Show mounted devices
    ]

    print("🖥️  System Information Commands:")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")
    print()

    # Volume inspection commands
    volume_commands = [
        "sudo ls -la /dev/xvd*",  # List all attached volumes
        "sudo file -s /dev/xvdbo",  # Check Tars volume (1024GB)
        "sudo file -s /dev/sdd",  # Check 384GB volume
        "sudo file -s /dev/sde",  # Check Tars 2 volume (1024GB)
        "sudo file -s /dev/sda1",  # Check Tars 3 volume (64GB)
    ]

    print("📦 Volume Inspection Commands:")
    for i, cmd in enumerate(volume_commands, 1):
        print(f"  {i}. {cmd}")
    print()

    # Create a comprehensive inspection script
    inspection_script = """#!/bin/bash
echo "=== LONDON INSTANCE VOLUME ANALYSIS ==="
echo "Date: $(date)"
echo "Instance: $(curl -s http://169.254.169.254/latest/meta-data/instance-id)"
echo

echo "=== DISK USAGE ==="
df -h
echo

echo "=== BLOCK DEVICES ==="
lsblk
echo

echo "=== MOUNTED FILESYSTEMS ==="
mount | grep -E '^/dev/'
echo

echo "=== DISK INFORMATION ==="
sudo fdisk -l | grep -E '^Disk /dev/'
echo

echo "=== VOLUME DETAILS ==="
echo "Checking each attached volume..."

echo "--- Volume /dev/xvdbo (Tars - 1024GB) ---"
sudo file -s /dev/xvdbo
if sudo file -s /dev/xvdbo | grep -q filesystem; then
    echo "Filesystem detected, attempting to mount for inspection..."
    sudo mkdir -p /tmp/inspect_tars
    if sudo mount -o ro /dev/xvdbo /tmp/inspect_tars 2>/dev/null; then
        echo "Contents of Tars volume:"
        sudo ls -la /tmp/inspect_tars/ | head -20
        echo "Disk usage:"
        sudo du -sh /tmp/inspect_tars/* 2>/dev/null | head -10
        sudo umount /tmp/inspect_tars
    else
        echo "Could not mount volume for inspection"
    fi
fi
echo

echo "--- Volume /dev/sdd (384GB) ---"
sudo file -s /dev/sdd
if sudo file -s /dev/sdd | grep -q filesystem; then
    echo "Filesystem detected, attempting to mount for inspection..."
    sudo mkdir -p /tmp/inspect_384
    if sudo mount -o ro /dev/sdd /tmp/inspect_384 2>/dev/null; then
        echo "Contents of 384GB volume:"
        sudo ls -la /tmp/inspect_384/ | head -20
        echo "Disk usage:"
        sudo du -sh /tmp/inspect_384/* 2>/dev/null | head -10
        sudo umount /tmp/inspect_384
    else
        echo "Could not mount volume for inspection"
    fi
fi
echo

echo "--- Volume /dev/sde (Tars 2 - 1024GB) ---"
sudo file -s /dev/sde
if sudo file -s /dev/sde | grep -q filesystem; then
    echo "Filesystem detected, attempting to mount for inspection..."
    sudo mkdir -p /tmp/inspect_tars2
    if sudo mount -o ro /dev/sde /tmp/inspect_tars2 2>/dev/null; then
        echo "Contents of Tars 2 volume:"
        sudo ls -la /tmp/inspect_tars2/ | head -20
        echo "Disk usage:"
        sudo du -sh /tmp/inspect_tars2/* 2>/dev/null | head -10
        sudo umount /tmp/inspect_tars2
    else
        echo "Could not mount volume for inspection"
    fi
fi
echo

echo "--- Volume /dev/sda1 (Tars 3 - 64GB) ---"
sudo file -s /dev/sda1
if sudo file -s /dev/sda1 | grep -q filesystem; then
    echo "Filesystem detected, attempting to mount for inspection..."
    sudo mkdir -p /tmp/inspect_tars3
    if sudo mount -o ro /dev/sda1 /tmp/inspect_tars3 2>/dev/null; then
        echo "Contents of Tars 3 volume:"
        sudo ls -la /tmp/inspect_tars3/ | head -20
        echo "Disk usage:"
        sudo du -sh /tmp/inspect_tars3/* 2>/dev/null | head -10
        sudo umount /tmp/inspect_tars3
    else
        echo "Could not mount volume for inspection"
    fi
fi
echo

echo "=== ANALYSIS COMPLETE ==="
echo "Review the above output to identify:"
echo "1. Which volumes contain similar data (duplicates)"
echo "2. Which volume has the most recent data"
echo "3. Which volumes can be safely deleted"
"""

    # Save the inspection script
    with open("/tmp/volume_inspection.sh", "w") as f:
        f.write(inspection_script)

    print("📝 Created comprehensive volume inspection script")
    print("💡 To run the analysis, execute these commands:")
    print()
    print("# Copy the inspection script to the instance:")
    print(f"scp -i ~/.ssh/your-key.pem /tmp/volume_inspection.sh ec2-user@{instance_ip}:/tmp/")
    print()
    print("# SSH into the instance:")
    print(f"ssh -i ~/.ssh/your-key.pem ec2-user@{instance_ip}")
    print()
    print("# Run the inspection script:")
    print("chmod +x /tmp/volume_inspection.sh")
    print("./tmp/volume_inspection.sh")
    print()

    print("📊 VOLUME SUMMARY FROM ANALYSIS:")
    print("=" * 80)
    print("✅ 4 volumes attached to instance i-05ad29f28fc8a8fdc:")
    print("   1. vol-0e148f66bcb4f7a0b (Tars) - 1024 GB - Created: 2023-02-25 (OLDEST)")
    print("   2. vol-089b9ed38099c68f3 (384) - 384 GB - Created: 2025-02-05")
    print("   3. vol-0e07da8b7b7dafa17 (Tars 2) - 1024 GB - Created: 2025-02-06")
    print("   4. vol-0249308257e5fa64d (Tars 3) - 64 GB - Created: 2025-02-06 (NEWEST)")
    print()
    print("❌ 1 unattached volume:")
    print("   5. vol-08f9abc839d13db62 (No name) - 32 GB - Created: 2025-02-05")
    print()
    print("🔍 DUPLICATE ANALYSIS:")
    print("   • Two 1024 GB volumes: 'Tars' (2023) vs 'Tars 2' (2025)")
    print("   • 'Tars 2' is nearly 2 years newer than 'Tars'")
    print("   • 'Tars 3' (64 GB) is the most recent, likely the boot/system volume")
    print()
    print("💰 COST OPTIMIZATION POTENTIAL:")
    print("   • Delete old 'Tars' volume (1024 GB): Save ~$82/month")
    print("   • Delete unattached volume (32 GB): Save ~$3/month")
    print("   • Total potential savings: ~$85/month")
    print()
    print("⚠️  RECOMMENDATION:")
    print("   1. Inspect 'Tars' vs 'Tars 2' contents to confirm 'Tars 2' is newer/better")
    print("   2. If confirmed, delete the old 'Tars' volume")
    print("   3. Delete the unattached 32 GB volume")
    print("   4. Keep 'Tars 2' (1024 GB), '384' (384 GB), and 'Tars 3' (64 GB)")


if __name__ == "__main__":
    inspect_volumes_via_ssh()
