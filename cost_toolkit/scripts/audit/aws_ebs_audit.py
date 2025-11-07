#!/usr/bin/env python3

import os
from collections import defaultdict
from datetime import datetime, timezone

import boto3
from dotenv import load_dotenv


def setup_aws_credentials():
    """Load AWS credentials from .env file"""
    # Load environment variables from .env file
    load_dotenv(os.path.expanduser("~/.env"))

    # Check if credentials are loaded
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        print("⚠️  AWS credentials not found in ~/.env file.")
        print("Please ensure ~/.env contains:")
        print("  AWS_ACCESS_KEY_ID=your-access-key")
        print("  AWS_SECRET_ACCESS_KEY=your-secret-key")
        print("  AWS_DEFAULT_REGION=us-east-1")
        return False

    return True


def get_all_regions():
    """Get all available AWS regions"""
    try:
        ec2 = boto3.client("ec2", region_name="us-east-1")
        response = ec2.describe_regions()
        return [region["RegionName"] for region in response["Regions"]]
    except Exception as e:
        print(f"Error getting regions: {e}")
        return [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-central-1",
        ]


def audit_ebs_volumes():
    """Audit all EBS volumes across all regions"""
    setup_aws_credentials()

    print("AWS EBS Volume & Snapshot Audit")
    print("=" * 80)
    print("Analyzing all EBS volumes and snapshots across all regions...")
    print()

    regions = get_all_regions()
    total_volumes = 0
    total_snapshots = 0
    total_volume_cost = 0
    total_snapshot_cost = 0

    volume_details = []
    snapshot_details = []

    for region in regions:
        try:
            ec2 = boto3.client("ec2", region_name=region)

            # Get volumes
            volumes_response = ec2.describe_volumes()
            volumes = volumes_response.get("Volumes", [])

            # Get snapshots (only owned by this account)
            snapshots_response = ec2.describe_snapshots(OwnerIds=["self"])
            snapshots = snapshots_response.get("Snapshots", [])

            if volumes or snapshots:
                print(f"🔍 Auditing EBS resources in {region}")
                print("=" * 80)

                # Process volumes
                if volumes:
                    print(f"📦 EBS Volumes ({len(volumes)} found):")
                    for volume in volumes:
                        volume_id = volume["VolumeId"]
                        size_gb = volume["Size"]
                        volume_type = volume["VolumeType"]
                        state = volume["State"]

                        # Get attachment info
                        attachments = volume.get("Attachments", [])
                        attached_to = "Not attached"
                        if attachments:
                            instance_id = attachments[0].get("InstanceId", "Unknown")
                            attached_to = f"Instance: {instance_id}"

                        # Estimate monthly cost (rough estimates)
                        if volume_type == "gp3":
                            monthly_cost = size_gb * 0.08  # $0.08 per GB/month
                        elif volume_type == "gp2":
                            monthly_cost = size_gb * 0.10  # $0.10 per GB/month
                        elif volume_type == "io1" or volume_type == "io2":
                            monthly_cost = size_gb * 0.125  # $0.125 per GB/month
                        else:
                            monthly_cost = size_gb * 0.10  # Default estimate

                        total_volume_cost += monthly_cost

                        print(f"  Volume ID: {volume_id}")
                        print(f"    Size: {size_gb} GB")
                        print(f"    Type: {volume_type}")
                        print(f"    State: {state}")
                        print(f"    Attached to: {attached_to}")
                        print(f"    Est. monthly cost: ${monthly_cost:.2f}")
                        print()

                        volume_details.append(
                            {
                                "region": region,
                                "volume_id": volume_id,
                                "size_gb": size_gb,
                                "volume_type": volume_type,
                                "state": state,
                                "attached_to": attached_to,
                                "monthly_cost": monthly_cost,
                            }
                        )

                # Process snapshots
                if snapshots:
                    print(f"📸 EBS Snapshots ({len(snapshots)} found):")
                    for snapshot in snapshots:
                        snapshot_id = snapshot["SnapshotId"]
                        size_gb = snapshot.get("VolumeSize", 0)
                        state = snapshot["State"]
                        start_time = snapshot["StartTime"]
                        description = snapshot.get("Description", "No description")

                        # Estimate monthly cost for snapshots
                        monthly_cost = size_gb * 0.05  # $0.05 per GB/month for snapshots
                        total_snapshot_cost += monthly_cost

                        print(f"  Snapshot ID: {snapshot_id}")
                        print(f"    Size: {size_gb} GB")
                        print(f"    State: {state}")
                        print(f"    Created: {start_time}")
                        print(f"    Description: {description}")
                        print(f"    Est. monthly cost: ${monthly_cost:.2f}")
                        print()

                        snapshot_details.append(
                            {
                                "region": region,
                                "snapshot_id": snapshot_id,
                                "size_gb": size_gb,
                                "state": state,
                                "start_time": start_time,
                                "description": description,
                                "monthly_cost": monthly_cost,
                            }
                        )

                total_volumes += len(volumes)
                total_snapshots += len(snapshots)
                print()

        except Exception as e:
            print(f"⚠️  Error auditing {region}: {e}")
            continue

    # Summary
    print("=" * 80)
    print("🎯 OVERALL EBS SUMMARY")
    print("=" * 80)
    print(f"Total EBS Volumes found: {total_volumes}")
    print(f"Total EBS Snapshots found: {total_snapshots}")
    print(f"Estimated monthly cost for volumes: ${total_volume_cost:.2f}")
    print(f"Estimated monthly cost for snapshots: ${total_snapshot_cost:.2f}")
    print(f"Total estimated monthly EBS cost: ${total_volume_cost + total_snapshot_cost:.2f}")
    print()

    # Volume breakdown by type
    if volume_details:
        print("📊 Volume Breakdown by Type:")
        volume_types = defaultdict(lambda: {"count": 0, "size": 0, "cost": 0})
        for vol in volume_details:
            volume_types[vol["volume_type"]]["count"] += 1
            volume_types[vol["volume_type"]]["size"] += vol["size_gb"]
            volume_types[vol["volume_type"]]["cost"] += vol["monthly_cost"]

        for vol_type, stats in volume_types.items():
            print(
                f"  {vol_type}: {stats['count']} volumes, {stats['size']} GB total, ${stats['cost']:.2f}/month"
            )
        print()

    # Unattached volumes (potential cleanup candidates)
    unattached_volumes = [vol for vol in volume_details if "Not attached" in vol["attached_to"]]
    if unattached_volumes:
        print("⚠️  UNATTACHED VOLUMES (Potential cleanup candidates):")
        unattached_cost = sum(vol["monthly_cost"] for vol in unattached_volumes)
        print(
            f"Found {len(unattached_volumes)} unattached volumes costing ${unattached_cost:.2f}/month"
        )
        for vol in unattached_volumes:
            print(
                f"  {vol['region']}: {vol['volume_id']} ({vol['size_gb']} GB {vol['volume_type']}) - ${vol['monthly_cost']:.2f}/month"
            )
        print()

    # Old snapshots (potential cleanup candidates)
    if snapshot_details:
        print("📅 SNAPSHOT AGE ANALYSIS:")
        now = datetime.now(timezone.utc)
        old_snapshots = []
        for snap in snapshot_details:
            age_days = (now - snap["start_time"]).days
            if age_days > 30:  # Older than 30 days
                old_snapshots.append({**snap, "age_days": age_days})

        if old_snapshots:
            old_snapshot_cost = sum(snap["monthly_cost"] for snap in old_snapshots)
            print(
                f"Found {len(old_snapshots)} snapshots older than 30 days costing ${old_snapshot_cost:.2f}/month"
            )
            # Show top 10 oldest/most expensive
            old_snapshots.sort(key=lambda x: x["monthly_cost"], reverse=True)
            for snap in old_snapshots[:10]:
                print(
                    f"  {snap['region']}: {snap['snapshot_id']} ({snap['size_gb']} GB, {snap['age_days']} days old) - ${snap['monthly_cost']:.2f}/month"
                )
        else:
            print("All snapshots are less than 30 days old")
        print()

    print("💡 RECOMMENDATIONS:")
    if unattached_volumes:
        print(
            f"  1. Consider deleting {len(unattached_volumes)} unattached volumes to save ${sum(vol['monthly_cost'] for vol in unattached_volumes):.2f}/month"
        )
    if old_snapshots:
        print(
            f"  2. Review {len(old_snapshots)} old snapshots - delete unnecessary ones to save up to ${sum(snap['monthly_cost'] for snap in old_snapshots):.2f}/month"
        )
    if not unattached_volumes and not old_snapshots:
        print("  All EBS resources appear to be in active use")


if __name__ == "__main__":
    audit_ebs_volumes()
