#!/usr/bin/env python3
"""
AWS Instance Termination Script
Safely terminates specified instances and handles associated EBS volumes.
"""

import argparse
from threading import Event

import boto3
from botocore.exceptions import ClientError

from cost_toolkit.common import aws_common
from cost_toolkit.common.aws_common import extract_tag_value
from cost_toolkit.common.cost_utils import calculate_ebs_volume_cost

from ..aws_utils import setup_aws_credentials

DEFAULT_INSTANCE_ID = "i-05ad29f28fc8a8fdc"
DEFAULT_INSTANCE_NAME = "Tars 3"
DEFAULT_REGION = "eu-west-2"
_WAIT_EVENT = Event()


def get_instance_details(instance_id, region):
    """Wrapper for tests to fetch instance details using boto3 client."""
    ec2_client = boto3.client("ec2", region_name=region)
    details = aws_common.get_instance_details(ec2_client, instance_id)
    if details:
        details["region"] = region
    return details


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

        return {
            "volume_id": volume_id,
            "name": extract_tag_value(volume, "Name"),
            "size": volume["Size"],
            "volume_type": volume["VolumeType"],
            "state": volume["State"],
            "encrypted": volume["Encrypted"],
        }

    except ClientError as e:
        print(f"❌ Error getting volume details for {volume_id}: {str(e)}")
        return None


def _print_instance_info(instance_info, region):
    """Print instance information."""
    print(f"🔍 Instance to terminate: {instance_info['instance_id']}")
    print(f"   Name: {instance_info['name']}")
    print(f"   Type: {instance_info['instance_type']}")
    print(f"   State: {instance_info['state']}")
    print(f"   Launch Time: {instance_info['launch_time']}")
    print(f"   Region: {region}")
    print()


def _check_and_print_volumes(instance_info, region):
    """Check volumes and return list of volumes to delete manually."""
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
                print("     ✅ Will be automatically deleted with instance")
            else:
                print("     ⚠️  Will remain after termination (manual deletion needed)")
                volumes_to_delete_manually.append(volume["volume_id"])
            print()

    return volumes_to_delete_manually


def _disable_termination_protection(ec2_client, instance_id):
    """Disable termination protection if enabled."""
    try:
        ec2_client.modify_instance_attribute(InstanceId=instance_id, DisableApiTermination={"Value": False})
        print("🔓 Disabled termination protection")
    except ClientError as e:
        print(f"ℹ️  Termination protection check: {str(e)}")


def _perform_termination(ec2_client, instance_id, instance_name):
    """Perform instance termination."""
    print(f"🚨 Terminating instance {instance_id} ({instance_name})...")

    response = ec2_client.terminate_instances(InstanceIds=[instance_id])

    current_state = response["TerminatingInstances"][0]["CurrentState"]["Name"]
    previous_state = response["TerminatingInstances"][0]["PreviousState"]["Name"]

    print("✅ Termination initiated successfully")
    print(f"   Previous state: {previous_state}")
    print(f"   Current state: {current_state}")
    print()


def _delete_manual_volumes(ec2_client, volumes_to_delete, region):
    """Delete volumes that need manual deletion."""
    if not volumes_to_delete:
        return

    print("🗑️  Volumes that need manual deletion:")
    for volume_id in volumes_to_delete:
        volume_details = get_volume_details(volume_id, region)
        if volume_details:
            monthly_cost = calculate_ebs_volume_cost(volume_details["size"], "gp3")
            print(f"   {volume_id} ({volume_details['name']}) - {volume_details['size']} GB")
            print(f"     Monthly cost: ${monthly_cost:.2f}")

            try:
                print(f"     🗑️  Deleting volume {volume_id}...")
                ec2_client.delete_volume(VolumeId=volume_id)
                print(f"     ✅ Volume {volume_id} deletion initiated")
            except ClientError as e:
                print(f"     ❌ Error deleting volume {volume_id}: {str(e)}")
    print()


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

        instance_info = get_instance_details(instance_id, region)
        if not instance_info:
            return False

        _print_instance_info(instance_info, region)

        volumes_to_delete_manually = _check_and_print_volumes(instance_info, region)

        if instance_info["state"] in ["terminated", "terminating"]:
            print(f"ℹ️  Instance {instance_id} is already {instance_info['state']}")
            return True

        _disable_termination_protection(ec2_client, instance_id)

        _perform_termination(ec2_client, instance_id, instance_info["name"])

        print("⏳ Waiting for termination to begin...")
        _WAIT_EVENT.wait(10)

        updated_info = get_instance_details(instance_id, region)
        if updated_info:
            print(f"📊 Current status: {updated_info['state']}")

        _delete_manual_volumes(ec2_client, volumes_to_delete_manually, region)

    except ClientError as e:
        print(f"❌ Error terminating instance {instance_id}: {str(e)}")
        return False
    return True


def _parse_args(argv=None):
    """Parse CLI arguments for the termination script."""
    parser = argparse.ArgumentParser(
        description="Safely terminate an EC2 instance and related volumes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--instance-id", help="Target EC2 instance ID")
    parser.add_argument("--region", help="AWS region for the target instance")
    parser.add_argument("--instance-name", help="Friendly instance name for messaging")
    parser.add_argument(
        "--use-default-target",
        action="store_true",
        help="Use the baked-in demo instance/region (requires explicit opt-in).",
    )
    args = parser.parse_args(argv)

    if not args.use_default_target and (not args.instance_id or not args.region):
        parser.error("Specify --instance-id and --region or use --use-default-target.")

    instance_id = args.instance_id or DEFAULT_INSTANCE_ID
    region = args.region or DEFAULT_REGION
    name = args.instance_name or DEFAULT_INSTANCE_NAME

    return {"id": instance_id, "name": name, "region": region}, args.use_default_target


def main(argv=None):
    """Main function to terminate the selected instance."""
    setup_aws_credentials()

    print("AWS Instance Termination Script")
    print("=" * 80)
    print("Terminating a selected instance and associated volumes...")
    print("⚠️  This action is IRREVERSIBLE!")
    print()

    target_instance, using_default = _parse_args(argv)
    if using_default:
        print("⚠️  Using default demo target; provide --instance-id/--region to override.")

    print(f"🎯 Target Instance: {target_instance['name']} ({target_instance['id']})")
    print(f"   Region: {target_instance['region']}")
    print()

    # Safety confirmation
    print("⚠️  FINAL WARNING: This will permanently destroy the instance and its data!")
    print(f"   - Instance '{target_instance['name']}' will be terminated")
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
