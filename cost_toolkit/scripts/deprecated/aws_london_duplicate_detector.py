#!/usr/bin/env python3

import json
import os
import time

import boto3

SSM_POLL_MAX_ATTEMPTS = 60


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def detect_duplicates():
    """Start instance and perform detailed duplicate detection"""
    setup_aws_credentials()

    print("AWS London EBS Duplicate Detection")
    print("=" * 80)
    print("🔍 Starting instance and performing detailed content analysis")
    print("⚠️  ANALYSIS ONLY - NO DELETIONS WILL BE PERFORMED")
    print()

    ec2 = boto3.client("ec2", region_name="eu-west-2")
    ssm = boto3.client("ssm", region_name="eu-west-2")
    instance_id = "i-05ad29f28fc8a8fdc"

    # Start the instance
    print("🚀 Starting instance for duplicate analysis...")
    try:
        ec2.start_instances(InstanceIds=[instance_id])
        print("   Instance start initiated. Waiting for running state...")

        # Wait for instance to be running
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id])

        # Get instance details
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]
        public_ip = instance.get("PublicIpAddress", "No public IP")

        print(f"   ✅ Instance is running at {public_ip}")

    except Exception as e:
        print(f"   ❌ Error starting instance: {str(e)}")
        return

    # Wait a bit for the instance to fully boot
    print("   Waiting for instance to fully initialize...")
    time.sleep(30)

    # Create comprehensive duplicate detection script
    duplicate_analysis_script = """#!/bin/bash
echo "=== COMPREHENSIVE EBS DUPLICATE DETECTION ==="
echo "Date: $(date)"
echo "Instance: $(curl -s http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null)"
echo

# Function to analyze and compare volumes
analyze_volume() {
    local device=$1
    local name=$2
    local size=$3
    local mount_point="/tmp/dup_check_${name,,}"
    
    echo "=== ANALYZING $device ($name - $size) ==="
    
    # Create mount point
    sudo mkdir -p $mount_point
    
    # Check filesystem
    echo "Filesystem type:"
    sudo file -s $device
    
    # Try to mount read-only
    if sudo mount -o ro $device $mount_point 2>/dev/null; then
        echo "✅ Successfully mounted at $mount_point"
        
        # Get detailed directory structure
        echo "Directory structure (top level):"
        sudo ls -la $mount_point/ 2>/dev/null
        
        echo "Directory sizes:"
        sudo du -sh $mount_point/* 2>/dev/null | sort -hr
        
        echo "File counts by directory:"
        for dir in $(sudo ls -d $mount_point/*/ 2>/dev/null); do
            count=$(sudo find "$dir" -type f 2>/dev/null | wc -l)
            echo "  $dir: $count files"
        done
        
        echo "Recent files (last 30 days):"
        sudo find $mount_point -type f -mtime -30 2>/dev/null | head -20
        
        echo "Large files (>50MB):"
        sudo find $mount_point -type f -size +50M 2>/dev/null | head -10
        
        # Create a signature of the volume
        echo "Volume signature (for comparison):"
        echo "  Total files: $(sudo find $mount_point -type f 2>/dev/null | wc -l)"
        echo "  Total directories: $(sudo find $mount_point -type d 2>/dev/null | wc -l)"
        echo "  Largest files:"
        sudo find $mount_point -type f -exec ls -la {} + 2>/dev/null | sort -k5 -nr | head -5
        
        # Check for common application directories
        echo "Common directories present:"
        for common in home var opt usr/local etc bin sbin lib; do
            if sudo ls -d $mount_point/$common 2>/dev/null >/dev/null; then
                size=$(sudo du -sh $mount_point/$common 2>/dev/null | cut -f1)
                echo "  /$common: $size"
            fi
        done
        
        # Generate content hash for comparison
        echo "Content fingerprint:"
        sudo find $mount_point -type f -name "*.txt" -o -name "*.log" -o -name "*.conf" 2>/dev/null | head -20 | while read file; do
            echo "  $(basename "$file"): $(sudo wc -l "$file" 2>/dev/null | cut -d' ' -f1) lines"
        done
        
        sudo umount $mount_point
        echo "✅ Volume unmounted"
        
    else
        echo "❌ Could not mount volume"
        echo "Raw device info:"
        sudo hexdump -C $device | head -5
    fi
    
    echo
}

# Analyze each volume
echo "Starting volume analysis..."
echo

analyze_volume "/dev/sda1" "Tars_3" "64GB"
analyze_volume "/dev/sde" "Tars_2" "1024GB"
analyze_volume "/dev/sdd" "384GB" "384GB"

echo "=== DUPLICATE COMPARISON ANALYSIS ==="
echo

# Now perform cross-comparison
echo "Performing duplicate detection between data volumes..."
echo

# Mount both data volumes for comparison
sudo mkdir -p /tmp/compare_tars2 /tmp/compare_384

echo "Mounting Tars 2 (1024GB) for comparison..."
if sudo mount -o ro /dev/sde /tmp/compare_tars2 2>/dev/null; then
    echo "✅ Tars 2 mounted"
    
    echo "Mounting 384GB volume for comparison..."
    if sudo mount -o ro /dev/sdd /tmp/compare_384 2>/dev/null; then
        echo "✅ 384GB volume mounted"
        
        echo "=== DETAILED DUPLICATE COMPARISON ==="
        
        # Compare directory structures
        echo "Directory structure comparison:"
        echo "Tars 2 directories:"
        sudo ls -la /tmp/compare_tars2/ | grep "^d"
        echo
        echo "384GB directories:"
        sudo ls -la /tmp/compare_384/ | grep "^d"
        echo
        
        # Compare file counts
        tars2_files=$(sudo find /tmp/compare_tars2 -type f 2>/dev/null | wc -l)
        vol384_files=$(sudo find /tmp/compare_384 -type f 2>/dev/null | wc -l)
        echo "File count comparison:"
        echo "  Tars 2: $tars2_files files"
        echo "  384GB: $vol384_files files"
        echo
        
        # Look for identical directory names
        echo "Common directory names:"
        tars2_dirs=$(sudo find /tmp/compare_tars2 -maxdepth 2 -type d -exec basename {} \; 2>/dev/null | sort | uniq)
        vol384_dirs=$(sudo find /tmp/compare_384 -maxdepth 2 -type d -exec basename {} \; 2>/dev/null | sort | uniq)
        
        for dir in $tars2_dirs; do
            if echo "$vol384_dirs" | grep -q "^$dir$"; then
                echo "  Common directory: $dir"
                # Compare sizes
                tars2_size=$(sudo du -sh /tmp/compare_tars2/*/$dir 2>/dev/null | cut -f1 | head -1)
                vol384_size=$(sudo du -sh /tmp/compare_384/*/$dir 2>/dev/null | cut -f1 | head -1)
                if [ ! -z "$tars2_size" ] && [ ! -z "$vol384_size" ]; then
                    echo "    Tars 2: $tars2_size, 384GB: $vol384_size"
                fi
            fi
        done
        echo
        
        # Check for identical files by name and size
        echo "Looking for identical files..."
        sudo find /tmp/compare_tars2 -type f -exec basename {} \; 2>/dev/null | sort > /tmp/tars2_files.txt
        sudo find /tmp/compare_384 -type f -exec basename {} \; 2>/dev/null | sort > /tmp/384_files.txt
        
        common_files=$(comm -12 /tmp/tars2_files.txt /tmp/384_files.txt | wc -l)
        echo "  Files with identical names: $common_files"
        
        if [ $common_files -gt 0 ]; then
            echo "  Sample identical filenames:"
            comm -12 /tmp/tars2_files.txt /tmp/384_files.txt | head -10
        fi
        echo
        
        # Check modification dates
        echo "Modification date analysis:"
        echo "Tars 2 - newest files:"
        sudo find /tmp/compare_tars2 -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -5 | while read timestamp file; do
            date -d "@$timestamp" "+%Y-%m-%d %H:%M" 2>/dev/null || echo "Unknown date"
            echo "  $file"
        done
        echo
        echo "384GB - newest files:"
        sudo find /tmp/compare_384 -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -5 | while read timestamp file; do
            date -d "@$timestamp" "+%Y-%m-%d %H:%M" 2>/dev/null || echo "Unknown date"
            echo "  $file"
        done
        echo
        
        sudo umount /tmp/compare_tars2 /tmp/compare_384
        echo "✅ Comparison volumes unmounted"
        
    else
        echo "❌ Could not mount 384GB volume for comparison"
        sudo umount /tmp/compare_tars2 2>/dev/null
    fi
else
    echo "❌ Could not mount Tars 2 for comparison"
fi

echo
echo "=== DUPLICATE DETECTION CONCLUSION ==="
echo "Review the above analysis to determine:"
echo "1. Do the volumes have similar directory structures?"
echo "2. Do they have similar file counts and types?"
echo "3. Do they share common files or applications?"
echo "4. Which volume appears to be newer/more complete?"
echo "5. Which volume can be safely removed?"
echo
echo "Analysis complete."
"""

    try:
        print("📡 Running comprehensive duplicate detection...")

        # Try using EC2 Instance Connect or direct command execution
        response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={
                "commands": [duplicate_analysis_script],
                "executionTimeout": ["600"],  # 10 minutes
            },
        )

        command_id = response["Command"]["CommandId"]
        print(f"   Command ID: {command_id}")
        print("   Executing duplicate detection script...")

        # Wait for command to complete
        max_attempts = SSM_POLL_MAX_ATTEMPTS  # 5 minutes
        attempt = 0

        while attempt < max_attempts:
            try:
                result = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)

                status = result["Status"]

                if status in ["Success", "Failed", "Cancelled", "TimedOut"]:
                    break

                if attempt % 6 == 0:  # Print status every 30 seconds
                    print(f"   Status: {status} (attempt {attempt + 1}/{max_attempts})")

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
            print("   ✅ Duplicate detection completed successfully!")
            print()
            print("📋 DUPLICATE DETECTION RESULTS:")
            print("=" * 80)
            print(result["StandardOutputContent"])

            if result.get("StandardErrorContent"):
                print()
                print("⚠️  Warnings/Errors:")
                print(result["StandardErrorContent"])

        else:
            print(f"   ❌ Command failed with status: {status}")
            if result.get("StandardErrorContent"):
                print(f"   Error: {result['StandardErrorContent']}")

            # Fallback to manual instructions
            print()
            print("💡 MANUAL ANALYSIS REQUIRED:")
            print(f"   SSH into instance: ssh -i ~/.ssh/your-key.pem ec2-user@{public_ip}")
            print("   Run the duplicate detection script manually")

    except Exception as e:
        print(f"❌ Error running duplicate detection: {str(e)}")
        print()
        print("💡 MANUAL ANALYSIS REQUIRED:")
        print(f"   Instance is running at: {public_ip}")
        print("   SSH in and run manual volume comparison")

    finally:
        # Stop the instance
        print()
        print("🛑 Stopping instance to avoid charges...")
        try:
            ec2.stop_instances(InstanceIds=[instance_id])
            print("   ✅ Instance stop initiated")
        except Exception as e:
            print(f"   ❌ Error stopping instance: {str(e)}")


if __name__ == "__main__":
    detect_duplicates()
