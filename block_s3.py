#!/usr/bin/env python3
"""
Generate restrictive S3 bucket policies for specified buckets.

Usage:
    python block_s3.py [bucket1 bucket2 ...]  # Generate policies for specific buckets
    python block_s3.py --all                   # Generate policies for all buckets
    python block_s3.py                         # Interactive mode
"""
import sys
import os
import argparse
from aws_utils import (
    get_aws_identity,
    list_s3_buckets,
    generate_restrictive_bucket_policy,
    save_policy_to_file
)


def main():
    parser = argparse.ArgumentParser(
        description="Generate restrictive S3 bucket policies"
    )
    parser.add_argument(
        "buckets",
        nargs="*",
        help="Bucket names to generate policies for"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate policies for all buckets in the account"
    )

    args = parser.parse_args()

    # Get AWS identity
    identity = get_aws_identity()
    user_arn = identity["user_arn"]

    # Determine which buckets to process
    if args.all:
        buckets = list_s3_buckets()
        print(f"Generating policies for all {len(buckets)} buckets...")
    elif args.buckets:
        buckets = args.buckets
        print(f"Generating policies for {len(buckets)} specified bucket(s)...")
    else:
        # Interactive mode
        print("No buckets specified. Available options:")
        print("  - Run with bucket names: python block_s3.py bucket1 bucket2")
        print("  - Run with --all flag: python block_s3.py --all")
        print("\nAvailable buckets:")
        available_buckets = list_s3_buckets()
        for bucket in available_buckets:
            print(f"  - {bucket}")
        sys.exit(0)

    # Ensure policies directory exists
    os.makedirs("policies", exist_ok=True)

    # Generate and save policies
    for bucket in buckets:
        policy = generate_restrictive_bucket_policy(user_arn, bucket)
        filename = os.path.join("policies", f"{bucket}_policy.json")
        save_policy_to_file(policy, filename)
        print(f"✓ Saved {filename}")

    print(f"\nSuccessfully generated {len(buckets)} policy file(s)")


if __name__ == "__main__":
    main()
