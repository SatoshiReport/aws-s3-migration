"""CLI interface for snapshot export"""

import argparse
import sys

from botocore.exceptions import ClientError

from .cli_helpers import _get_snapshots_to_export, process_single_snapshot_export
from .export_ops import load_aws_credentials
from .validation import calculate_cost_savings


def _print_export_intro(snapshots_to_export, total_savings):
    """Print export introduction and cost savings."""
    print("AWS EBS Snapshot to S3 Export Script")
    print("=" * 80)
    print("Exporting EBS snapshots to S3 for maximum cost savings...")
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

    print("⚠️  IMPORTANT NOTES:")
    print("   - Export process can take several hours per snapshot")
    print("   - AMIs will be created temporarily and automatically cleaned up after export")
    print("   - Data will be stored in S3 Standard for immediate access")
    print("   - Original snapshots can be deleted after successful export")
    print()


def _print_export_summary(export_results, snapshots_to_export, region):
    """Print final export summary."""
    successful_exports = len(export_results)
    failed_exports = len(snapshots_to_export) - successful_exports

    print("=" * 80)
    print("🎯 S3 EXPORT SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully exported: {successful_exports} snapshots")
    print(f"❌ Failed to export: {failed_exports} snapshots")

    if export_results:
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
        print("3. Delete original EBS snapshots to realize savings")
        print()
        print("🔧 Optional: Delete Original Snapshots (after verifying S3 exports):")
        for result in export_results:
            print(
                f"   aws ec2 delete-snapshot --snapshot-id {result['snapshot_id']} "
                f"--region {region}"
            )


def export_snapshots_to_s3(overwrite_existing=False):
    """Main function to export EBS snapshots to S3"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    snapshots_to_export = _get_snapshots_to_export()
    total_size_gb = sum(snap["size_gb"] for snap in snapshots_to_export)
    total_savings = calculate_cost_savings(total_size_gb)

    _print_export_intro(snapshots_to_export, total_savings)

    confirmation = input("Type 'EXPORT TO S3' to proceed with snapshot export: ")

    if confirmation != "EXPORT TO S3":
        print("❌ Operation cancelled by user")
        return

    print()
    print("🚨 Proceeding with snapshot export to S3...")
    print("=" * 80)

    export_results = []
    snapshots_to_export = sorted(snapshots_to_export, key=lambda x: x["size_gb"])

    print("📋 Processing snapshots in order of size (smallest first):")
    for snap in snapshots_to_export:
        print(f"   - {snap['snapshot_id']}: {snap['size_gb']} GB")
    print()

    for snap_info in snapshots_to_export:
        result, _ = process_single_snapshot_export(
            snap_info, aws_access_key_id, aws_secret_access_key, overwrite_existing
        )
        if result:
            export_results.append(result)
        print()

    region = snapshots_to_export[0]["region"] if snapshots_to_export else "unknown"
    _print_export_summary(export_results, snapshots_to_export, region)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export EBS snapshots to S3 for cost optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 aws_snapshot_to_s3_export.py                    # Normal mode - skip existing exports
  python3 aws_snapshot_to_s3_export.py --overwrite       # Overwrite existing S3 files
        """,
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing S3 exports (default: skip existing exports)",
    )

    args = parser.parse_args()

    try:
        export_snapshots_to_s3(overwrite_existing=args.overwrite)
    except ClientError as e:
        print(f"❌ Script failed: {e}")
        sys.exit(1)
