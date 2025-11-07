#!/usr/bin/env python3

import base64
import os
import time

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def create_analysis_script():
    """Create the analysis script that will run on the instance"""
    script = """#!/bin/bash
exec > /tmp/volume_analysis.log 2>&1

echo "=== AWS EBS Volume Content Analysis ==="
echo "Started at: $(date)"
echo

# Wait for volumes to be available
sleep 10

echo "=== Current Disk Layout ==="
lsblk
echo
df -h
echo

echo "=== Creating Mount Points ==="
mkdir -p /mnt/tars2 /mnt/vol384

# Unmount if already mounted
umount /mnt/tars2 2>/dev/null || true
umount /mnt/vol384 2>/dev/null || true

echo "=== Mounting Volumes Read-Only ==="
# Mount the data volumes (not the boot volume)
mount -o ro /dev/sde /mnt/tars2 && echo "Tars2 mounted successfully" || echo "Failed to mount Tars2"
mount -o ro /dev/sdd /mnt/vol384 && echo "Vol384 mounted successfully" || echo "Failed to mount Vol384"

echo
mount | grep /mnt
echo

echo "=== Directory Structure Comparison ==="
echo "--- Tars2 Root Directory ---"
ls -la /mnt/tars2/ 2>/dev/null | head -20 || echo "Cannot list Tars2 directory"
echo
echo "--- Vol384 Root Directory ---"
ls -la /mnt/vol384/ 2>/dev/null | head -20 || echo "Cannot list Vol384 directory"
echo

echo "=== File and Directory Counts ==="
echo "Tars2 directories: $(find /mnt/tars2 -type d 2>/dev/null | wc -l)"
echo "Tars2 files: $(find /mnt/tars2 -type f 2>/dev/null | wc -l)"
echo "Vol384 directories: $(find /mnt/vol384 -type d 2>/dev/null | wc -l)"
echo "Vol384 files: $(find /mnt/vol384 -type f 2>/dev/null | wc -l)"
echo

echo "=== Disk Usage Comparison ==="
echo "Tars2 total size:"
du -sh /mnt/tars2 2>/dev/null || echo "Cannot calculate Tars2 size"
echo "Vol384 total size:"
du -sh /mnt/vol384 2>/dev/null || echo "Cannot calculate Vol384 size"
echo

echo "=== Top Level Directory Sizes ==="
echo "--- Tars2 subdirectories ---"
du -sh /mnt/tars2/* 2>/dev/null | head -10 || echo "No Tars2 subdirectories"
echo
echo "--- Vol384 subdirectories ---"
du -sh /mnt/vol384/* 2>/dev/null | head -10 || echo "No Vol384 subdirectories"
echo

echo "=== Directory Structure Analysis ==="
find /mnt/tars2 -maxdepth 2 -type d 2>/dev/null | sort > /tmp/tars2_dirs.txt
find /mnt/vol384 -maxdepth 2 -type d 2>/dev/null | sort > /tmp/vol384_dirs.txt

echo "Tars2 directory structure (top 10):"
head -10 /tmp/tars2_dirs.txt 2>/dev/null || echo "No Tars2 directories"
echo
echo "Vol384 directory structure (top 10):"
head -10 /tmp/vol384_dirs.txt 2>/dev/null || echo "No Vol384 directories"
echo

echo "Common directories between volumes:"
comm -12 /tmp/tars2_dirs.txt /tmp/vol384_dirs.txt 2>/dev/null | head -10 || echo "No common directories found"
echo

echo "=== File Modification Time Analysis ==="
echo "Newest file in Tars2:"
find /mnt/tars2 -type f -printf "%T@ %TY-%Tm-%Td %TH:%TM %p\\n" 2>/dev/null | sort -n | tail -1 || echo "No files in Tars2"
echo "Newest file in Vol384:"
find /mnt/vol384 -type f -printf "%T@ %TY-%Tm-%Td %TH:%TM %p\\n" 2>/dev/null | sort -n | tail -1 || echo "No files in Vol384"
echo

echo "=== Sample File Checksum Comparison ==="
echo "Sample checksums from Tars2 (first 5 files > 1KB):"
find /mnt/tars2 -type f -size +1k 2>/dev/null | head -5 | while read file; do
    md5sum "$file" 2>/dev/null || echo "Cannot checksum $file"
done
echo
echo "Sample checksums from Vol384 (first 5 files > 1KB):"
find /mnt/vol384 -type f -size +1k 2>/dev/null | head -5 | while read file; do
    md5sum "$file" 2>/dev/null || echo "Cannot checksum $file"
done
echo

echo "=== Content Overlap Analysis ==="
# Check if Vol384 content exists in Tars2
echo "Checking if Vol384 files exist in Tars2..."
vol384_files=$(find /mnt/vol384 -type f 2>/dev/null | head -10)
if [ -n "$vol384_files" ]; then
    echo "$vol384_files" | while read file; do
        relative_path=${file#/mnt/vol384}
        if [ -f "/mnt/tars2$relative_path" ]; then
            echo "MATCH: $relative_path exists in both volumes"
        else
            echo "UNIQUE: $relative_path only in Vol384"
        fi
    done
else
    echo "No files found in Vol384 to compare"
fi
echo

echo "=== Final Assessment ==="
tars2_files=$(find /mnt/tars2 -type f 2>/dev/null | wc -l)
vol384_files=$(find /mnt/vol384 -type f 2>/dev/null | wc -l)

echo "File count comparison:"
echo "  Tars2: $tars2_files files"
echo "  Vol384: $vol384_files files"

if [ "$vol384_files" -eq 0 ]; then
    echo "CONCLUSION: Vol384 appears to be EMPTY - Safe to remove"
elif [ "$vol384_files" -lt "$((tars2_files / 2))" ]; then
    echo "CONCLUSION: Vol384 has significantly fewer files - Likely SUBSET/OLD VERSION"
else
    echo "CONCLUSION: Vol384 has substantial content - MANUAL REVIEW needed"
fi

echo
echo "=== Cleanup ==="
umount /mnt/tars2 2>/dev/null || true
umount /mnt/vol384 2>/dev/null || true
rmdir /mnt/tars2 /mnt/vol384 2>/dev/null || true

echo "Analysis completed at: $(date)"
echo "Results saved to: /tmp/volume_analysis.log"
"""
    return script


def run_analysis():
    """Run the automated file analysis"""
    setup_aws_credentials()

    print("AWS London EBS Direct File Content Analysis")
    print("=" * 80)
    print("🔍 Running automated file content analysis on instance")
    print("⚠️  ANALYSIS ONLY - NO DELETIONS WILL BE PERFORMED")
    print()

    ec2 = boto3.client("ec2", region_name="eu-west-2")
    instance_id = "i-05ad29f28fc8a8fdc"

    try:
        # Check if instance is running
        print("🚀 Checking instance status...")
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]
        state = instance["State"]["Name"]

        if state != "running":
            print("   Instance not running. Starting...")
            ec2.start_instances(InstanceIds=[instance_id])
            waiter = ec2.get_waiter("instance_running")
            waiter.wait(InstanceIds=[instance_id])
            print("   ✅ Instance started")
        else:
            print("   ✅ Instance already running")

        # Get instance IP
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]
        public_ip = instance.get("PublicIpAddress", "No public IP")

        print(f"   Instance IP: {public_ip}")
        print()

        # Create and encode the analysis script
        analysis_script = create_analysis_script()
        user_data = base64.b64encode(analysis_script.encode()).decode()

        print("📋 MANUAL EXECUTION REQUIRED:")
        print("=" * 80)
        print("Since automated execution via SSM is not available, please:")
        print()
        print("1. SSH into the instance:")
        print(f"   ssh -i your-key.pem ec2-user@{public_ip}")
        print()
        print("2. Run this analysis script:")
        print()
        print("```bash")
        print("# Create the analysis script")
        print("cat > /tmp/analyze_volumes.sh << 'EOF'")
        print(analysis_script)
        print("EOF")
        print()
        print("# Make it executable and run")
        print("chmod +x /tmp/analyze_volumes.sh")
        print("sudo /tmp/analyze_volumes.sh")
        print()
        print("# View the results")
        print("cat /tmp/volume_analysis.log")
        print("```")
        print()
        print("3. The script will:")
        print("   ✅ Mount both volumes read-only")
        print("   ✅ Compare directory structures")
        print("   ✅ Count files and directories")
        print("   ✅ Compare disk usage")
        print("   ✅ Check file modification times")
        print("   ✅ Generate checksums for sample files")
        print("   ✅ Look for content overlap")
        print("   ✅ Provide a conclusion")
        print()
        print("4. Based on the output, you'll know if Vol384 is:")
        print("   • Empty → Safe to remove")
        print("   • Subset of Tars2 → Likely safe to remove")
        print("   • Different content → Keep both")
        print()

        print("⚠️  REMEMBER: Stop the instance when analysis is complete!")
        print(f"   aws ec2 stop-instances --instance-ids {instance_id}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    run_analysis()
