#!/usr/bin/env python3
"""
AWS Lambda Cleanup Script
Deletes all Lambda functions across regions to eliminate costs.
"""

import os
import time

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def delete_lambda_functions():
    """Delete all Lambda functions across regions"""
    setup_aws_credentials()

    # Regions where Lambda functions were detected
    regions = ["us-east-1", "us-east-2", "us-west-2"]

    total_deleted = 0

    for region in regions:
        print(f"\n=== Checking Lambda functions in {region} ===")

        try:
            lambda_client = boto3.client("lambda", region_name=region)

            # List all functions in this region
            response = lambda_client.list_functions()
            functions = response["Functions"]

            if not functions:
                print(f"No Lambda functions found in {region}")
                continue

            print(f"Found {len(functions)} Lambda functions in {region}")

            for function in functions:
                function_name = function["FunctionName"]
                print(f"Deleting Lambda function: {function_name}")

                try:
                    lambda_client.delete_function(FunctionName=function_name)
                    print(f"✅ Successfully deleted: {function_name}")
                    total_deleted += 1
                    time.sleep(1)  # Small delay to avoid rate limiting

                except Exception as e:
                    print(f"❌ Failed to delete {function_name}: {str(e)}")

        except Exception as e:
            print(f"❌ Error accessing Lambda in {region}: {str(e)}")

    print(f"\n=== Lambda Cleanup Summary ===")
    print(f"Total Lambda functions deleted: {total_deleted}")

    if total_deleted > 0:
        print("✅ Lambda cleanup completed successfully!")
        print("💰 This should eliminate Lambda compute and storage costs.")
    else:
        print("ℹ️ No Lambda functions were deleted.")


if __name__ == "__main__":
    print("AWS Lambda Cleanup Script")
    print("=" * 50)
    delete_lambda_functions()
