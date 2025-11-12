"""
AWS Billing Report Package.
Provides modular billing report functionality for AWS cost analysis.
"""

from .cli import main
from .cost_analysis import (
    categorize_services,
    get_combined_billing_data,
    get_date_range,
    process_cost_data,
    process_usage_data,
)
from .formatting import (
    display_regional_breakdown,
    display_usage_details,
    format_combined_billing_report,
)
from .service_checks import (
    check_cloudwatch_status,
    check_global_accelerator_status,
    check_lightsail_status,
)
from .service_checks_extended import (
    check_efs_status,
    check_kms_status,
    check_lambda_status,
    check_route53_status,
    check_vpc_status,
    get_resolved_services_status,
)

__all__ = [
    "main",
    "get_combined_billing_data",
    "get_date_range",
    "process_cost_data",
    "process_usage_data",
    "categorize_services",
    "format_combined_billing_report",
    "display_regional_breakdown",
    "display_usage_details",
    "check_global_accelerator_status",
    "check_lightsail_status",
    "check_cloudwatch_status",
    "check_lambda_status",
    "check_efs_status",
    "check_route53_status",
    "check_kms_status",
    "check_vpc_status",
    "get_resolved_services_status",
]
