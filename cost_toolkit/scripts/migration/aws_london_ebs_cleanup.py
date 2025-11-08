#!/usr/bin/env python3

import os
from datetime import datetime

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def cleanup_london_ebs_volumes():  # noqa: C901, PLR0912, PLR0915
    """Clean up duplicate and unattached EBS volumes in London"""
    setup_aws_credentials()

    print("AWS London EBS Volume Cleanup")
    print("=" * 80)

    ec2 = boto3.client("ec2", region_name="eu-west-2")

    # Volumes to delete
    volumes_to_delete = [
        {
            "id": "vol-0e148f66bcb4f7a0b",
            "name": "Tars (OLD)",
            "size": "1024 GB",
            "reason": "Duplicate - older version of Tars 2",
            "savings": "$82/month",
        },
        {
            "id": "vol-08f9abc839d13db62",
            "name": "Unattached",
            "size": "32 GB",
            "reason": "Unattached volume - not in use",
            "savings": "$3/month",
        },
    ]

    print("🗑️  Volumes scheduled for deletion:")
    total_savings = 0
    for vol in volumes_to_delete:
        print(f"   • {vol['id']} ({vol['name']}) - {vol['size']}")
        print(f"     Reason: {vol['reason']}")
        print(f"     Savings: {vol['savings']}")
        savings_amount = int(vol["savings"].replace("$", "").replace("/month", ""))
        total_savings += savings_amount
        print()

    print(f"💰 Total estimated monthly savings: ${total_savings}")
    print()

    # First, detach the old Tars volume if it's still attached
    print("🔧 Step 1: Detaching old Tars volume if attached...")
    try:
        # Check if volume is attached
        response = ec2.describe_volumes(VolumeIds=["vol-0e148f66bcb4f7a0b"])
        volume = response["Volumes"][0]

        if volume["Attachments"]:
            attachment = volume["Attachments"][0]
            instance_id = attachment["InstanceId"]
            device = attachment["Device"]

            print(f"   Volume is attached to {instance_id} as {device}")
            print("   Detaching volume...")

            ec2.detach_volume(
                VolumeId="vol-0e148f66bcb4f7a0b", InstanceId=instance_id, Device=device, Force=True
            )

            print("   ✅ Volume detachment initiated")

            # Wait for detachment
            print("   Waiting for volume to detach...")
            waiter = ec2.get_waiter("volume_available")
            waiter.wait(VolumeIds=["vol-0e148f66bcb4f7a0b"])
            print("   ✅ Volume successfully detached")
        else:
            print("   Volume is already detached")

    except Exception as e:
        print(f"   ❌ Error detaching volume: {str(e)}")
        return

    print()
    print("🗑️  Step 2: Deleting volumes...")

    deleted_volumes = []
    failed_deletions = []

    for vol in volumes_to_delete:
        try:
            print(f"   Deleting {vol['id']} ({vol['name']})...")

            # Delete the volume
            ec2.delete_volume(VolumeId=vol["id"])

            print(f"   ✅ Successfully deleted {vol['id']}")
            deleted_volumes.append(vol)

        except Exception as e:
            print(f"   ❌ Failed to delete {vol['id']}: {str(e)}")
            failed_deletions.append({"volume": vol, "error": str(e)})

    print()
    print("📊 CLEANUP SUMMARY:")
    print("=" * 80)

    if deleted_volumes:
        print("✅ Successfully deleted volumes:")
        total_deleted_savings = 0
        for vol in deleted_volumes:
            print(f"   • {vol['id']} ({vol['name']}) - {vol['size']}")
            savings_amount = int(vol["savings"].replace("$", "").replace("/month", ""))
            total_deleted_savings += savings_amount
        print(f"   💰 Monthly savings achieved: ${total_deleted_savings}")
        print()

    if failed_deletions:
        print("❌ Failed deletions:")
        for failure in failed_deletions:
            vol = failure["volume"]
            error = failure["error"]
            print(f"   • {vol['id']} ({vol['name']}): {error}")
        print()

    # Show remaining volumes
    print("📦 Remaining London EBS volumes:")
    try:
        response = ec2.describe_volumes(
            Filters=[
                {"Name": "state", "Values": ["available", "in-use"]},
                {"Name": "availability-zone", "Values": ["eu-west-2a", "eu-west-2b", "eu-west-2c"]},
            ]
        )

        remaining_cost = 0
        for volume in response["Volumes"]:
            size = volume["Size"]
            vol_id = volume["VolumeId"]
            state = volume["State"]

            # Get volume name from tags
            name = "No name"
            if "Tags" in volume:
                for tag in volume["Tags"]:
                    if tag["Key"] == "Name":
                        name = tag["Value"]
                        break

            monthly_cost = size * 0.08  # $0.08 per GB per month for gp2
            remaining_cost += monthly_cost

            print(f"   • {vol_id} ({name}) - {size} GB - {state} - ${monthly_cost:.2f}/month")

        print(f"   💰 Total remaining monthly cost: ${remaining_cost:.2f}")

    except Exception as e:
        print(f"   ❌ Error listing remaining volumes: {str(e)}")

    print()
    print("🎯 OPTIMIZATION COMPLETE!")
    print(f"   Estimated monthly savings: ${total_deleted_savings if deleted_volumes else 0}")
    print("   Duplicate 'Tars' volume removed, keeping newer 'Tars 2'")
    print("   Unattached volume removed")


if __name__ == "__main__":
    cleanup_london_ebs_volumes()
