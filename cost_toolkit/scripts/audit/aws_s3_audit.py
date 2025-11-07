#!/usr/bin/env python3
"""
AWS S3 Comprehensive Audit Script
Analyzes S3 buckets, objects, storage classes, costs, and optimization opportunities.
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aws_utils import setup_aws_credentials

# S3 storage class pricing per GB/month (US East 1 rates as baseline)
STORAGE_CLASS_PRICING = {
    "STANDARD": 0.023,
    "REDUCED_REDUNDANCY": 0.024,
    "STANDARD_IA": 0.0125,
    "ONEZONE_IA": 0.01,
    "GLACIER": 0.004,
    "DEEP_ARCHIVE": 0.00099,
    "GLACIER_IR": 0.004,
    "INTELLIGENT_TIERING": 0.0125,
    "OUTPOSTS": 0.068,
}

# Request pricing per 1000 requests
REQUEST_PRICING = {
    "PUT_COPY_POST_LIST": 0.0005,  # PUT, COPY, POST, LIST requests per 1000
    "GET_SELECT": 0.0004,  # GET, SELECT requests per 1000
    "LIFECYCLE_TRANSITION": 0.01,  # Lifecycle transition requests per 1000
    "DATA_RETRIEVAL_GLACIER": 0.01,  # Glacier retrieval per 1000
    "DATA_RETRIEVAL_DEEP_ARCHIVE": 0.02,  # Deep Archive retrieval per 1000
}


def get_all_regions():
    """Get all available AWS regions that support S3"""
    try:
        ec2 = boto3.client("ec2", region_name="us-east-1")
        response = ec2.describe_regions()
        return [region["RegionName"] for region in response["Regions"]]
    except Exception as e:
        print(f"Error getting regions: {e}")
        # Fallback to common regions
        return [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-central-1",
            "eu-north-1",
            "ap-southeast-1",
            "ap-southeast-2",
            "ap-northeast-1",
        ]


def get_bucket_region(bucket_name):
    """Get the region where a bucket is located"""
    try:
        s3_client = boto3.client("s3")
        response = s3_client.get_bucket_location(Bucket=bucket_name)
        region = response.get("LocationConstraint")
        # us-east-1 returns None for LocationConstraint
        return region if region else "us-east-1"
    except Exception as e:
        print(f"Error getting region for bucket {bucket_name}: {e}")
        return "us-east-1"


def analyze_bucket_objects(bucket_name, region):
    """Analyze all objects in a bucket for storage classes, sizes, and counts"""
    try:
        s3_client = boto3.client("s3", region_name=region)

        bucket_analysis = {
            "bucket_name": bucket_name,
            "region": region,
            "total_objects": 0,
            "total_size_bytes": 0,
            "storage_classes": defaultdict(lambda: {"count": 0, "size_bytes": 0}),
            "last_modified_oldest": None,
            "last_modified_newest": None,
            "large_objects": [],  # Objects > 100MB
            "old_objects": [],  # Objects > 90 days old
            "versioning_enabled": False,
            "lifecycle_policy": None,
            "encryption": None,
            "public_access": False,
        }

        # Check bucket versioning
        try:
            versioning_response = s3_client.get_bucket_versioning(Bucket=bucket_name)
            bucket_analysis["versioning_enabled"] = versioning_response.get("Status") == "Enabled"
        except ClientError:
            pass

        # Check lifecycle policy
        try:
            lifecycle_response = s3_client.get_bucket_lifecycle_configuration(Bucket=bucket_name)
            bucket_analysis["lifecycle_policy"] = lifecycle_response.get("Rules", [])
        except ClientError:
            bucket_analysis["lifecycle_policy"] = []

        # Check encryption
        try:
            encryption_response = s3_client.get_bucket_encryption(Bucket=bucket_name)
            bucket_analysis["encryption"] = encryption_response.get(
                "ServerSideEncryptionConfiguration"
            )
        except ClientError:
            pass

        # Check public access
        try:
            public_access_response = s3_client.get_public_access_block(Bucket=bucket_name)
            pab = public_access_response.get("PublicAccessBlockConfiguration", {})
            # If any of these are False, bucket might have public access
            bucket_analysis["public_access"] = not all(
                [
                    pab.get("BlockPublicAcls", True),
                    pab.get("IgnorePublicAcls", True),
                    pab.get("BlockPublicPolicy", True),
                    pab.get("RestrictPublicBuckets", True),
                ]
            )
        except ClientError:
            # If we can't get public access block, assume it might be public
            bucket_analysis["public_access"] = True

        # Paginate through all objects
        paginator = s3_client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=bucket_name)

        ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
        large_object_threshold = 100 * 1024 * 1024  # 100MB in bytes

        for page in page_iterator:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                bucket_analysis["total_objects"] += 1
                size = obj["Size"]
                bucket_analysis["total_size_bytes"] += size

                # Determine storage class (default to STANDARD if not specified)
                storage_class = obj.get("StorageClass", "STANDARD")
                bucket_analysis["storage_classes"][storage_class]["count"] += 1
                bucket_analysis["storage_classes"][storage_class]["size_bytes"] += size

                # Track oldest and newest objects
                last_modified = obj["LastModified"]
                if (
                    not bucket_analysis["last_modified_oldest"]
                    or last_modified < bucket_analysis["last_modified_oldest"]
                ):
                    bucket_analysis["last_modified_oldest"] = last_modified
                if (
                    not bucket_analysis["last_modified_newest"]
                    or last_modified > bucket_analysis["last_modified_newest"]
                ):
                    bucket_analysis["last_modified_newest"] = last_modified

                # Track large objects (potential for optimization)
                if size > large_object_threshold:
                    bucket_analysis["large_objects"].append(
                        {
                            "key": obj["Key"],
                            "size_bytes": size,
                            "storage_class": storage_class,
                            "last_modified": last_modified,
                        }
                    )

                # Track old objects (potential for archival)
                if last_modified < ninety_days_ago:
                    bucket_analysis["old_objects"].append(
                        {
                            "key": obj["Key"],
                            "size_bytes": size,
                            "storage_class": storage_class,
                            "last_modified": last_modified,
                            "age_days": (datetime.now(timezone.utc) - last_modified).days,
                        }
                    )

        return bucket_analysis

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchBucket":
            print(f"⚠️  Bucket {bucket_name} does not exist")
        elif error_code == "AccessDenied":
            print(f"⚠️  Access denied to bucket {bucket_name}")
        else:
            print(f"⚠️  Error analyzing bucket {bucket_name}: {e}")
        return None
    except Exception as e:
        print(f"⚠️  Unexpected error analyzing bucket {bucket_name}: {e}")
        return None


def calculate_monthly_cost(size_bytes, storage_class):
    """Calculate estimated monthly cost for given size and storage class"""
    size_gb = size_bytes / (1024**3)  # Convert bytes to GB
    price_per_gb = STORAGE_CLASS_PRICING.get(storage_class, STORAGE_CLASS_PRICING["STANDARD"])
    return size_gb * price_per_gb


def format_bytes(bytes_value):
    """Format bytes into human readable format"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def generate_optimization_recommendations(bucket_analysis):
    """Generate specific optimization recommendations for a bucket"""
    recommendations = []

    # Check for objects that could be moved to cheaper storage classes
    standard_objects = bucket_analysis["storage_classes"].get(
        "STANDARD", {"count": 0, "size_bytes": 0}
    )
    if standard_objects["size_bytes"] > 0:
        # Objects older than 30 days could move to IA
        old_standard_objects = [
            obj
            for obj in bucket_analysis["old_objects"]
            if obj["storage_class"] == "STANDARD" and obj["age_days"] > 30
        ]
        if old_standard_objects:
            old_size = sum(obj["size_bytes"] for obj in old_standard_objects)
            current_cost = calculate_monthly_cost(old_size, "STANDARD")
            ia_cost = calculate_monthly_cost(old_size, "STANDARD_IA")
            savings = current_cost - ia_cost
            recommendations.append(
                {
                    "type": "storage_class_optimization",
                    "description": f"Move {len(old_standard_objects)} objects ({format_bytes(old_size)}) older than 30 days to Standard-IA",
                    "potential_savings": savings,
                    "action": "Create lifecycle policy to transition to Standard-IA after 30 days",
                }
            )

        # Objects older than 90 days could move to Glacier
        very_old_objects = [
            obj
            for obj in bucket_analysis["old_objects"]
            if obj["storage_class"] in ["STANDARD", "STANDARD_IA"] and obj["age_days"] > 90
        ]
        if very_old_objects:
            old_size = sum(obj["size_bytes"] for obj in very_old_objects)
            current_cost = calculate_monthly_cost(old_size, "STANDARD")
            glacier_cost = calculate_monthly_cost(old_size, "GLACIER")
            savings = current_cost - glacier_cost
            recommendations.append(
                {
                    "type": "archival_optimization",
                    "description": f"Archive {len(very_old_objects)} objects ({format_bytes(old_size)}) older than 90 days to Glacier",
                    "potential_savings": savings,
                    "action": "Create lifecycle policy to transition to Glacier after 90 days",
                }
            )

    # Check for lifecycle policy
    if not bucket_analysis["lifecycle_policy"]:
        recommendations.append(
            {
                "type": "lifecycle_policy",
                "description": "No lifecycle policy configured",
                "potential_savings": 0,
                "action": "Consider implementing lifecycle policies for automatic cost optimization",
            }
        )

    # Check for versioning without lifecycle
    if bucket_analysis["versioning_enabled"] and not bucket_analysis["lifecycle_policy"]:
        recommendations.append(
            {
                "type": "versioning_optimization",
                "description": "Versioning enabled but no lifecycle policy for old versions",
                "potential_savings": 0,
                "action": "Configure lifecycle policy to delete or archive old object versions",
            }
        )

    # Check for large objects that might benefit from multipart upload optimization
    large_objects = bucket_analysis["large_objects"]
    if large_objects:
        total_large_size = sum(obj["size_bytes"] for obj in large_objects)
        recommendations.append(
            {
                "type": "large_object_optimization",
                "description": f"{len(large_objects)} large objects ({format_bytes(total_large_size)}) found",
                "potential_savings": 0,
                "action": "Consider using multipart uploads and compression for large objects",
            }
        )

    # Check for public access
    if bucket_analysis["public_access"]:
        recommendations.append(
            {
                "type": "security_optimization",
                "description": "Bucket may have public access configured",
                "potential_savings": 0,
                "action": "Review and restrict public access if not needed",
            }
        )

    return recommendations


def audit_s3_comprehensive():
    """Perform comprehensive S3 audit across all regions"""
    setup_aws_credentials()

    print("AWS S3 Comprehensive Storage Audit")
    print("=" * 80)
    print("Analyzing all S3 buckets, objects, storage classes, and costs...")
    print()

    try:
        # Get all buckets (S3 is global, but we need to check each bucket's region)
        s3_client = boto3.client("s3")
        response = s3_client.list_buckets()
        buckets = response.get("Buckets", [])

        if not buckets:
            print("✅ No S3 buckets found in your account")
            return

        print(f"🔍 Found {len(buckets)} S3 bucket(s) to analyze")
        print()

        total_objects = 0
        total_size_bytes = 0
        total_monthly_cost = 0
        all_bucket_analyses = []
        storage_class_summary = defaultdict(lambda: {"count": 0, "size_bytes": 0, "cost": 0})
        all_recommendations = []

        for bucket in buckets:
            bucket_name = bucket["Name"]
            bucket_region = get_bucket_region(bucket_name)

            print(f"📦 Analyzing bucket: {bucket_name} (region: {bucket_region})")
            print("-" * 60)

            bucket_analysis = analyze_bucket_objects(bucket_name, bucket_region)

            if bucket_analysis:
                all_bucket_analyses.append(bucket_analysis)

                # Update totals
                total_objects += bucket_analysis["total_objects"]
                total_size_bytes += bucket_analysis["total_size_bytes"]

                # Calculate costs for this bucket
                bucket_cost = 0
                for storage_class, data in bucket_analysis["storage_classes"].items():
                    class_cost = calculate_monthly_cost(data["size_bytes"], storage_class)
                    bucket_cost += class_cost
                    storage_class_summary[storage_class]["count"] += data["count"]
                    storage_class_summary[storage_class]["size_bytes"] += data["size_bytes"]
                    storage_class_summary[storage_class]["cost"] += class_cost

                total_monthly_cost += bucket_cost

                # Display bucket summary
                print(f"  Objects: {bucket_analysis['total_objects']:,}")
                print(f"  Total size: {format_bytes(bucket_analysis['total_size_bytes'])}")
                print(f"  Estimated monthly cost: ${bucket_cost:.2f}")
                print(
                    f"  Versioning: {'Enabled' if bucket_analysis['versioning_enabled'] else 'Disabled'}"
                )
                print(
                    f"  Lifecycle policies: {len(bucket_analysis['lifecycle_policy'])} configured"
                )
                print(
                    f"  Encryption: {'Configured' if bucket_analysis['encryption'] else 'Not configured'}"
                )
                print(
                    f"  Public access: {'Possible' if bucket_analysis['public_access'] else 'Blocked'}"
                )

                # Show storage class breakdown
                if bucket_analysis["storage_classes"]:
                    print("  Storage classes:")
                    for storage_class, data in bucket_analysis["storage_classes"].items():
                        class_cost = calculate_monthly_cost(data["size_bytes"], storage_class)
                        print(
                            f"    {storage_class}: {data['count']:,} objects, {format_bytes(data['size_bytes'])}, ${class_cost:.2f}/month"
                        )

                # Show age information
                if (
                    bucket_analysis["last_modified_oldest"]
                    and bucket_analysis["last_modified_newest"]
                ):
                    oldest_age = (
                        datetime.now(timezone.utc) - bucket_analysis["last_modified_oldest"]
                    ).days
                    newest_age = (
                        datetime.now(timezone.utc) - bucket_analysis["last_modified_newest"]
                    ).days
                    print(f"  Object age range: {newest_age} to {oldest_age} days")

                # Show optimization opportunities
                if bucket_analysis["old_objects"]:
                    old_size = sum(obj["size_bytes"] for obj in bucket_analysis["old_objects"])
                    print(
                        f"  Old objects (>90 days): {len(bucket_analysis['old_objects'])} objects, {format_bytes(old_size)}"
                    )

                if bucket_analysis["large_objects"]:
                    large_size = sum(obj["size_bytes"] for obj in bucket_analysis["large_objects"])
                    print(
                        f"  Large objects (>100MB): {len(bucket_analysis['large_objects'])} objects, {format_bytes(large_size)}"
                    )

                # Generate recommendations
                recommendations = generate_optimization_recommendations(bucket_analysis)
                if recommendations:
                    all_recommendations.extend([(bucket_name, rec) for rec in recommendations])

                print()
            else:
                print(f"  ⚠️  Could not analyze bucket {bucket_name}")
                print()

        # Overall summary
        print("=" * 80)
        print("🎯 OVERALL S3 SUMMARY")
        print("=" * 80)
        print(f"Total buckets analyzed: {len(all_bucket_analyses)}")
        print(f"Total objects: {total_objects:,}")
        print(f"Total storage size: {format_bytes(total_size_bytes)}")
        print(f"Estimated monthly cost: ${total_monthly_cost:.2f}")
        print()

        # Storage class breakdown
        if storage_class_summary:
            print("📊 Storage Class Breakdown:")
            print("-" * 40)
            for storage_class, data in sorted(
                storage_class_summary.items(), key=lambda x: x[1]["cost"], reverse=True
            ):
                percentage = (
                    (data["size_bytes"] / total_size_bytes * 100) if total_size_bytes > 0 else 0
                )
                print(f"  {storage_class}:")
                print(f"    Objects: {data['count']:,}")
                print(f"    Size: {format_bytes(data['size_bytes'])} ({percentage:.1f}%)")
                print(f"    Cost: ${data['cost']:.2f}/month")
                print()

        # Optimization recommendations
        if all_recommendations:
            print("💡 OPTIMIZATION RECOMMENDATIONS:")
            print("-" * 40)
            total_potential_savings = 0

            for bucket_name, rec in all_recommendations:
                print(f"📦 {bucket_name}:")
                print(f"  {rec['description']}")
                print(f"  Action: {rec['action']}")
                if rec["potential_savings"] > 0:
                    print(f"  Potential savings: ${rec['potential_savings']:.2f}/month")
                    total_potential_savings += rec["potential_savings"]
                print()

            if total_potential_savings > 0:
                print(f"🎯 Total potential monthly savings: ${total_potential_savings:.2f}")
                print(f"🎯 Annual potential savings: ${total_potential_savings * 12:.2f}")
        else:
            print("✅ No immediate optimization opportunities found")

        # Files you can potentially get rid of
        print("\n" + "=" * 80)
        print("🗑️  CLEANUP OPPORTUNITIES")
        print("=" * 80)

        cleanup_candidates = []
        for analysis in all_bucket_analyses:
            # Very old objects that haven't been accessed
            very_old_objects = [obj for obj in analysis["old_objects"] if obj["age_days"] > 365]
            if very_old_objects:
                cleanup_size = sum(obj["size_bytes"] for obj in very_old_objects)
                cleanup_cost = sum(
                    calculate_monthly_cost(obj["size_bytes"], obj["storage_class"])
                    for obj in very_old_objects
                )
                cleanup_candidates.append(
                    {
                        "bucket": analysis["bucket_name"],
                        "type": "very_old_objects",
                        "count": len(very_old_objects),
                        "size": cleanup_size,
                        "monthly_cost": cleanup_cost,
                        "description": f"Objects older than 1 year in {analysis['bucket_name']}",
                    }
                )

        if cleanup_candidates:
            total_cleanup_size = sum(c["size"] for c in cleanup_candidates)
            total_cleanup_cost = sum(c["monthly_cost"] for c in cleanup_candidates)

            print(f"Found {len(cleanup_candidates)} cleanup opportunities:")
            for candidate in cleanup_candidates:
                print(f"  • {candidate['description']}")
                print(f"    {candidate['count']} objects, {format_bytes(candidate['size'])}")
                print(f"    Potential savings: ${candidate['monthly_cost']:.2f}/month")
                print()

            print(
                f"Total cleanup potential: {format_bytes(total_cleanup_size)}, ${total_cleanup_cost:.2f}/month savings"
            )
        else:
            print("No obvious cleanup candidates found (no objects older than 1 year)")

    except NoCredentialsError:
        print("❌ AWS credentials not found. Please configure your credentials.")
    except ClientError as e:
        print(f"❌ AWS API error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    audit_s3_comprehensive()
