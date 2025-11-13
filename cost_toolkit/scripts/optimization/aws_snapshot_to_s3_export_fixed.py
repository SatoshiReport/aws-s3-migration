#!/usr/bin/env python3
"""
AWS EBS Snapshot to S3 Export Script - Fixed Version
Exports EBS snapshots to S3 with fail-fast error handling.

This is a thin wrapper around the snapshot_export_fixed package.
"""

from cost_toolkit.scripts.optimization.snapshot_export_fixed.cli import (
    export_snapshots_to_s3_fixed,
)

if __name__ == "__main__":  # pragma: no cover - script entry point
    import argparse

    parser = argparse.ArgumentParser(
        description="Export EBS snapshots to S3 for cost optimization - FIXED VERSION",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 aws_snapshot_to_s3_export_fixed.py    # Export with fail-fast error handling
        """,
    )

    args = parser.parse_args()

    export_snapshots_to_s3_fixed()
