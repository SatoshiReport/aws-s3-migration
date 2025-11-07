#!/usr/bin/env python3

import base64
import json
import os
import time

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def create_s3_analysis_script():
    """Create analysis script that uploads results to S3"""
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
tars2_dirs=$(find /mnt/tars2 -type d 2>/dev/null | wc -l)
tars2_files=$(find /mnt/tars2 -type f 2>/dev/null | wc -l)
vol384_dirs=$(find /mnt/vol384 -type d 2>/dev/null | wc -l)
vol384_files=$(find /mnt/vol384 -type f 2>/dev/null | wc -l)

echo "Tars2 directories: $tars2_dirs"
echo "Tars2 files: $tars2_files"
echo "Vol384 directories: $vol384_dirs"
echo "Vol384 files: $vol384_files"
echo

echo "=== Disk Usage Comparison ==="
echo "Tars2 total size:"
tars2_size=$(du -sh /mnt/tars2 2>/dev/null | cut -f1 || echo "Unknown")
echo "$tars2_size"
echo "Vol384 total size:"
vol384_size=$(du -sh /mnt/vol384 2>/dev/null | cut -f1 || echo "Unknown")
echo "$vol384_size"
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
common_dirs=$(comm -12 /tmp/tars2_dirs.txt /tmp/vol384_dirs.txt 2>/dev/null | wc -l)
echo "Found $common_dirs common directories"
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
vol384_sample_files=$(find /mnt/vol384 -type f 2>/dev/null | head -10)
matches=0
total_checked=0

if [ -n "$vol384_sample_files" ]; then
    echo "$vol384_sample_files" | while read file; do
        relative_path=${file#/mnt/vol384}
        if [ -f "/mnt/tars2$relative_path" ]; then
            echo "MATCH: $relative_path exists in both volumes"
            matches=$((matches + 1))
        else
            echo "UNIQUE: $relative_path only in Vol384"
        fi
        total_checked=$((total_checked + 1))
    done
else
    echo "No files found in Vol384 to compare"
fi
echo

echo "=== FINAL ASSESSMENT ==="
echo "=========================================="
echo "File count comparison:"
echo "  Tars2: $tars2_files files in $tars2_dirs directories ($tars2_size)"
echo "  Vol384: $vol384_files files in $vol384_dirs directories ($vol384_size)"
echo

# Determine conclusion based on analysis
if [ "$vol384_files" -eq 0 ]; then
    conclusion="EMPTY - Safe to remove"
    confidence="HIGH"
    recommendation="REMOVE Vol384 (saves $30.72/month)"
elif [ "$vol384_files" -lt 100 ] && [ "$tars2_files" -gt 1000 ]; then
    conclusion="MOSTLY EMPTY - Likely safe to remove"
    confidence="HIGH"
    recommendation="REMOVE Vol384 (saves $30.72/month)"
elif [ "$vol384_files" -lt "$((tars2_files / 3))" ]; then
    conclusion="SUBSET/OLD VERSION - Likely safe to remove"
    confidence="MEDIUM-HIGH"
    recommendation="REMOVE Vol384 after final verification (saves $30.72/month)"
elif [ "$common_dirs" -gt "$((vol384_dirs / 2))" ] && [ "$vol384_files" -lt "$tars2_files" ]; then
    conclusion="DUPLICATE/OLDER VERSION - Likely safe to remove"
    confidence="MEDIUM"
    recommendation="REMOVE Vol384 after manual spot check (saves $30.72/month)"
else
    conclusion="SUBSTANTIAL DIFFERENT CONTENT - Keep both"
    confidence="MEDIUM"
    recommendation="KEEP both volumes - different datasets"
fi

echo "CONCLUSION: Vol384 appears to be $conclusion"
echo "CONFIDENCE: $confidence"
echo "RECOMMENDATION: $recommendation"
echo

echo "=== Cleanup ==="
umount /mnt/tars2 2>/dev/null || true
umount /mnt/vol384 2>/dev/null || true
rmdir /mnt/tars2 /mnt/vol384 2>/dev/null || true

echo "Analysis completed at: $(date)"
echo "Results saved to: /tmp/volume_analysis.log"

# Upload results to S3
echo "Uploading results to S3..."
aws s3 cp /tmp/volume_analysis.log s3://aws-cost-analysis-results/volume-analysis-$(date +%Y%m%d-%H%M%S).log --region eu-west-2 || echo "Failed to upload to S3"
echo "Upload completed"
"""
    return script


def run_s3_analysis():
    """Run analysis using User Data and S3 for results"""
    setup_aws_credentials()

    print("AWS London EBS S3-Based Volume Analysis")
    print("=" * 80)
    print("🔍 Running automated analysis with S3 results upload")
    print("⚠️  ANALYSIS ONLY - NO DELETIONS WILL BE PERFORMED")
    print()

    ec2 = boto3.client("ec2", region_name="eu-west-2")
    s3 = boto3.client("s3", region_name="eu-west-2")
    instance_id = "i-05ad29f28fc8a8fdc"
    bucket_name = "aws-cost-analysis-results"

    try:
        # Create S3 bucket if it doesn't exist
        print("📦 Setting up S3 bucket for results...")
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"   ✅ Bucket {bucket_name} already exists")
        except:
            try:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
                )
                print(f"   ✅ Created bucket {bucket_name}")
            except Exception as e:
                print(f"   ⚠️  Could not create bucket: {e}")
                print("   Using default bucket approach...")

        # Stop instance first to modify user data
        print("🛑 Stopping instance to modify user data...")
        try:
            ec2.stop_instances(InstanceIds=[instance_id])
            waiter = ec2.get_waiter("instance_stopped")
            waiter.wait(InstanceIds=[instance_id])
            print("   ✅ Instance stopped")
        except Exception as e:
            print(f"   ⚠️  Instance stop issue: {e}")

        # Create and set user data
        print("📝 Setting up analysis script as user data...")
        analysis_script = create_s3_analysis_script()
        user_data = base64.b64encode(analysis_script.encode()).decode()

        try:
            ec2.modify_instance_attribute(InstanceId=instance_id, UserData={"Value": user_data})
            print("   ✅ User data script configured")
        except Exception as e:
            print(f"   ❌ Failed to set user data: {e}")
            return

        # Start instance to run analysis
        print("🚀 Starting instance to run analysis...")
        ec2.start_instances(InstanceIds=[instance_id])
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id])
        print("   ✅ Instance started - analysis script is running")

        # Wait for analysis to complete
        print("⏳ Waiting for analysis to complete (this may take 2-3 minutes)...")
        time.sleep(180)  # Wait 3 minutes for analysis

        # Check for results in S3
        print("📊 Checking for analysis results in S3...")
        try:
            response = s3.list_objects_v2(Bucket=bucket_name, Prefix="volume-analysis-")

            if "Contents" in response and len(response["Contents"]) > 0:
                # Get the most recent result
                latest_object = sorted(response["Contents"], key=lambda x: x["LastModified"])[-1]
                object_key = latest_object["Key"]

                print(f"   ✅ Found analysis results: {object_key}")

                # Download and display results
                print("\n📋 ANALYSIS RESULTS:")
                print("=" * 80)

                response = s3.get_object(Bucket=bucket_name, Key=object_key)
                results = response["Body"].read().decode("utf-8")
                print(results)

                # Save results locally
                with open("volume_analysis_results.log", "w") as f:
                    f.write(results)
                print(f"\n💾 Results saved to: volume_analysis_results.log")

            else:
                print("   ⚠️  No results found yet. Analysis may still be running.")
                print("   Check S3 bucket manually or wait longer.")

        except Exception as e:
            print(f"   ❌ Error checking S3 results: {e}")

        # Stop instance to save costs
        print("\n🛑 Stopping instance to avoid charges...")
        try:
            ec2.stop_instances(InstanceIds=[instance_id])
            print("   ✅ Instance stop initiated")
        except Exception as e:
            print(f"   ⚠️  Could not stop instance: {e}")

        print(f"\n🔍 You can also check S3 bucket manually:")
        print(f"   aws s3 ls s3://{bucket_name}/")
        print(f"   aws s3 cp s3://{bucket_name}/volume-analysis-YYYYMMDD-HHMMSS.log ./")

    except Exception as e:
        print(f"❌ Error during S3 analysis: {str(e)}")
        print("\n🛑 Attempting to stop instance...")
        try:
            ec2.stop_instances(InstanceIds=[instance_id])
            print("   ✅ Instance stop initiated")
        except:
            print("   ⚠️  Could not stop instance - check AWS console")


if __name__ == "__main__":
    run_s3_analysis()
