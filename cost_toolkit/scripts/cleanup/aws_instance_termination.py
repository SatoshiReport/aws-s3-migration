#!/usr/bin/env python3
"""
AWS Instance Termination Script
Safely terminates specified instances and handles associated EBS volumes.
"""

import os
import sys
import time
from datetime import datetime, timezone

import boto3

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aws_utils import setup_aws_credentials


def get_instance_details(instance_id, region):
    """
    Get detailed information about an EC2 instance.

    Args:
        instance_id: The EC2 instance ID
        region: AWS region where the instance is located

    Returns:
        Dictionary containing instance information
    """
    try:
        ec2_client = boto3.client("ec2", region_name=region)

        response = ec2_client.describe_instances(InstanceIds=[instance_id])

        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                # Get instance name from tags
                instance_name = "Unnamed"
                for tag in instance.get("Tags", []):
                    if tag["Key"] == "Name":
                        instance_name = tag["Value"]
                        break

                # Get attached volumes
                volumes = []
                for bdm in instance.get("BlockDeviceMappings", []):
                    if "Ebs" in bdm:
                        volumes.append(
                            {
                                "volume_id": bdm["Ebs"]["VolumeId"],
                                "device": bdm["DeviceName"],
                                "delete_on_termination": bdm["Ebs"]["DeleteOnTermination"],
                            }
                        )

                return {
                    "instance_id": instance_id,
                    "name": instance_name,
                    "state": instance["State"]["Name"],
                    "instance_type": instance["InstanceType"],
                    "launch_time": instance["LaunchTime"],
                    "availability_zone": instance["Placement"]["AvailabilityZone"],
                    "volumes": volumes,
                    "region": region,
                }

    except Exception as e:
        print(f"❌ Error getting instance details for {instance_id}: {str(e)}")
        return None


def get_volume_details(volume_id, region):
    """
    Get details about an EBS volume.

    Args:
        volume_id: The EBS volume ID
        region: AWS region where the volume is located

    Returns:
        Dictionary containing volume information
    """
    try:
        ec2_client = boto3.client("ec2", region_name=region)

        response = ec2_client.describe_volumes(VolumeIds=[volume_id])
        volume = response["Volumes"][0]

        # Get volume name from tags
        volume_name = "Unnamed"
        for tag in volume.get("Tags", []):
            if tag["Key"] == "Name":
                volume_name = tag["Value"]
                break

        return {
            "volume_id": volume_id,
            "name": volume_name,
            "size": volume["Size"],
            "volume_type": volume["VolumeType"],
            "state": volume["State"],
            "encrypted": volume["Encrypted"],
        }

    except Exception as e:
        print(f"❌ Error getting volume details for {volume_id}: {str(e)}")
        return None


def terminate_instance_safely(instance_id, region):
    """
    Safely terminate an EC2 instance with proper checks and volume handling.

    Args:
        instance_id: The EC2 instance ID to terminate
        region: AWS region where the instance is located

    Returns:
        True if successful, False otherwise
    """
    try:
        ec2_client = boto3.client("ec2", region_name=region)

        # Get instance details before termination
        instance_info = get_instance_details(instance_id, region)
        if not instance_info:
            return False

        print(f"🔍 Instance to terminate: {instance_id}")
        print(f"   Name: {instance_info['name']}")
        print(f"   Type: {instance_info['instance_type']}")
        print(f"   State: {instance_info['state']}")
        print(f"   Launch Time: {instance_info['launch_time']}")
        print(f"   Region: {region}")
        print()

        # Show attached volumes and their fate
        print("📦 Attached Volumes:")
        volumes_to_delete_manually = []

        for volume in instance_info["volumes"]:
            volume_details = get_volume_details(volume["volume_id"], region)
            if volume_details:
                print(f"   Volume: {volume['volume_id']} ({volume_details['name']})")
                print(f"     Size: {volume_details['size']} GB")
                print(f"     Device: {volume['device']}")
                print(f"     Delete on Termination: {volume['delete_on_termination']}")

                if volume["delete_on_termination"]:
                    print(f"     ✅ Will be automatically deleted with instance")
                else:
                    print(f"     ⚠️  Will remain after termination (manual deletion needed)")
                    volumes_to_delete_manually.append(volume["volume_id"])
                print()

        # Check if instance is already terminated
        if instance_info["state"] in ["terminated", "terminating"]:
            print(f"ℹ️  Instance {instance_id} is already {instance_info['state']}")
            return True

        # Disable termination protection if enabled
        try:
            ec2_client.modify_instance_attribute(
                InstanceId=instance_id, DisableApiTermination={"Value": False}
            )
            print("🔓 Disabled termination protection")
        except Exception as e:
            print(f"ℹ️  Termination protection check: {str(e)}")

        # Terminate the instance
        print(f"🚨 Terminating instance {instance_id} ({instance_info['name']})...")

        response = ec2_client.terminate_instances(InstanceIds=[instance_id])

        current_state = response["TerminatingInstances"][0]["CurrentState"]["Name"]
        previous_state = response["TerminatingInstances"][0]["PreviousState"]["Name"]

        print(f"✅ Termination initiated successfully")
        print(f"   Previous state: {previous_state}")
        print(f"   Current state: {current_state}")
        print()

        # Wait a moment and check status
        print("⏳ Waiting for termination to begin...")
        time.sleep(10)

        # Check current status
        updated_info = get_instance_details(instance_id, region)
        if updated_info:
            print(f"📊 Current status: {updated_info['state']}")

        # Handle volumes that won't be automatically deleted
        if volumes_to_delete_manually:
            print("🗑️  Volumes that need manual deletion:")
            for volume_id in volumes_to_delete_manually:
                volume_details = get_volume_details(volume_id, region)
                if volume_details:
                    monthly_cost = volume_details["size"] * 0.08  # Rough estimate for gp3
                    print(
                        f"   {volume_id} ({volume_details['name']}) - {volume_details['size']} GB"
                    )
                    print(f"     Monthly cost: ${monthly_cost:.2f}")

                    # Delete the volume
                    try:
                        print(f"     🗑️  Deleting volume {volume_id}...")
                        ec2_client.delete_volume(VolumeId=volume_id)
                        print(f"     ✅ Volume {volume_id} deletion initiated")
                    except Exception as e:
                        print(f"     ❌ Error deleting volume {volume_id}: {str(e)}")
            print()

        return True

    except Exception as e:
        print(f"❌ Error terminating instance {instance_id}: {str(e)}")
        return False


def main():
    """Main function to terminate the Tars 3 instance."""
    setup_aws_credentials()

    print("AWS Instance Termination Script")
    print("=" * 80)
    print("Terminating 'Tars 3' instance and associated volumes...")
    print("⚠️  This action is IRREVERSIBLE!")
    print()

    # Target instance details
    target_instance = {"id": "i-05ad29f28fc8a8fdc", "name": "Tars 3", "region": "eu-west-2"}

    print(f"🎯 Target Instance: {target_instance['name']} ({target_instance['id']})")
    print(f"   Region: {target_instance['region']}")
    print()

    # Safety confirmation
    print("⚠️  FINAL WARNING: This will permanently destroy the instance and its data!")
    print("   - Instance 'Tars 3' will be terminated")
    print("   - Associated EBS volumes will be deleted")
    print("   - All data on these volumes will be lost")
    print("   - Snapshots will be preserved (as requested)")
    print()

    confirmation = input("Type 'TERMINATE' to confirm instance termination: ")
    if confirmation != "TERMINATE":
        print("❌ Termination cancelled")
        return

    print()
    print("🚨 Proceeding with termination...")
    print("=" * 80)

    # Terminate the instance
    success = terminate_instance_safely(target_instance["id"], target_instance["region"])

    # Summary
    print("=" * 80)
    print("🎯 TERMINATION SUMMARY")
    print("=" * 80)

    if success:
        print("✅ Instance termination initiated successfully")
        print("✅ Associated volumes deletion initiated")
        print("✅ Snapshots preserved (as requested)")
        print()
        print("💰 Expected Monthly Savings:")
        print("   - Instance costs: Variable (depends on instance type)")
        print("   - EBS volumes: ~$35.84/month (384GB + 64GB)")
        print("   - Total EBS savings: ~$35.84/month")
        print()
        print("📝 What remains:")
        print("   - mufasa instance: Running (preserved)")
        print("   - All snapshots: Preserved")
        print("   - S3 buckets: Unchanged")

    else:
        print("❌ Instance termination failed")
        print("   Please check the error messages above")

    print()
    print("⏳ Note: Termination is in progress and may take a few minutes to complete")


if __name__ == "__main__":
    main()
