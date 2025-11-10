"""Validation and cost calculation utilities"""


def calculate_cost_savings(snapshot_size_gb):
    """Calculate cost savings from EBS to S3 Standard"""
    ebs_monthly_cost = snapshot_size_gb * 0.05
    s3_standard_cost = snapshot_size_gb * 0.023
    monthly_savings = ebs_monthly_cost - s3_standard_cost
    annual_savings = monthly_savings * 12

    return {
        "ebs_cost": ebs_monthly_cost,
        "s3_cost": s3_standard_cost,
        "monthly_savings": monthly_savings,
        "annual_savings": annual_savings,
        "savings_percentage": (monthly_savings / ebs_monthly_cost) * 100,
    }
