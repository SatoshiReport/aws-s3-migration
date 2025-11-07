#!/usr/bin/env python3
"""
AWS EBS Volume Management Script
Handles volume deletion and detailed volume information retrieval.
"""

import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

import boto3

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aws_utils import setup_aws_credentials


def get_all_aws_regions() -> List[str]:
    """
    Get all available AWS regions by querying the EC2 service.

    Returns:
        List of AWS region names
    """
    ec2_client = boto3.client("ec2", region_name="us-east-1")
    response = ec2_client.describe_regions()
    return [region["RegionName"] for region in response["Regions"]]


def find_volume_region(volume_id: str) -> Optional[str]:
    """
    Find which region contains the specified volume.

    Args:
        volume_id: The EBS volume ID to locate

    Returns:
        Region name if found, None otherwise
    """
    regions = get_all_aws_regions()

    for region in regions:
        try:
            ec2_client = boto3.client("ec2", region_name=region)
            response = ec2_client.describe_volumes(VolumeIds=[volume_id])
            if response["Volumes"]:
                return region
        except ec2_client.exceptions.ClientError as e:
            if "InvalidVolume.NotFound" in str(e):
                continue
            raise

    return None


def get_instance_name(instance_id: str, region: str) -> str:
    """
    Get the Name tag value for an EC2 instance.

    Args:
        instance_id: The EC2 instance ID
        region: AWS region where the instance is located

    Returns:
        Instance name from Name tag, or 'No Name' if not found
    """
    ec2_client = boto3.client("ec2", region_name=region)

    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                for tag in instance.get("Tags", []):
                    if tag["Key"] == "Name":
                        return tag["Value"]
        return "No Name"
    except Exception:
        return "Unknown"


def get_volume_tags(volume: Dict) -> Dict[str, str]:
    """
    Extract tags from a volume description.

    Args:
        volume: Volume description from AWS API

    Returns:
        Dictionary of tag key-value pairs
    """
    tags = {}
    for tag in volume.get("Tags", []):
        tags[tag["Key"]] = tag["Value"]
    return tags


def get_volume_detailed_info(volume_id: str) -> Dict:
    """
    Get comprehensive information about a specific EBS volume.

    Args:
        volume_id: The EBS volume ID to analyze

    Returns:
        Dictionary containing detailed volume information
    """
    region = find_volume_region(volume_id)
    if not region:
        raise ValueError(f"Volume {volume_id} not found in any region")

    ec2_client = boto3.client("ec2", region_name=region)
    cloudwatch_client = boto3.client("cloudwatch", region_name=region)

    # Get volume details
    response = ec2_client.describe_volumes(VolumeIds=[volume_id])
    volume = response["Volumes"][0]

    # Extract basic information
    volume_info = {
        "volume_id": volume_id,
        "region": region,
        "size_gb": volume["Size"],
        "volume_type": volume["VolumeType"],
        "state": volume["State"],
        "create_time": volume["CreateTime"],
        "availability_zone": volume["AvailabilityZone"],
        "encrypted": volume["Encrypted"],
        "iops": volume.get("Iops", "N/A"),
        "throughput": volume.get("Throughput", "N/A"),
        "tags": get_volume_tags(volume),
    }

    # Get attachment information
    attachments = volume.get("Attachments", [])
    if attachments:
        attachment = attachments[0]
        instance_id = attachment["InstanceId"]
        volume_info["attached_to_instance_id"] = instance_id
        volume_info["attached_to_instance_name"] = get_instance_name(instance_id, region)
        volume_info["device"] = attachment["Device"]
        volume_info["attach_time"] = attachment["AttachTime"]
        volume_info["delete_on_termination"] = attachment["DeleteOnTermination"]
    else:
        volume_info["attached_to_instance_id"] = None
        volume_info["attached_to_instance_name"] = "Not attached"
        volume_info["device"] = None
        volume_info["attach_time"] = None
        volume_info["delete_on_termination"] = None

    # Get CloudWatch metrics for last usage
    try:
        # Query VolumeReadOps metric for the last 30 days
        end_time = datetime.now(timezone.utc)
        start_time = end_time.replace(day=1)  # Start of current month

        metrics_response = cloudwatch_client.get_metric_statistics(
            Namespace="AWS/EBS",
            MetricName="VolumeReadOps",
            Dimensions=[{"Name": "VolumeId", "Value": volume_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,  # Daily
            Statistics=["Sum"],
        )

        if metrics_response["Datapoints"]:
            # Sort by timestamp and get the most recent
            sorted_datapoints = sorted(
                metrics_response["Datapoints"], key=lambda x: x["Timestamp"], reverse=True
            )
            volume_info["last_read_activity"] = sorted_datapoints[0]["Timestamp"]
        else:
            volume_info["last_read_activity"] = "No recent activity"

    except Exception as e:
        volume_info["last_read_activity"] = f"Error retrieving metrics: {str(e)}"

    return volume_info


def delete_ebs_volume(volume_id: str, force: bool = False) -> bool:
    """
    Delete an EBS volume after safety checks.

    Args:
        volume_id: The EBS volume ID to delete
        force: Skip safety prompts if True

    Returns:
        True if deletion successful, False otherwise
    """
    region = find_volume_region(volume_id)
    if not region:
        print(f"❌ Volume {volume_id} not found in any region")
        return False

    ec2_client = boto3.client("ec2", region_name=region)

    # Get volume information before deletion
    try:
        response = ec2_client.describe_volumes(VolumeIds=[volume_id])
        volume = response["Volumes"][0]
    except ec2_client.exceptions.ClientError as e:
        print(f"❌ Error retrieving volume {volume_id}: {str(e)}")
        return False

    # Safety checks
    if volume["State"] == "in-use":
        print(f"❌ Volume {volume_id} is currently attached to an instance")
        print("   You must detach the volume before deletion")
        return False

    # Display volume information
    print(f"🔍 Volume to delete: {volume_id}")
    print(f"   Region: {region}")
    print(f"   Size: {volume['Size']} GB")
    print(f"   Type: {volume['VolumeType']}")
    print(f"   State: {volume['State']}")
    print(f"   Created: {volume['CreateTime']}")

    tags = get_volume_tags(volume)
    if tags:
        print("   Tags:")
        for key, value in tags.items():
            print(f"     {key}: {value}")

    # Confirmation prompt unless forced
    if not force:
        print("\n⚠️  WARNING: This action cannot be undone!")
        confirmation = input("Type 'DELETE' to confirm volume deletion: ")
        if confirmation != "DELETE":
            print("❌ Deletion cancelled")
            return False

    # Perform deletion
    try:
        ec2_client.delete_volume(VolumeId=volume_id)
        print(f"✅ Volume {volume_id} deletion initiated successfully")
        print("   The volume will be permanently deleted within a few minutes")
        return True
    except Exception as e:
        print(f"❌ Error deleting volume {volume_id}: {str(e)}")
        return False


def print_volume_detailed_report(volume_info: Dict) -> None:
    """
    Print a comprehensive report for a volume.

    Args:
        volume_info: Dictionary containing volume information
    """
    print(f"📦 Volume: {volume_info['volume_id']}")
    print(f"   Region: {volume_info['region']}")
    print(f"   Type: {volume_info['volume_type']}")
    print(f"   Size: {volume_info['size_gb']} GB")
    print(f"   State: {volume_info['state']}")
    print(f"   Created: {volume_info['create_time']}")
    print(f"   Availability Zone: {volume_info['availability_zone']}")
    print(f"   Encrypted: {volume_info['encrypted']}")

    if volume_info["iops"] != "N/A":
        print(f"   IOPS: {volume_info['iops']}")
    if volume_info["throughput"] != "N/A":
        print(f"   Throughput: {volume_info['throughput']} MB/s")

    # Attachment information
    if volume_info["attached_to_instance_id"]:
        print(f"   Attached to Instance: {volume_info['attached_to_instance_id']}")
        print(f"   Instance Name: {volume_info['attached_to_instance_name']}")
        print(f"   Device: {volume_info['device']}")
        print(f"   Attached Since: {volume_info['attach_time']}")
        print(f"   Delete on Termination: {volume_info['delete_on_termination']}")
    else:
        print(f"   Attachment Status: {volume_info['attached_to_instance_name']}")

    # Tags
    if volume_info["tags"]:
        print("   Tags:")
        for key, value in volume_info["tags"].items():
            print(f"     {key}: {value}")
    else:
        print("   Tags: None")

    # Usage information
    print(f"   Last Read Activity: {volume_info['last_read_activity']}")

    print()


def create_volume_snapshot(volume_id: str, description: Optional[str] = None) -> Dict:
    """
    Create a snapshot of an EBS volume.

    Args:
        volume_id: The EBS volume ID to snapshot
        description: Optional description for the snapshot

    Returns:
        Dictionary containing snapshot information
    """
    region = find_volume_region(volume_id)
    if not region:
        raise ValueError(f"Volume {volume_id} not found in any region")

    ec2_client = boto3.client("ec2", region_name=region)

    # Get volume information for the description
    try:
        response = ec2_client.describe_volumes(VolumeIds=[volume_id])
        volume = response["Volumes"][0]
        volume_size = volume["Size"]
        volume_tags = get_volume_tags(volume)
        volume_name = volume_tags.get("Name", "Unnamed")

        # Create default description if none provided
        if not description:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            description = f"Snapshot of {volume_name} ({volume_id}) - {volume_size}GB - {timestamp}"

    except Exception as e:
        raise ValueError(f"Error retrieving volume {volume_id}: {str(e)}")

    # Create the snapshot
    try:
        snapshot_response = ec2_client.create_snapshot(VolumeId=volume_id, Description=description)

        snapshot_id = snapshot_response["SnapshotId"]

        # Add tags to the snapshot to match the volume
        if volume_tags:
            snapshot_tags = []
            for key, value in volume_tags.items():
                if key == "Name":
                    snapshot_tags.append({"Key": "Name", "Value": f"{value}-snapshot"})
                else:
                    snapshot_tags.append({"Key": key, "Value": value})

            # Add additional metadata tags
            snapshot_tags.extend(
                [
                    {"Key": "SourceVolume", "Value": volume_id},
                    {"Key": "CreatedBy", "Value": "aws_ebs_volume_manager"},
                    {
                        "Key": "CreatedDate",
                        "Value": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    },
                ]
            )

            ec2_client.create_tags(Resources=[snapshot_id], Tags=snapshot_tags)

        return {
            "snapshot_id": snapshot_id,
            "volume_id": volume_id,
            "region": region,
            "description": description,
            "state": snapshot_response["State"],
            "start_time": snapshot_response["StartTime"],
            "volume_size": volume_size,
            "volume_name": volume_name,
        }

    except Exception as e:
        raise ValueError(f"Error creating snapshot for volume {volume_id}: {str(e)}")


def create_multiple_snapshots(volume_ids: List[str]) -> List[Dict]:
    """
    Create snapshots for multiple volumes.

    Args:
        volume_ids: List of volume IDs to snapshot

    Returns:
        List of dictionaries containing snapshot information
    """
    snapshots = []

    for volume_id in volume_ids:
        try:
            print(f"🔄 Creating snapshot for volume {volume_id}...")
            snapshot_info = create_volume_snapshot(volume_id)
            snapshots.append(snapshot_info)
            print(f"✅ Snapshot {snapshot_info['snapshot_id']} created successfully")
            print(f"   Volume: {snapshot_info['volume_name']} ({snapshot_info['volume_size']} GB)")
            print(f"   Region: {snapshot_info['region']}")
            print()
        except Exception as e:
            print(f"❌ Error creating snapshot for {volume_id}: {str(e)}")
            print()

    return snapshots


def main():
    """Main function to handle command line arguments and execute operations."""
    if len(sys.argv) < 2:
        print("AWS EBS Volume Manager")
        print("=" * 50)
        print("Usage:")
        print("  Delete volume:     python aws_ebs_volume_manager.py delete <volume-id>")
        print(
            "  Get volume info:   python aws_ebs_volume_manager.py info <volume-id> [volume-id2] ..."
        )
        print(
            "  Create snapshot:   python aws_ebs_volume_manager.py snapshot <volume-id> [volume-id2] ..."
        )
        print("  Force delete:      python aws_ebs_volume_manager.py delete <volume-id> --force")
        print()
        print("Examples:")
        print("  python aws_ebs_volume_manager.py delete vol-01b1dadf1397de37c")
        print("  python aws_ebs_volume_manager.py info vol-089b9ed38099c68f3 vol-0249308257e5fa64d")
        print(
            "  python aws_ebs_volume_manager.py snapshot vol-089b9ed38099c68f3 vol-0249308257e5fa64d"
        )
        sys.exit(1)

    # Setup AWS credentials
    setup_aws_credentials()

    command = sys.argv[1].lower()

    if command == "delete":
        if len(sys.argv) < 3:
            print("❌ Volume ID required for delete command")
            sys.exit(1)

        volume_id = sys.argv[2]
        force = "--force" in sys.argv

        print("AWS EBS Volume Deletion")
        print("=" * 50)
        success = delete_ebs_volume(volume_id, force)
        sys.exit(0 if success else 1)

    elif command == "info":
        if len(sys.argv) < 3:
            print("❌ At least one volume ID required for info command")
            sys.exit(1)

        volume_ids = sys.argv[2:]

        print("AWS EBS Volume Detailed Information")
        print("=" * 50)

        for volume_id in volume_ids:
            try:
                volume_info = get_volume_detailed_info(volume_id)
                print_volume_detailed_report(volume_info)
            except Exception as e:
                print(f"❌ Error getting info for {volume_id}: {str(e)}")
                print()

    elif command == "snapshot":
        if len(sys.argv) < 3:
            print("❌ At least one volume ID required for snapshot command")
            sys.exit(1)

        volume_ids = sys.argv[2:]

        print("AWS EBS Volume Snapshot Creation")
        print("=" * 50)

        snapshots = create_multiple_snapshots(volume_ids)

        if snapshots:
            print("📊 SNAPSHOT SUMMARY:")
            print("=" * 50)
            total_size = sum(snap["volume_size"] for snap in snapshots)
            estimated_monthly_cost = total_size * 0.05  # $0.05 per GB/month for snapshots

            print(f"✅ Created {len(snapshots)} snapshots")
            print(f"📦 Total size: {total_size} GB")
            print(f"💰 Estimated monthly cost: ${estimated_monthly_cost:.2f}")
            print()

            for snapshot in snapshots:
                print(
                    f"  {snapshot['snapshot_id']} ({snapshot['volume_name']}) - {snapshot['volume_size']} GB"
                )
            print()
            print("💡 Snapshots are being created in the background and will be available shortly.")

    else:
        print(f"❌ Unknown command: {command}")
        print("Valid commands: delete, info, snapshot")
        sys.exit(1)


if __name__ == "__main__":
    main()
