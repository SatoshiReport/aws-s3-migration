"""
AWS EBS Volume Manager CLI Module
Handles command-line argument parsing and execution.
"""

import sys
from typing import Dict, List

from cost_toolkit.scripts.aws_utils import setup_aws_credentials

from .operations import delete_ebs_volume, get_volume_detailed_info
from .reporting import print_snapshot_summary, print_volume_detailed_report
from .snapshot import create_volume_snapshot

# Command-line argument count constants
MIN_ARGS_FOR_COMMAND = 2
MIN_ARGS_WITH_VOLUME_ID = 3


def print_usage() -> None:
    """Print usage information for the script."""
    print("AWS EBS Volume Manager")
    print("=" * 50)
    print("Usage:")
    print("  Delete volume:     python aws_ebs_volume_manager.py delete <volume-id>")
    print("  Get volume info:   python aws_ebs_volume_manager.py info <volume-id> [volume-id2] ...")
    print(
        "  Create snapshot:   python aws_ebs_volume_manager.py snapshot "
        "<volume-id> [volume-id2] ..."
    )
    print("  Force delete:      python aws_ebs_volume_manager.py delete <volume-id> --force")
    print()
    print("Examples:")
    print("  python aws_ebs_volume_manager.py delete vol-01b1dadf1397de37c")
    print("  python aws_ebs_volume_manager.py info vol-089b9ed38099c68f3 vol-0249308257e5fa64d")
    print("  python aws_ebs_volume_manager.py snapshot vol-089b9ed38099c68f3 vol-0249308257e5fa64d")


def handle_delete_command() -> None:
    """Handle the delete volume command."""
    if len(sys.argv) < MIN_ARGS_WITH_VOLUME_ID:
        print("Volume ID required for delete command")
        sys.exit(1)

    volume_id = sys.argv[2]
    force = "--force" in sys.argv

    print("AWS EBS Volume Deletion")
    print("=" * 50)
    success = delete_ebs_volume(volume_id, force)
    sys.exit(0 if success else 1)


def handle_info_command() -> None:
    """Handle the volume info command."""
    if len(sys.argv) < MIN_ARGS_WITH_VOLUME_ID:
        print("At least one volume ID required for info command")
        sys.exit(1)

    volume_ids = sys.argv[2:]

    print("AWS EBS Volume Detailed Information")
    print("=" * 50)

    for volume_id in volume_ids:
        try:
            volume_info = get_volume_detailed_info(volume_id)
            print_volume_detailed_report(volume_info)
        except (OSError, ValueError) as e:
            print(f"Error getting info for {volume_id}: {str(e)}")
            print()


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
            print(f"Creating snapshot for volume {volume_id}...")
            snapshot_info = create_volume_snapshot(volume_id)
            snapshots.append(snapshot_info)
            print(f"Snapshot {snapshot_info['snapshot_id']} created successfully")
            print(f"   Volume: {snapshot_info['volume_name']} ({snapshot_info['volume_size']} GB)")
            print(f"   Region: {snapshot_info['region']}")
            print()
        except (OSError, ValueError) as e:
            print(f"Error creating snapshot for {volume_id}: {str(e)}")
            print()

    return snapshots


def handle_snapshot_command() -> None:
    """Handle the snapshot creation command."""
    if len(sys.argv) < MIN_ARGS_WITH_VOLUME_ID:
        print("At least one volume ID required for snapshot command")
        sys.exit(1)

    volume_ids = sys.argv[2:]

    print("AWS EBS Volume Snapshot Creation")
    print("=" * 50)

    snapshots = create_multiple_snapshots(volume_ids)

    if snapshots:
        print_snapshot_summary(snapshots)


def main() -> None:
    """Main function to handle command line arguments and execute operations."""
    if len(sys.argv) < MIN_ARGS_FOR_COMMAND:
        print_usage()
        sys.exit(1)

    setup_aws_credentials()

    command = sys.argv[1].lower()

    if command == "delete":
        handle_delete_command()
    elif command == "info":
        handle_info_command()
    elif command == "snapshot":
        handle_snapshot_command()
    else:
        print(f"Unknown command: {command}")
        print("Valid commands: delete, info, snapshot")
        sys.exit(1)


if __name__ == "__main__":
    pass
