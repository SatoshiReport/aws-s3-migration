#!/usr/bin/env python3
"""
Apply bucket policies to S3 buckets.

Usage:
    python apply_block.py bucket1 [bucket2 ...]  # Apply policies to specific buckets
    python apply_block.py --all                   # Apply policies to all buckets with policy files
"""
import sys
import os
import argparse
from aws_utils import load_policy_from_file, apply_bucket_policy, list_s3_buckets


def get_buckets_with_policy_files():
    """
    Get list of buckets that have corresponding policy files.

    Returns:
        list: Bucket names that have policy files
    """
    policies_dir = 'policies'
    if not os.path.exists(policies_dir):
        return []
    policy_files = [f for f in os.listdir(policies_dir) if f.endswith('_policy.json')]
    return [f.replace('_policy.json', '') for f in policy_files]


def main():
    parser = argparse.ArgumentParser(
        description="Apply S3 bucket policies to specified buckets"
    )
    parser.add_argument(
        "buckets",
        nargs="*",
        help="Bucket names to apply policies to"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Apply all available policy files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be applied without making changes"
    )

    args = parser.parse_args()

    # Determine which buckets to process
    if args.all:
        buckets = get_buckets_with_policy_files()
        if not buckets:
            print("No policy files found (looking for *_policy.json)")
            sys.exit(1)
        print(f"Found {len(buckets)} policy file(s)")
    elif args.buckets:
        buckets = args.buckets
    else:
        # Interactive mode
        print("No buckets specified. Available options:")
        print("  - Run with bucket names: python apply_block.py bucket1 bucket2")
        print("  - Run with --all flag: python apply_block.py --all")
        print("\nAvailable policy files:")
        available = get_buckets_with_policy_files()
        if available:
            for bucket in available:
                print(f"  - {bucket}")
        else:
            print("  (none found)")
        sys.exit(0)

    # Apply policies
    for bucket in buckets:
        policy_file = os.path.join("policies", f"{bucket}_policy.json")

        if not os.path.exists(policy_file):
            print(f"✗ Policy file not found: {policy_file}")
            continue

        try:
            policy_json = load_policy_from_file(policy_file)

            if args.dry_run:
                print(f"[DRY RUN] Would apply {policy_file} to {bucket}")
            else:
                apply_bucket_policy(bucket, policy_json)
                print(f"✓ Applied policy to {bucket}")
        except Exception as e:
            print(f"✗ Failed to apply policy to {bucket}: {str(e)}")

    if args.dry_run:
        print("\nDry run completed. No changes were made.")
    else:
        print(f"\nCompleted applying policies to {len(buckets)} bucket(s)")


if __name__ == "__main__":
    main()
