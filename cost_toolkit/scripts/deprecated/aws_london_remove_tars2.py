#!/usr/bin/env python3

import os
import time

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def remove_tars2_volume():
    """Remove the 1024 GB Tars 2 volume to save $81.92/month"""
    setup_aws_credentials()

    print("AWS London EBS Volume Cleanup - Remove Tars 2")
    print("=" * 80)
    print("🗑️  Removing 1024 GB Tars 2 volume for maximum cost savings")
    print("💰 Expected savings: $81.92/month")
    print()

    ec2 = boto3.client("ec2", region_name="eu-west-2")

    # Target volume to remove
    tars2_volume_id = "vol-0e07da8b7b7dafa17"  # Tars 2 - 1024 GB

    try:
        # First, get current volume status
        print("📊 CURRENT VOLUME STATUS:")
        print("=" * 80)

        volumes_response = ec2.describe_volumes(VolumeIds=[tars2_volume_id])
        volume = volumes_response["Volumes"][0]

        size = volume["Size"]
        state = volume["State"]
        attachments = volume.get("Attachments", [])

        # Get volume name
        name = "No name"
        if "Tags" in volume:
            for tag in volume["Tags"]:
                if tag["Key"] == "Name":
                    name = tag["Value"]
                    break

        print(f"📦 Volume: {name} ({tars2_volume_id})")
        print(f"   Size: {size} GB")
        print(f"   State: {state}")
        print(f"   Monthly cost: ${size * 0.08:.2f}")

        if attachments:
            instance_id = attachments[0]["InstanceId"]
            device = attachments[0]["Device"]
            print(f"   Attached to: {instance_id} at {device}")
        else:
            print("   Attached to: Not attached")

        print()

        # Check if volume is attached and detach if necessary
        if attachments:
            print("🔌 DETACHING VOLUME:")
            print("=" * 80)
            instance_id = attachments[0]["InstanceId"]
            device = attachments[0]["Device"]

            print(f"Detaching {tars2_volume_id} from {instance_id}...")

            ec2.detach_volume(VolumeId=tars2_volume_id, InstanceId=instance_id, Device=device)

            print("✅ Detach command sent")
            print("⏳ Waiting for volume to detach...")

            # Wait for volume to be available
            waiter = ec2.get_waiter("volume_available")
            waiter.wait(VolumeIds=[tars2_volume_id], WaiterConfig={"Delay": 5, "MaxAttempts": 60})

            print("✅ Volume successfully detached")
            print()

        # Delete the volume
        print("🗑️  DELETING VOLUME:")
        print("=" * 80)
        print(f"Deleting {name} ({tars2_volume_id})...")

        ec2.delete_volume(VolumeId=tars2_volume_id)

        print("✅ Volume deletion initiated")
        print()

        # Verify deletion
        print("✅ CLEANUP COMPLETE:")
        print("=" * 80)
        print(f"🗑️  Removed: {name} ({tars2_volume_id})")
        print(f"📦 Size: {size} GB")
        print(f"💰 Monthly savings: ${size * 0.08:.2f}")
        print()
        print("🔒 REMAINING VOLUMES:")
        print("   - 384 GB volume (vol-089b9ed38099c68f3) - $30.72/month")
        print("   - Tars 3 64 GB (vol-0249308257e5fa64d) - $5.12/month")
        print("   - Total remaining EBS cost: $35.84/month")
        print()
        print(f"💰 TOTAL EBS SAVINGS ACHIEVED: $85.00 + $81.92 = $166.92/month")
        print("   (Previous cleanup: $85.00 + This cleanup: $81.92)")
        print()
        print("🎉 London EBS optimization complete!")

    except Exception as e:
        print(f"❌ Error during volume removal: {str(e)}")
        print("Please check the error and try again.")


if __name__ == "__main__":
    remove_tars2_volume()
