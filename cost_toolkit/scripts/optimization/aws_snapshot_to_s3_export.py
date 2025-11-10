#!/usr/bin/env python3
"""
AWS EBS Snapshot to S3 Export Script
Exports EBS snapshots to S3 for significant cost savings.

This is a thin wrapper around the snapshot_export package.
"""

from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.snapshot_export.cli import export_snapshots_to_s3

if __name__ == "__main__":
    import argparse
    import sys

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
