#!/usr/bin/env python3
"""
Apply bucket policies to S3 buckets.

Usage:
    python apply_block.py bucket1 [bucket2 ...]  # Apply policies to specific buckets
    python apply_block.py --all                   # Apply policies to all buckets with policy files
"""
import argparse
import os
import sys

from aws_utils import (
    apply_bucket_policy,
    load_policy_from_file,
    print_interactive_help,
)


def get_buckets_with_policy_files():
    """
    Get list of buckets that have corresponding policy files.

    Returns:
        list: Bucket names that have policy files
    """
    policies_dir = "policies"
    if not os.path.exists(policies_dir):
        return []
    policy_files = [f for f in os.listdir(policies_dir) if f.endswith("_policy.json")]
    return [f.replace("_policy.json", "") for f in policy_files]


def determine_buckets(args):
    """Determine which buckets to process based on arguments"""
    if args.all:
        buckets = get_buckets_with_policy_files()
        if not buckets:
            print("No policy files found (looking for *_policy.json)")
            raise SystemExit(1)
        print(f"Found {len(buckets)} policy file(s)")
        return buckets
    if args.buckets:
        return args.buckets
    show_interactive_help()
    raise SystemExit(1)


def show_interactive_help():
    """Show interactive mode help and available policies"""
    available = get_buckets_with_policy_files()
    print_interactive_help("apply_block.py", available, "policy files")


def apply_policy_to_bucket(bucket, dry_run):
    """Apply policy to a single bucket"""
    policy_file = os.path.join("policies", f"{bucket}_policy.json")
    if not os.path.exists(policy_file):
        print(f"✗ Policy file not found: {policy_file}")
        return False
    try:
        policy_json = load_policy_from_file(policy_file)
        if dry_run:
            print(f"[DRY RUN] Would apply {policy_file} to {bucket}")
        else:
            apply_bucket_policy(bucket, policy_json)
            print(f"✓ Applied policy to {bucket}")
    except (OSError, IOError, ValueError) as e:
        print(f"✗ Failed to apply policy to {bucket}: {str(e)}")
        return False
    return True


def main():
    """Main entry point for applying bucket policies"""
    parser = argparse.ArgumentParser(description="Apply S3 bucket policies to specified buckets")
    parser.add_argument("buckets", nargs="*", help="Bucket names to apply policies to")
    parser.add_argument("--all", action="store_true", help="Apply all available policy files")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be applied without making changes",
    )
    args = parser.parse_args()
    buckets = determine_buckets(args)
    failures = 0
    for bucket in buckets:
        if not apply_policy_to_bucket(bucket, args.dry_run):
            failures += 1
    if args.dry_run:
        print("\nDry run completed. No changes were made.")
    else:
        print(f"\nCompleted applying policies to {len(buckets)} bucket(s)")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
