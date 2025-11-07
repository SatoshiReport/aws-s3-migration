#!/usr/bin/env python3
"""
AWS AMI and Snapshot Analysis Script
Analyzes AMIs that are preventing snapshot deletion and provides detailed information
about what each AMI is used for and whether it can be safely deregistered.
"""

import os
from datetime import datetime

import boto3
from dotenv import load_dotenv


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def get_ami_details(ec2_client, ami_id):
    """Get detailed information about an AMI"""
    try:
        response = ec2_client.describe_images(ImageIds=[ami_id])
        if response["Images"]:
            ami = response["Images"][0]
            return {
                "ami_id": ami_id,
                "name": ami.get("Name", "N/A"),
                "description": ami.get("Description", "N/A"),
                "state": ami.get("State", "N/A"),
                "creation_date": ami.get("CreationDate", "N/A"),
                "owner_id": ami.get("OwnerId", "N/A"),
                "public": ami.get("Public", False),
                "platform": ami.get("Platform", "Linux"),
                "architecture": ami.get("Architecture", "N/A"),
                "virtualization_type": ami.get("VirtualizationType", "N/A"),
                "root_device_type": ami.get("RootDeviceType", "N/A"),
                "block_device_mappings": ami.get("BlockDeviceMappings", []),
                "tags": ami.get("Tags", []),
            }
    except Exception as e:
        return {"ami_id": ami_id, "error": str(e), "accessible": False}
    return None


def check_ami_usage(ec2_client, ami_id):
    """Check if AMI is currently being used by any instances"""
    try:
        # Check for running instances using this AMI
        response = ec2_client.describe_instances(
            Filters=[
                {"Name": "image-id", "Values": [ami_id]},
                {
                    "Name": "instance-state-name",
                    "Values": ["pending", "running", "shutting-down", "stopping", "stopped"],
                },
            ]
        )

        instances = []
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                instances.append(
                    {
                        "instance_id": instance["InstanceId"],
                        "state": instance["State"]["Name"],
                        "launch_time": instance.get("LaunchTime", "N/A"),
                        "instance_type": instance.get("InstanceType", "N/A"),
                        "tags": instance.get("Tags", []),
                    }
                )

        return instances
    except Exception as e:
        print(f"   ❌ Error checking AMI usage: {e}")
        return []


def analyze_snapshot_ami_relationships():
    """Analyze the relationship between snapshots and AMIs"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    # Snapshots that couldn't be deleted and their associated AMIs
    snapshot_ami_mapping = {
        "snap-09e90c64db692f884": {"ami": "ami-0cb04cf30dc50a00e", "region": "eu-west-2"},
        "snap-07c0d4017e24b3240": {"ami": "ami-0abc073133c9d3e18", "region": "us-east-1"},
        "snap-0fbb003580d3dc8ba": {"ami": "ami-0b340e8c04ad01f48", "region": "us-east-1"},
        "snap-024d718f6d670bff2": {"ami": "ami-0833a92e637927528", "region": "us-east-1"},
        "snap-0ac8b88270ff68d4d": {"ami": "ami-0cb41e78dab346fb3", "region": "us-east-1"},
        "snap-036eee4a7c291fd26": {"ami": "ami-05d0a30507ebee9d6", "region": "us-east-2"},
        "snap-0700cdc4cdfaaf8fd": {"ami": "ami-07b9b9991f7466e6d", "region": "us-east-2"},
        "snap-05a42843f18ba1c5e": {"ami": "ami-0966e8f6fa677382b", "region": "us-east-2"},
    }

    print("AWS AMI and Snapshot Analysis")
    print("=" * 80)
    print("Analyzing AMIs that are preventing snapshot deletion...\n")

    total_potential_savings = 0

    for snapshot_id, info in snapshot_ami_mapping.items():
        ami_id = info["ami"]
        region = info["region"]

        print(f"🔍 Analyzing {snapshot_id} -> {ami_id} in {region}")
        print("-" * 60)

        # Create EC2 client for the specific region
        ec2_client = boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        # Get AMI details
        ami_details = get_ami_details(ec2_client, ami_id)

        if ami_details and "error" not in ami_details:
            print(f"   📋 AMI Name: {ami_details['name']}")
            print(f"   📝 Description: {ami_details['description']}")
            print(f"   📅 Created: {ami_details['creation_date']}")
            print(f"   🏗️  Architecture: {ami_details['architecture']}")
            print(f"   💻 Platform: {ami_details['platform']}")
            print(f"   🔧 State: {ami_details['state']}")
            print(f"   🔒 Public: {ami_details['public']}")

            # Check for tags
            if ami_details["tags"]:
                print("   🏷️  Tags:")
                for tag in ami_details["tags"]:
                    print(f"      {tag['Key']}: {tag['Value']}")
            else:
                print("   🏷️  Tags: None")

            # Check if AMI is being used by any instances
            instances = check_ami_usage(ec2_client, ami_id)
            if instances:
                print(f"   ⚠️  Currently used by {len(instances)} instance(s):")
                for instance in instances:
                    instance_name = "Unnamed"
                    for tag in instance["tags"]:
                        if tag["Key"] == "Name":
                            instance_name = tag["Value"]
                            break
                    print(
                        f"      - {instance['instance_id']} ({instance_name}) - {instance['state']}"
                    )
            else:
                print("   ✅ Not currently used by any instances")

            # Calculate potential savings if this snapshot could be deleted
            # Get snapshot details to calculate cost
            try:
                snapshots = ec2_client.describe_snapshots(SnapshotIds=[snapshot_id])
                if snapshots["Snapshots"]:
                    snapshot = snapshots["Snapshots"][0]
                    size_gb = snapshot["VolumeSize"]
                    monthly_cost = size_gb * 0.05  # $0.05 per GB per month
                    total_potential_savings += monthly_cost
                    print(f"   💰 Snapshot size: {size_gb} GB")
                    print(f"   💰 Monthly cost: ${monthly_cost:.2f}")

                    if not instances:
                        print(
                            f"   💡 RECOMMENDATION: This AMI appears unused - consider deregistering to save ${monthly_cost:.2f}/month"
                        )
                    else:
                        print(
                            f"   ⚠️  CAUTION: AMI is in use - verify instances before deregistering"
                        )
            except Exception as e:
                print(f"   ❌ Error getting snapshot details: {e}")

        elif ami_details and "error" in ami_details:
            print(f"   ❌ Error accessing AMI: {ami_details['error']}")
            print("   💡 This AMI may be owned by another account or may not exist")
        else:
            print("   ❌ AMI not found or inaccessible")

        print()

    print("=" * 80)
    print("🎯 SUMMARY")
    print("=" * 80)
    print(f"Total snapshots analyzed: {len(snapshot_ami_mapping)}")
    print(
        f"Total potential monthly savings if all AMIs were deregistered: ${total_potential_savings:.2f}"
    )
    print(f"Total potential annual savings: ${total_potential_savings * 12:.2f}")
    print()
    print("💡 NEXT STEPS:")
    print("1. Review each AMI to determine if it's still needed")
    print("2. For unused AMIs, deregister them using: aws ec2 deregister-image --image-id <ami-id>")
    print("3. After deregistering AMIs, the associated snapshots can be deleted")
    print("4. Always verify that no critical systems depend on these AMIs before deregistering")


if __name__ == "__main__":
    try:
        analyze_snapshot_ami_relationships()
    except Exception as e:
        print(f"❌ Script failed: {e}")
        exit(1)
