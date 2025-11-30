"""
S3 Audit Package.
Provides comprehensive S3 bucket analysis, cost estimation, and optimization recommendations.
"""

from cost_toolkit.common.s3_utils import get_bucket_region
from .bucket_analysis import analyze_bucket_objects
from .cli import audit_s3_comprehensive
from .recommendations import generate_optimization_recommendations
from .reporting import (
    display_bucket_summary,
    print_cleanup_opportunities,
    print_optimization_recommendations,
    print_overall_summary,
    print_storage_class_breakdown,
)
from .utils import calculate_monthly_cost

__all__ = [
    "analyze_bucket_objects",
    "get_bucket_region",
    "audit_s3_comprehensive",
    "generate_optimization_recommendations",
    "display_bucket_summary",
    "print_cleanup_opportunities",
    "print_optimization_recommendations",
    "print_overall_summary",
    "print_storage_class_breakdown",
    "calculate_monthly_cost",
]
