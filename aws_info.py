#!/usr/bin/env python3
"""
Display AWS account information and S3 buckets.
"""
from aws_utils import get_aws_identity, list_s3_buckets


def main():
    """Main entry point for displaying AWS account information"""
    # Get AWS identity information
    identity = get_aws_identity()

    # Get all S3 buckets
    buckets = list_s3_buckets()

    # Display information
    print(f"Account ID: {identity['account_id']}")
    print(f"Username: {identity['username']}")
    print(f"User ARN: {identity['user_arn']}")
    print(f"\nS3 Buckets ({len(buckets)}):")
    for bucket in buckets:
        print(f"  - {bucket}")


if __name__ == "__main__":
    main()
