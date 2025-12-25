"""
Main entry point for S3 audit CLI.
Orchestrates bucket analysis and report generation.
"""

from collections import defaultdict

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from cost_toolkit.common.s3_utils import get_bucket_region
from cost_toolkit.scripts.aws_utils import setup_aws_credentials

from .bucket_analysis import analyze_bucket_objects
from .recommendations import generate_optimization_recommendations
from .reporting import (
    display_bucket_summary,
    print_cleanup_opportunities,
    print_optimization_recommendations,
    print_overall_summary,
    print_storage_class_breakdown,
)
from .utils import calculate_monthly_cost


def _process_single_bucket(bucket_name, bucket_region, storage_class_summary):
    """Process and display analysis for a single bucket"""
    print(f"📦 Analyzing bucket: {bucket_name} (region: {bucket_region})")
    print("-" * 60)

    bucket_analysis = analyze_bucket_objects(bucket_name, bucket_region)

    if not bucket_analysis:
        print(f"  ⚠️  Could not analyze bucket {bucket_name}")
        print()
        return None, 0, 0, 0, []

    # Calculate costs for this bucket
    bucket_cost = 0
    for storage_class, data in bucket_analysis["storage_classes"].items():
        class_cost = calculate_monthly_cost(data["size_bytes"], storage_class)
        bucket_cost += class_cost
        storage_class_summary[storage_class]["count"] += data["count"]
        storage_class_summary[storage_class]["size_bytes"] += data["size_bytes"]
        storage_class_summary[storage_class]["cost"] += class_cost

    # Display bucket summary
    display_bucket_summary(bucket_analysis, bucket_cost)

    # Generate recommendations
    recommendations = generate_optimization_recommendations(bucket_analysis)
    bucket_recommendations = []
    if recommendations:
        bucket_recommendations = [(bucket_name, rec) for rec in recommendations]

    print()

    return (
        bucket_analysis,
        bucket_analysis["total_objects"],
        bucket_analysis["total_size_bytes"],
        bucket_cost,
        bucket_recommendations,
    )


def _process_all_buckets(buckets):
    """Process all S3 buckets and return aggregated results."""
    total_objects = 0
    total_size_bytes = 0
    total_monthly_cost = 0
    all_bucket_analyses = []
    storage_class_summary = defaultdict(lambda: {"count": 0, "size_bytes": 0, "cost": 0})
    all_recommendations = []

    for bucket in buckets:
        bucket_name = bucket["Name"]
        bucket_region = get_bucket_region(bucket_name)

        (
            bucket_analysis,
            bucket_objects,
            bucket_size,
            bucket_cost,
            bucket_recs,
        ) = _process_single_bucket(bucket_name, bucket_region, storage_class_summary)

        if bucket_analysis:
            all_bucket_analyses.append(bucket_analysis)
            total_objects += bucket_objects
            total_size_bytes += bucket_size
            total_monthly_cost += bucket_cost
            all_recommendations.extend(bucket_recs)

    return (
        all_bucket_analyses,
        storage_class_summary,
        all_recommendations,
        total_objects,
        total_size_bytes,
        total_monthly_cost,
    )


def audit_s3_comprehensive():
    """Perform comprehensive S3 audit across all regions"""
    setup_aws_credentials()

    print("AWS S3 Comprehensive Storage Audit")
    print("=" * 80)
    print("Analyzing all S3 buckets, objects, storage classes, and costs...")
    print()

    try:
        response = boto3.client("s3").list_buckets()
        buckets = []
        if "Buckets" in response:
            buckets = response["Buckets"]

        if not buckets:
            print("✅ No S3 buckets found in your account")
            return

        print(f"🔍 Found {len(buckets)} S3 bucket(s) to analyze")
        print()

        (
            all_bucket_analyses,
            storage_class_summary,
            all_recommendations,
            total_objects,
            total_size_bytes,
            total_monthly_cost,
        ) = _process_all_buckets(buckets)

        # Print overall summary and recommendations
        print_overall_summary(all_bucket_analyses, total_objects, total_size_bytes, total_monthly_cost)
        print_storage_class_breakdown(storage_class_summary, total_size_bytes)
        print_optimization_recommendations(all_recommendations)
        print_cleanup_opportunities(all_bucket_analyses)

    except NoCredentialsError:
        print("❌ AWS credentials not found. Please configure your credentials.")
    except ClientError as e:
        print(f"❌ AWS API error: {e}")


if __name__ == "__main__":
    pass
