#!/usr/bin/env python3

import os
import time

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def analyze_remaining_volumes():
    """Start instance and analyze the 3 remaining EBS volumes for duplicates"""
    setup_aws_credentials()

    print("AWS London Volume Content Analysis")
    print("=" * 80)
    print("⚠️  ANALYSIS ONLY - NO DELETIONS WILL BE PERFORMED")
    print()

    ec2 = boto3.client("ec2", region_name="eu-west-2")

    # Start the instance
    print("🚀 Starting instance i-05ad29f28fc8a8fdc for volume analysis...")
    try:
        ec2.start_instances(InstanceIds=["i-05ad29f28fc8a8fdc"])
        print("   Instance start initiated. Waiting for running state...")

        # Wait for instance to be running
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=["i-05ad29f28fc8a8fdc"])

        # Get instance details
        response = ec2.describe_instances(InstanceIds=["i-05ad29f28fc8a8fdc"])
        instance = response["Reservations"][0]["Instances"][0]
        public_ip = instance.get("PublicIpAddress", "No public IP")
        private_ip = instance.get("PrivateIpAddress", "No private IP")

        print(f"   ✅ Instance is now running!")
        print(f"   Public IP: {public_ip}")
        print(f"   Private IP: {private_ip}")

    except Exception as e:
        print(f"   ❌ Error starting instance: {str(e)}")
        return

    print()
    print("📦 Remaining 3 EBS Volumes to Analyze:")
    print("   • vol-0249308257e5fa64d (Tars 3) - 64 GB - Boot/system volume")
    print("   • vol-0e07da8b7b7dafa17 (Tars 2) - 1024 GB - Data volume")
    print("   • vol-089b9ed38099c68f3 (384) - 384 GB - Data volume")
    print()

    # Create comprehensive volume analysis script
    analysis_script = """#!/bin/bash
echo "=== LONDON EBS VOLUME DUPLICATE ANALYSIS ==="
echo "Date: $(date)"
echo "Instance: $(curl -s http://169.254.169.254/latest/meta-data/instance-id)"
echo "Analysis Purpose: Check for duplicate content between remaining volumes"
echo

echo "=== SYSTEM OVERVIEW ==="
echo "Current disk usage:"
df -h
echo

echo "Block devices:"
lsblk
echo

echo "Mounted filesystems:"
mount | grep -E '^/dev/'
echo

echo "=== VOLUME ANALYSIS ==="
echo "Analyzing each volume for content and potential duplicates..."
echo

# Function to safely analyze a volume
analyze_volume() {
    local device=$1
    local name=$2
    local size=$3
    local mount_point="/tmp/analyze_${name,,}"
    
    echo "--- Analyzing $device ($name - $size) ---"
    
    # Check filesystem type
    echo "Filesystem type:"
    sudo file -s $device
    
    # Try to mount read-only for analysis
    sudo mkdir -p $mount_point
    if sudo mount -o ro $device $mount_point 2>/dev/null; then
        echo "✅ Successfully mounted for analysis"
        
        echo "Root directory contents:"
        sudo ls -la $mount_point/ 2>/dev/null | head -20
        
        echo "Directory sizes (top 10):"
        sudo du -sh $mount_point/* 2>/dev/null | sort -hr | head -10
        
        echo "File count by type:"
        sudo find $mount_point -type f 2>/dev/null | head -1000 | xargs -I {} file {} 2>/dev/null | cut -d: -f2 | sort | uniq -c | sort -nr | head -10
        
        echo "Recent files (last 30 days):"
        sudo find $mount_point -type f -mtime -30 2>/dev/null | head -10
        
        echo "Large files (>100MB):"
        sudo find $mount_point -type f -size +100M 2>/dev/null | head -10
        
        # Look for common duplicate indicators
        echo "Checking for common directories that might indicate duplicates:"
        for common_dir in home var opt usr/local etc/config; do
            if sudo ls -d $mount_point/$common_dir 2>/dev/null; then
                echo "  Found: /$common_dir"
                sudo ls -la $mount_point/$common_dir 2>/dev/null | head -5
            fi
        done
        
        # Unmount
        sudo umount $mount_point
        echo "✅ Volume unmounted"
        
    else
        echo "❌ Could not mount volume (may be encrypted, corrupted, or different filesystem)"
        
        # Try to get basic info without mounting
        echo "Attempting basic analysis without mounting:"
        sudo hexdump -C $device | head -5
    fi
    
    echo
}

# Analyze each volume
analyze_volume "/dev/sda1" "Tars_3" "64GB"
analyze_volume "/dev/sde" "Tars_2" "1024GB" 
analyze_volume "/dev/sdd" "384GB_Volume" "384GB"

echo "=== DUPLICATE ANALYSIS SUMMARY ==="
echo "Compare the above outputs to identify:"
echo "1. Volumes with similar directory structures"
echo "2. Volumes with similar file types and counts"
echo "3. Volumes with overlapping recent file dates"
echo "4. Volumes with similar large files"
echo
echo "Key indicators of duplicates:"
echo "- Same directory structure (home, var, opt, etc.)"
echo "- Similar file counts and types"
echo "- Overlapping modification dates"
echo "- Same large files or applications"
echo
echo "=== ANALYSIS COMPLETE ==="
"""

    # Save the analysis script
    with open("/tmp/volume_duplicate_analysis.sh", "w") as f:
        f.write(analysis_script)

    print("📝 Created comprehensive volume duplicate analysis script")
    print()
    print("💡 To perform the duplicate analysis, execute these commands:")
    print()
    print("# Copy the analysis script to the instance:")
    print(
        f"scp -i ~/.ssh/your-key.pem /tmp/volume_duplicate_analysis.sh ec2-user@{public_ip}:/tmp/"
    )
    print()
    print("# SSH into the instance:")
    print(f"ssh -i ~/.ssh/your-key.pem ec2-user@{public_ip}")
    print()
    print("# Run the analysis script:")
    print("chmod +x /tmp/volume_duplicate_analysis.sh")
    print("./tmp/volume_duplicate_analysis.sh")
    print()

    print("🔍 WHAT TO LOOK FOR IN THE ANALYSIS:")
    print("=" * 80)
    print("📋 Duplicate Indicators:")
    print("   • Similar directory structures (/home, /var, /opt, etc.)")
    print("   • Same file types and counts")
    print("   • Overlapping modification dates")
    print("   • Identical large files or applications")
    print("   • Similar disk usage patterns")
    print()
    print("📦 Volume Expectations:")
    print("   • Tars 3 (64 GB): Likely boot/OS volume - should have /boot, /etc, /usr")
    print("   • Tars 2 (1024 GB): Data volume - may have /home, applications, data")
    print("   • 384 GB: Secondary data - could be backup or different data set")
    print()
    print("⚠️  Remember: Instance is running - stop it after analysis to avoid charges!")


if __name__ == "__main__":
    analyze_remaining_volumes()
