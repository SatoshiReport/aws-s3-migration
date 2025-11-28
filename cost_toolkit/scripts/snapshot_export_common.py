"""
Shared utilities for snapshot export operations.

This module provides common patterns for snapshot export scripts
to eliminate code duplication. AWS-facing helpers live in
cost_toolkit.scripts.optimization.snapshot_export_common to keep the
operational logic canonical and avoid drift between similarly named modules.
"""


def print_export_summary(snapshots_to_export, total_savings):
    """
    Print a formatted summary of snapshots to be exported and cost savings.

    Args:
        snapshots_to_export: List of snapshot dictionaries with size_gb field
        total_savings: Dictionary with cost breakdown (ebs_cost, s3_cost, etc.)
    """
    print()

    total_size_gb = sum(snap["size_gb"] for snap in snapshots_to_export)

    print(f"🎯 Target: {len(snapshots_to_export)} snapshots ({total_size_gb} GB total)")
    print(f"💰 Current monthly cost: ${total_savings['ebs_cost']:.2f}")
    print(f"💰 Future monthly cost: ${total_savings['s3_cost']:.2f}")
    print(
        f"💰 Monthly savings: ${total_savings['monthly_savings']:.2f} "
        f"({total_savings['savings_percentage']:.1f}%)"
    )
    print(f"💰 Annual savings: ${total_savings['annual_savings']:.2f}")
    print()


def print_export_results(export_results):
    """
    Print a formatted summary of completed export results.

    Args:
        export_results: List of export result dictionaries with monthly_savings,
                       snapshot_id, bucket_name, and s3_key fields
    """
    total_monthly_savings = sum(result["monthly_savings"] for result in export_results)
    print(f"💰 Total monthly savings: ${total_monthly_savings:.2f}")
    print(f"💰 Total annual savings: ${total_monthly_savings * 12:.2f}")
    print()

    print("📋 Export Results:")
    for result in export_results:
        print(f"   {result['snapshot_id']} → s3://{result['bucket_name']}/{result['s3_key']}")

    print()
    print("📝 Next Steps:")
    print("1. Verify exports in S3 console")
    print("2. Test restore process if needed")
    print("3. Delete original snapshots to realize savings")


# Sample snapshot data used across multiple export scripts
SAMPLE_SNAPSHOTS = [
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


if __name__ == "__main__":
    raise SystemExit(
        "This module is library-only. Import cost_toolkit.scripts.snapshot_export_common instead."
    )
