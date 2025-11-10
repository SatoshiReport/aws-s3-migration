#!/usr/bin/env python3
"""
AWS EBS Snapshot to S3 Export Script - Robust Version
This version implements workarounds for AWS export service issues with retry logic.

This is a thin wrapper around the snapshot_export_robust package.
"""

from cost_toolkit.scripts.optimization.snapshot_export_robust import main

if __name__ == "__main__":
    main()
