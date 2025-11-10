"""CLI interface for robust snapshot export"""

import argparse

from .export_ops import (
    EBS_SNAPSHOT_COST_PER_GB_MONTHLY,
    S3_STANDARD_COST_PER_GB_MONTHLY,
    export_snapshot_with_retries,
    load_aws_credentials,
)
from .monitoring import print_summary


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Export EBS snapshots to S3 with robust error handling and retries"
    )
    _ = parser.parse_args()

    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    snapshots = [
        {
            "snapshot_id": "snap-036eee4a7c291fd26",
            "region": "us-east-2",
            "size_gb": 8,
            "description": "Copied for DestinationAmi ami-05d0a30507ebee9d6",
        },
        {
            "snapshot_id": "snap-046b7eace8694913b",
            "region": "eu-west-2",
            "size_gb": 64,
            "description": "EBS snapshot for cost optimization",
        },
        {
            "snapshot_id": "snap-0f68820355c25e73e",
            "region": "eu-west-2",
            "size_gb": 384,
            "description": "Large EBS snapshot for cost optimization",
        },
    ]

    print("AWS EBS Snapshot to S3 Export Script - ROBUST VERSION")
    print("=" * 80)
    print("This version includes:")
    print("- Retry logic for failed exports")
    print("- Better AMI compatibility settings")
    print("- Improved completion detection")
    print("- Longer wait times for AWS processing")
    print()

    total_size_gb = sum(snap["size_gb"] for snap in snapshots)
    total_monthly_savings = total_size_gb * (
        EBS_SNAPSHOT_COST_PER_GB_MONTHLY - S3_STANDARD_COST_PER_GB_MONTHLY
    )

    print(f"🎯 Target: {len(snapshots)} snapshots ({total_size_gb} GB total)")
    print(f"💰 Potential monthly savings: ${total_monthly_savings:.2f}")
    print()

    confirmation = input("Type 'EXPORT' to proceed: ")
    if confirmation != "EXPORT":
        print("Operation cancelled")
        return

    results = []
    for snapshot in snapshots:
        result = export_snapshot_with_retries(snapshot, aws_access_key_id, aws_secret_access_key)
        results.append(result)

    print_summary(results)


if __name__ == "__main__":
    main()
