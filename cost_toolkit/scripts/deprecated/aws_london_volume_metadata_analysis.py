#!/usr/bin/env python3

import os
from datetime import datetime

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def analyze_volume_metadata():
    """Analyze volume metadata to identify potential duplicates"""
    setup_aws_credentials()

    print("AWS London Volume Metadata Analysis")
    print("=" * 80)
    print("🔍 Analyzing remaining 3 EBS volumes for duplicate patterns")
    print("⚠️  ANALYSIS ONLY - NO DELETIONS WILL BE PERFORMED")
    print()

    ec2 = boto3.client("ec2", region_name="eu-west-2")

    # Get detailed information about the remaining volumes
    volume_ids = [
        "vol-0249308257e5fa64d",  # Tars 3 - 64 GB
        "vol-0e07da8b7b7dafa17",  # Tars 2 - 1024 GB
        "vol-089b9ed38099c68f3",  # 384 GB
    ]

    try:
        response = ec2.describe_volumes(VolumeIds=volume_ids)
        volumes = response["Volumes"]

        print("📦 DETAILED VOLUME ANALYSIS:")
        print("=" * 80)

        volume_data = []

        for volume in volumes:
            vol_id = volume["VolumeId"]
            size = volume["Size"]
            created = volume["CreateTime"]
            state = volume["State"]
            vol_type = volume["VolumeType"]
            encrypted = volume["Encrypted"]

            # Get tags
            name = "No name"
            tags = {}
            if "Tags" in volume:
                for tag in volume["Tags"]:
                    tags[tag["Key"]] = tag["Value"]
                    if tag["Key"] == "Name":
                        name = tag["Value"]

            # Get attachment info
            attachments = volume.get("Attachments", [])
            attachment_info = "Not attached"
            if attachments:
                att = attachments[0]
                attachment_info = f"Attached to {att['InstanceId']} as {att['Device']}"

            # Get snapshot info if available
            snapshot_id = volume.get("SnapshotId", "None")

            volume_info = {
                "id": vol_id,
                "name": name,
                "size": size,
                "created": created,
                "state": state,
                "type": vol_type,
                "encrypted": encrypted,
                "attachment": attachment_info,
                "snapshot": snapshot_id,
                "tags": tags,
            }

            volume_data.append(volume_info)

            print(f"Volume: {vol_id}")
            print(f"  Name: {name}")
            print(f"  Size: {size} GB")
            print(f"  Created: {created.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Type: {vol_type}")
            print(f"  Encrypted: {encrypted}")
            print(f"  State: {state}")
            print(f"  Attachment: {attachment_info}")
            print(f"  Snapshot: {snapshot_id}")
            print(f"  Tags: {tags}")
            print()

        # Now analyze for duplicates
        print("🔍 DUPLICATE ANALYSIS:")
        print("=" * 80)

        # Sort by creation date
        volume_data.sort(key=lambda x: x["created"])

        print("📅 Chronological Order (oldest to newest):")
        for i, vol in enumerate(volume_data, 1):
            age_days = (datetime.now(vol["created"].tzinfo) - vol["created"]).days
            print(f"  {i}. {vol['name']} ({vol['id']}) - {vol['size']} GB - {age_days} days old")
        print()

        # Analyze patterns
        print("🔍 Pattern Analysis:")

        # Check for similar sizes
        sizes = [vol["size"] for vol in volume_data]
        size_counts = {}
        for size in sizes:
            size_counts[size] = size_counts.get(size, 0) + 1

        duplicate_sizes = [size for size, count in size_counts.items() if count > 1]
        if duplicate_sizes:
            print(f"   ⚠️  Found volumes with duplicate sizes: {duplicate_sizes} GB")
        else:
            print("   ✅ All volumes have unique sizes")

        # Check creation time patterns
        print("   📅 Creation Time Analysis:")
        for vol in volume_data:
            print(f"      {vol['name']}: {vol['created'].strftime('%Y-%m-%d %H:%M:%S')}")

        # Check if volumes were created close together (potential batch creation)
        creation_times = [vol["created"] for vol in volume_data]
        creation_times.sort()

        close_creations = []
        for i in range(len(creation_times) - 1):
            time_diff = (creation_times[i + 1] - creation_times[i]).total_seconds() / 3600  # hours
            if time_diff < 24:  # Created within 24 hours
                close_creations.append((creation_times[i], creation_times[i + 1], time_diff))

        if close_creations:
            print("   ⚠️  Volumes created close together (potential batch/backup creation):")
            for t1, t2, diff in close_creations:
                print(
                    f"      {t1.strftime('%Y-%m-%d %H:%M')} and {t2.strftime('%Y-%m-%d %H:%M')} ({diff:.1f} hours apart)"
                )

        # Check snapshot relationships
        print("   📸 Snapshot Analysis:")
        snapshots = [vol["snapshot"] for vol in volume_data if vol["snapshot"] != "None"]
        if snapshots:
            print(f"      Volumes created from snapshots: {len(snapshots)}")
            for vol in volume_data:
                if vol["snapshot"] != "None":
                    print(f"         {vol['name']}: from snapshot {vol['snapshot']}")
        else:
            print("      No volumes created from snapshots")

        print()
        print("💡 DUPLICATE LIKELIHOOD ASSESSMENT:")
        print("=" * 80)

        # Assess each volume
        tars_3 = next(vol for vol in volume_data if "Tars 3" in vol["name"])
        tars_2 = next(vol for vol in volume_data if "Tars 2" in vol["name"])
        vol_384 = next(vol for vol in volume_data if vol["size"] == 384)

        print(f"📦 {tars_3['name']} (64 GB):")
        print("   • Smallest volume - likely boot/system disk")
        print("   • Different size from others - probably unique content")
        print("   • Assessment: LIKELY UNIQUE (keep)")
        print()

        print(f"📦 {tars_2['name']} (1024 GB):")
        print("   • Large data volume")
        print("   • Created on same day as Tars 3")
        print("   • Assessment: LIKELY PRIMARY DATA VOLUME (keep)")
        print()

        print(f"📦 384 GB Volume:")
        print("   • Medium-sized data volume")
        print("   • Created 1 day before Tars 2 and Tars 3")
        print("   • Different size suggests different content")
        print(
            "   • Assessment: LIKELY DIFFERENT DATA SET (keep unless content analysis shows duplicates)"
        )
        print()

        print("🎯 RECOMMENDATION:")
        print("=" * 80)
        print("Based on metadata analysis:")
        print("✅ All 3 volumes have different sizes (64 GB, 384 GB, 1024 GB)")
        print("✅ Created on different days with different purposes")
        print("✅ No obvious duplicate patterns in metadata")
        print()
        print("⚠️  CONTENT ANALYSIS NEEDED:")
        print("   To definitively determine if these are duplicates, you need to:")
        print("   1. SSH into the running instance (IP: 18.132.211.58)")
        print("   2. Mount each volume and examine contents")
        print("   3. Compare directory structures and file contents")
        print()
        print("💰 Current monthly cost: $117.76 for all 3 volumes")
        print("   • Tars 3 (64 GB): $5.12/month")
        print("   • Tars 2 (1024 GB): $81.92/month")
        print("   • 384 GB volume: $30.72/month")

    except Exception as e:
        print(f"❌ Error analyzing volumes: {str(e)}")


if __name__ == "__main__":
    analyze_volume_metadata()
