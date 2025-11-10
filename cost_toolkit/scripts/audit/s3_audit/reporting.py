"""
Report generation and output functions for S3 audit.
Handles displaying analysis results and recommendations.
"""

from datetime import datetime, timezone

from .constants import DAYS_THRESHOLD_VERY_OLD
from .utils import calculate_monthly_cost, format_bytes


def _print_bucket_storage_classes(storage_classes):
    """Print storage class breakdown for a bucket"""
    if not storage_classes:
        return

    print("  Storage classes:")
    for storage_class, data in storage_classes.items():
        class_cost = calculate_monthly_cost(data["size_bytes"], storage_class)
        print(
            f"    {storage_class}: {data['count']:,} objects, "
            f"{format_bytes(data['size_bytes'])}, ${class_cost:.2f}/month"
        )


def _print_bucket_age_info(bucket_analysis):
    """Print object age information for a bucket"""
    if not bucket_analysis["last_modified_oldest"] or not bucket_analysis["last_modified_newest"]:
        return

    oldest_age = (datetime.now(timezone.utc) - bucket_analysis["last_modified_oldest"]).days
    newest_age = (datetime.now(timezone.utc) - bucket_analysis["last_modified_newest"]).days
    print(f"  Object age range: {newest_age} to {oldest_age} days")


def _print_bucket_optimization_opportunities(bucket_analysis):
    """Print optimization opportunities for a bucket"""
    if bucket_analysis["old_objects"]:
        old_size = sum(obj["size_bytes"] for obj in bucket_analysis["old_objects"])
        print(
            f"  Old objects (>90 days): {len(bucket_analysis['old_objects'])} objects, "
            f"{format_bytes(old_size)}"
        )

    if bucket_analysis["large_objects"]:
        large_size = sum(obj["size_bytes"] for obj in bucket_analysis["large_objects"])
        print(
            f"  Large objects (>100MB): {len(bucket_analysis['large_objects'])} objects, "
            f"{format_bytes(large_size)}"
        )


def display_bucket_summary(bucket_analysis, bucket_cost):
    """Display summary information for a single bucket"""
    print(f"  Objects: {bucket_analysis['total_objects']:,}")
    print(f"  Total size: {format_bytes(bucket_analysis['total_size_bytes'])}")
    print(f"  Estimated monthly cost: ${bucket_cost:.2f}")
    print(f"  Versioning: {'Enabled' if bucket_analysis['versioning_enabled'] else 'Disabled'}")
    print(f"  Lifecycle policies: {len(bucket_analysis['lifecycle_policy'])} configured")
    print(f"  Encryption: {'Configured' if bucket_analysis['encryption'] else 'Not configured'}")
    print(f"  Public access: {'Possible' if bucket_analysis['public_access'] else 'Blocked'}")

    _print_bucket_storage_classes(bucket_analysis["storage_classes"])
    _print_bucket_age_info(bucket_analysis)
    _print_bucket_optimization_opportunities(bucket_analysis)


def print_overall_summary(all_bucket_analyses, total_objects, total_size_bytes, total_monthly_cost):
    """Print overall S3 audit summary"""
    print("=" * 80)
    print("🎯 OVERALL S3 SUMMARY")
    print("=" * 80)
    print(f"Total buckets analyzed: {len(all_bucket_analyses)}")
    print(f"Total objects: {total_objects:,}")
    print(f"Total storage size: {format_bytes(total_size_bytes)}")
    print(f"Estimated monthly cost: ${total_monthly_cost:.2f}")
    print()


def print_storage_class_breakdown(storage_class_summary, total_size_bytes):
    """Print storage class breakdown summary"""
    if not storage_class_summary:
        return

    print("📊 Storage Class Breakdown:")
    print("-" * 40)
    for storage_class, data in sorted(
        storage_class_summary.items(), key=lambda x: x[1]["cost"], reverse=True
    ):
        percentage = (data["size_bytes"] / total_size_bytes * 100) if total_size_bytes > 0 else 0
        print(f"  {storage_class}:")
        print(f"    Objects: {data['count']:,}")
        print(f"    Size: {format_bytes(data['size_bytes'])} ({percentage:.1f}%)")
        print(f"    Cost: ${data['cost']:.2f}/month")
        print()


def print_optimization_recommendations(all_recommendations):
    """Print optimization recommendations for all buckets"""
    if not all_recommendations:
        print("✅ No immediate optimization opportunities found")
        return

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


def _collect_cleanup_candidates(all_bucket_analyses):
    """Collect cleanup candidates from bucket analyses"""
    cleanup_candidates = []
    for analysis in all_bucket_analyses:
        very_old_objects = [
            obj for obj in analysis["old_objects"] if obj["age_days"] > DAYS_THRESHOLD_VERY_OLD
        ]
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
    return cleanup_candidates


def print_cleanup_opportunities(all_bucket_analyses):
    """Print cleanup opportunities for very old objects"""
    print("\n" + "=" * 80)
    print("🗑️  CLEANUP OPPORTUNITIES")
    print("=" * 80)

    cleanup_candidates = _collect_cleanup_candidates(all_bucket_analyses)

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
            f"Total cleanup potential: {format_bytes(total_cleanup_size)}, "
            f"${total_cleanup_cost:.2f}/month savings"
        )
    else:
        print("No obvious cleanup candidates found (no objects older than 1 year)")
