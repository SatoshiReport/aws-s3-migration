"""
AWS EBS Volume Reporting Module
Handles report formatting and output for volume information and snapshots.
"""

from typing import Dict, List


def print_volume_detailed_report(volume_info: Dict) -> None:
    """
    Print a comprehensive report for a volume.

    Args:
        volume_info: Dictionary containing volume information
    """
    print(f"Volume: {volume_info['volume_id']}")
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


def print_snapshot_summary(snapshots: List[Dict]) -> None:
    """
    Print summary of created snapshots.

    Args:
        snapshots: List of dictionaries containing snapshot information
    """
    print("SNAPSHOT SUMMARY:")
    print("=" * 50)
    total_size = sum(snap["volume_size"] for snap in snapshots)
    estimated_monthly_cost = total_size * 0.05

    print(f"Created {len(snapshots)} snapshots")
    print(f"Total size: {total_size} GB")
    print(f"Estimated monthly cost: ${estimated_monthly_cost:.2f}")
    print()

    for snapshot in snapshots:
        print(
            f"  {snapshot['snapshot_id']} ({snapshot['volume_name']}) - "
            f"{snapshot['volume_size']} GB"
        )
    print()
    print("Snapshots are being created in the background and will be available shortly.")


if __name__ == "__main__":
    pass
