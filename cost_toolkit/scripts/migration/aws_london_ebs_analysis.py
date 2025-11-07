#!/usr/bin/env python3

import os
import time
from datetime import datetime

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def analyze_london_ebs():
    """Analyze London EBS volumes and start instance for inspection"""
    setup_aws_credentials()

    print("AWS London EBS Analysis")
    print("=" * 80)

    ec2 = boto3.client("ec2", region_name="eu-west-2")

    # Instance and volume details from audit
    instance_id = "i-05ad29f28fc8a8fdc"
    attached_volumes = [
        {"id": "vol-0e148f66bcb4f7a0b", "size": "1024 GB", "type": "gp3"},
        {"id": "vol-089b9ed38099c68f3", "size": "384 GB", "type": "gp3"},
        {"id": "vol-0e07da8b7b7dafa17", "size": "1024 GB", "type": "gp3"},
        {"id": "vol-0249308257e5fa64d", "size": "64 GB", "type": "gp3"},
    ]
    unattached_volume = {"id": "vol-08f9abc839d13db62", "size": "32 GB", "type": "gp3"}

    print(f"📋 London EBS Summary:")
    print(f"Instance: {instance_id}")
    print(f"Attached volumes: {len(attached_volumes)}")
    print(f"Unattached volumes: 1 ({unattached_volume['id']})")
    print()

    # Check current instance state
    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]
        current_state = instance["State"]["Name"]
        instance_type = instance["InstanceType"]

        print(f"🖥️  Instance Details:")
        print(f"  Instance ID: {instance_id}")
        print(f"  Instance Type: {instance_type}")
        print(f"  Current State: {current_state}")
        print()

        # Get detailed volume information
        print("📦 Attached Volume Details:")
        for i, vol in enumerate(attached_volumes, 1):
            try:
                vol_response = ec2.describe_volumes(VolumeIds=[vol["id"]])
                volume = vol_response["Volumes"][0]

                # Get attachment info
                attachments = volume.get("Attachments", [])
                device = attachments[0]["Device"] if attachments else "Unknown"

                # Get creation time
                create_time = volume["CreateTime"]

                # Get tags
                tags = {tag["Key"]: tag["Value"] for tag in volume.get("Tags", [])}
                name_tag = tags.get("Name", "No name")

                print(f"  Volume {i}: {vol['id']}")
                print(f"    Size: {vol['size']}")
                print(f"    Device: {device}")
                print(f"    Created: {create_time}")
                print(f"    Name: {name_tag}")
                print(f"    Tags: {tags}")
                print()

            except Exception as e:
                print(f"    Error getting details for {vol['id']}: {e}")

        # Check unattached volume
        print("🔍 Unattached Volume Details:")
        try:
            vol_response = ec2.describe_volumes(VolumeIds=[unattached_volume["id"]])
            volume = vol_response["Volumes"][0]

            create_time = volume["CreateTime"]
            tags = {tag["Key"]: tag["Value"] for tag in volume.get("Tags", [])}
            name_tag = tags.get("Name", "No name")

            print(f"  Volume: {unattached_volume['id']}")
            print(f"    Size: {unattached_volume['size']}")
            print(f"    Created: {create_time}")
            print(f"    Name: {name_tag}")
            print(f"    Tags: {tags}")
            print()

        except Exception as e:
            print(f"    Error getting details for {unattached_volume['id']}: {e}")

        # Start instance if stopped
        if current_state == "stopped":
            print("🚀 Starting instance for analysis...")
            try:
                ec2.start_instances(InstanceIds=[instance_id])
                print("  Instance start initiated. Waiting for running state...")

                # Wait for instance to be running
                waiter = ec2.get_waiter("instance_running")
                waiter.wait(
                    InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 20}
                )

                print("  ✅ Instance is now running!")

                # Get updated instance info
                response = ec2.describe_instances(InstanceIds=[instance_id])
                instance = response["Reservations"][0]["Instances"][0]
                public_ip = instance.get("PublicIpAddress", "No public IP")
                private_ip = instance.get("PrivateIpAddress", "No private IP")

                print(f"  Public IP: {public_ip}")
                print(f"  Private IP: {private_ip}")
                print()

            except Exception as e:
                print(f"  ❌ Error starting instance: {e}")

        elif current_state == "running":
            print("✅ Instance is already running!")
            public_ip = instance.get("PublicIpAddress", "No public IP")
            private_ip = instance.get("PrivateIpAddress", "No private IP")
            print(f"  Public IP: {public_ip}")
            print(f"  Private IP: {private_ip}")
            print()
        else:
            print(f"⚠️  Instance is in '{current_state}' state")
            print()

        # Analyze snapshots related to this instance
        print("📸 Related Snapshots Analysis:")
        try:
            snapshots_response = ec2.describe_snapshots(OwnerIds=["self"])
            snapshots = snapshots_response.get("Snapshots", [])

            # Filter snapshots that mention this instance
            related_snapshots = []
            for snap in snapshots:
                description = snap.get("Description", "")
                if instance_id in description or any(
                    vol["id"] in description for vol in attached_volumes
                ):
                    related_snapshots.append(snap)

            if related_snapshots:
                print(f"  Found {len(related_snapshots)} snapshots related to this instance:")
                for snap in related_snapshots:
                    snap_id = snap["SnapshotId"]
                    size = snap.get("VolumeSize", 0)
                    start_time = snap["StartTime"]
                    description = snap.get("Description", "No description")

                    print(f"    {snap_id}: {size} GB, created {start_time}")
                    print(f"      Description: {description}")
                print()
            else:
                print("  No snapshots directly related to this instance found.")
                print()

        except Exception as e:
            print(f"  Error analyzing snapshots: {e}")

        # Recommendations
        print("💡 ANALYSIS & RECOMMENDATIONS:")
        print("=" * 80)

        # Check for duplicate-sized volumes
        sizes = [vol["size"] for vol in attached_volumes]
        duplicate_sizes = [size for size in set(sizes) if sizes.count(size) > 1]

        if duplicate_sizes:
            print(f"⚠️  Found volumes with duplicate sizes: {duplicate_sizes}")
            print("   These may be duplicates - manual inspection needed after instance starts")

        print(f"🗑️  Unattached volume {unattached_volume['id']} (32 GB) can likely be deleted")
        print("   This volume is not attached to any instance and costs $2.56/month")
        print()

        print("📋 NEXT STEPS:")
        print("1. SSH into the running instance to examine volume contents")
        print("2. Check mount points: df -h")
        print("3. Examine each volume's contents to identify duplicates")
        print("4. Identify the most recent/important data")
        print("5. Plan cleanup of duplicate volumes")
        print()

        if current_state == "stopped":
            print("⚠️  IMPORTANT: Instance was started for analysis.")
            print("   Remember to stop it after analysis to avoid ongoing compute charges!")

    except Exception as e:
        print(f"❌ Error analyzing instance: {e}")


if __name__ == "__main__":
    analyze_london_ebs()
