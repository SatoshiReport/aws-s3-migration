#!/usr/bin/env python3

import json
import os
import time

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def run_ssm_command(ssm_client, instance_id, commands, description):
    """Run a command via SSM and return the output"""
    try:
        response = ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": commands},
            Comment=description,
        )

        command_id = response["Command"]["CommandId"]

        # Wait for command to complete
        time.sleep(5)

        # Get command output
        output_response = ssm_client.get_command_invocation(
            CommandId=command_id, InstanceId=instance_id
        )

        return output_response.get("StandardOutputContent", ""), output_response.get(
            "StandardErrorContent", ""
        )

    except Exception as e:
        return "", str(e)


def analyze_file_contents():
    """Automated file content analysis using SSM"""
    setup_aws_credentials()

    print("AWS London EBS Automated File Content Analysis")
    print("=" * 80)
    print("🔍 Performing automated file content comparison")
    print("⚠️  ANALYSIS ONLY - NO DELETIONS WILL BE PERFORMED")
    print()

    ec2 = boto3.client("ec2", region_name="eu-west-2")
    ssm = boto3.client("ssm", region_name="eu-west-2")
    instance_id = "i-05ad29f28fc8a8fdc"

    try:
        # Ensure instance is running
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
            time.sleep(30)  # Wait for full initialization
        else:
            print("   ✅ Instance already running")

        print("\n📦 Step 1: Checking current disk layout...")
        stdout, stderr = run_ssm_command(ssm, instance_id, ["lsblk", "df -h"], "Check disk layout")
        if stdout:
            print("Current disk layout:")
            print(stdout)
        if stderr:
            print(f"Errors: {stderr}")

        print("\n📁 Step 2: Creating mount points and mounting volumes...")
        mount_commands = [
            "sudo mkdir -p /mnt/tars2 /mnt/vol384",
            "sudo umount /mnt/tars2 2>/dev/null || true",
            "sudo umount /mnt/vol384 2>/dev/null || true",
            "sudo mount -o ro /dev/sde /mnt/tars2",
            "sudo mount -o ro /dev/sdd /mnt/vol384",
            "mount | grep /mnt",
        ]

        stdout, stderr = run_ssm_command(ssm, instance_id, mount_commands, "Mount volumes")
        if stdout:
            print("Mount results:")
            print(stdout)
        if stderr and "already mounted" not in stderr:
            print(f"Mount errors: {stderr}")

        print("\n🔍 Step 3: Comparing directory structures...")
        dir_commands = [
            'echo "=== Tars2 root directory ==="',
            "sudo ls -la /mnt/tars2/ | head -20",
            'echo "=== Vol384 root directory ==="',
            "sudo ls -la /mnt/vol384/ | head -20",
            'echo "=== Directory counts ==="',
            'echo "Tars2 directories: $(sudo find /mnt/tars2 -type d 2>/dev/null | wc -l)"',
            'echo "Vol384 directories: $(sudo find /mnt/vol384 -type d 2>/dev/null | wc -l)"',
        ]

        stdout, stderr = run_ssm_command(ssm, instance_id, dir_commands, "Compare directories")
        if stdout:
            print("Directory comparison:")
            print(stdout)

        print("\n📊 Step 4: Comparing file counts and sizes...")
        size_commands = [
            'echo "=== File counts ==="',
            'echo "Tars2 files: $(sudo find /mnt/tars2 -type f 2>/dev/null | wc -l)"',
            'echo "Vol384 files: $(sudo find /mnt/vol384 -type f 2>/dev/null | wc -l)"',
            'echo "=== Disk usage ==="',
            'sudo du -sh /mnt/tars2 2>/dev/null || echo "Tars2: Could not calculate"',
            'sudo du -sh /mnt/vol384 2>/dev/null || echo "Vol384: Could not calculate"',
            'echo "=== Top level directory sizes ==="',
            'sudo du -sh /mnt/tars2/* 2>/dev/null | head -10 || echo "Tars2: No subdirectories"',
            'echo "---"',
            'sudo du -sh /mnt/vol384/* 2>/dev/null | head -10 || echo "Vol384: No subdirectories"',
        ]

        stdout, stderr = run_ssm_command(ssm, instance_id, size_commands, "Compare sizes")
        if stdout:
            print("Size comparison:")
            print(stdout)

        print("\n🔎 Step 5: Looking for common directory structures...")
        structure_commands = [
            'echo "=== Common directories check ==="',
            "sudo find /mnt/tars2 -maxdepth 2 -type d 2>/dev/null | sort > /tmp/tars2_dirs.txt",
            "sudo find /mnt/vol384 -maxdepth 2 -type d 2>/dev/null | sort > /tmp/vol384_dirs.txt",
            'echo "Tars2 top directories:"',
            "head -10 /tmp/tars2_dirs.txt",
            'echo "Vol384 top directories:"',
            "head -10 /tmp/vol384_dirs.txt",
            'echo "=== Directory structure comparison ==="',
            "comm -12 /tmp/tars2_dirs.txt /tmp/vol384_dirs.txt | head -10",
        ]

        stdout, stderr = run_ssm_command(ssm, instance_id, structure_commands, "Compare structures")
        if stdout:
            print("Structure comparison:")
            print(stdout)

        print("\n🕐 Step 6: Checking file modification times...")
        time_commands = [
            'echo "=== Recent files in Tars2 ==="',
            'sudo find /mnt/tars2 -type f -newermt "2025-01-01" 2>/dev/null | head -5',
            'echo "=== Recent files in Vol384 ==="',
            'sudo find /mnt/vol384 -type f -newermt "2025-01-01" 2>/dev/null | head -5',
            'echo "=== File age comparison ==="',
            'echo "Tars2 newest file:"',
            'sudo find /mnt/tars2 -type f -printf "%T@ %p\\n" 2>/dev/null | sort -n | tail -1',
            'echo "Vol384 newest file:"',
            'sudo find /mnt/vol384 -type f -printf "%T@ %p\\n" 2>/dev/null | sort -n | tail -1',
        ]

        stdout, stderr = run_ssm_command(ssm, instance_id, time_commands, "Check file times")
        if stdout:
            print("File time comparison:")
            print(stdout)

        print("\n🧮 Step 7: Sample file checksum comparison...")
        checksum_commands = [
            'echo "=== Sample checksums from Tars2 ==="',
            'sudo find /mnt/tars2 -type f -size +1k 2>/dev/null | head -5 | xargs -I {} sudo md5sum "{}" 2>/dev/null || echo "No files to checksum in Tars2"',
            'echo "=== Sample checksums from Vol384 ==="',
            'sudo find /mnt/vol384 -type f -size +1k 2>/dev/null | head -5 | xargs -I {} sudo md5sum "{}" 2>/dev/null || echo "No files to checksum in Vol384"',
        ]

        stdout, stderr = run_ssm_command(ssm, instance_id, checksum_commands, "Compare checksums")
        if stdout:
            print("Checksum comparison:")
            print(stdout)

        print("\n🧹 Step 8: Cleaning up...")
        cleanup_commands = [
            "sudo umount /mnt/tars2 2>/dev/null || true",
            "sudo umount /mnt/vol384 2>/dev/null || true",
            "sudo rmdir /mnt/tars2 /mnt/vol384 2>/dev/null || true",
            'echo "Cleanup completed"',
        ]

        stdout, stderr = run_ssm_command(ssm, instance_id, cleanup_commands, "Cleanup")
        if stdout:
            print("Cleanup results:")
            print(stdout)

        print("\n🎯 ANALYSIS SUMMARY:")
        print("=" * 80)
        print("Based on the automated analysis above, look for these patterns:")
        print()
        print("🔍 DUPLICATE INDICATORS:")
        print("   ✅ Similar directory structures in both volumes")
        print("   ✅ Similar file counts")
        print("   ✅ Matching checksums for sample files")
        print("   ✅ Vol384 has older modification times than Tars2")
        print()
        print("🔍 DIFFERENT CONTENT INDICATORS:")
        print("   ❌ Completely different directory structures")
        print("   ❌ Very different file counts")
        print("   ❌ No matching checksums")
        print("   ❌ Vol384 has newer files than Tars2")
        print()
        print("💡 RECOMMENDATION:")
        print("   Review the output above to determine if Vol384 appears to be:")
        print("   • A duplicate/subset of Tars2 → Safe to remove")
        print("   • Completely different content → Keep both")
        print("   • Mostly empty → Safe to remove")

        print("\n🛑 Stopping instance to avoid charges...")
        ec2.stop_instances(InstanceIds=[instance_id])
        print("   ✅ Instance stop initiated")

    except Exception as e:
        print(f"❌ Error during analysis: {str(e)}")
        print("\n🛑 Attempting to stop instance...")
        try:
            ec2.stop_instances(InstanceIds=[instance_id])
            print("   ✅ Instance stop initiated")
        except:
            print("   ⚠️  Could not stop instance - check AWS console")


if __name__ == "__main__":
    analyze_file_contents()
