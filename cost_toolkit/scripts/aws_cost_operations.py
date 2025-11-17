#!/usr/bin/env python3
"""
AWS Cost Explorer Operations Module
Common Cost Explorer API operations extracted to reduce code duplication.
"""

from datetime import datetime, timedelta
from typing import Optional

from cost_toolkit.common.aws_client_factory import create_cost_explorer_client


def get_today_date_range() -> tuple[str, str]:
    """
    Get the date range for today in YYYY-MM-DD format for Cost Explorer.

    Returns:
        tuple: (start_date, end_date) where end_date is tomorrow
    """
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    return start_of_day.strftime("%Y-%m-%d"), end_of_day.strftime("%Y-%m-%d")


def get_month_date_range() -> tuple[str, str]:
    """
    Get the date range for the current month in YYYY-MM-DD format.

    Returns:
        tuple: (start_date, end_date) where start is first day of month, end is tomorrow
    """
    now = datetime.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_date = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    return start_of_month.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def get_cost_and_usage(
    start_date: str,
    end_date: str,
    *,
    granularity: str = "DAILY",
    metrics: Optional[list[str]] = None,
    group_by: Optional[list[dict]] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> dict:
    """
    Get cost and usage data from AWS Cost Explorer.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        granularity: Time granularity (DAILY, MONTHLY, HOURLY)
        metrics: List of metrics to retrieve (default: ["BlendedCost", "UsageQuantity"])
        group_by: Optional list of grouping dimensions
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        dict: Cost and usage data response

    Raises:
        ClientError: If API call fails
    """
    ce_client = create_cost_explorer_client(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    if metrics is None:
        metrics = ["BlendedCost", "UsageQuantity"]

    params = {
        "TimePeriod": {"Start": start_date, "End": end_date},
        "Granularity": granularity,
        "Metrics": metrics,
    }

    if group_by:
        params["GroupBy"] = group_by

    return ce_client.get_cost_and_usage(**params)


def get_daily_costs_by_service(
    start_date: str,
    end_date: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> dict:
    """
    Get daily costs grouped by service.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        dict: Cost and usage data grouped by service

    Raises:
        ClientError: If API call fails
    """
    return get_cost_and_usage(
        start_date=start_date,
        end_date=end_date,
        granularity="DAILY",
        metrics=["BlendedCost", "UsageQuantity"],
        group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def get_hourly_costs_by_service(
    start_date: str,
    end_date: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> dict:
    """
    Get hourly costs grouped by service.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        dict: Cost and usage data grouped by service with hourly granularity

    Raises:
        ClientError: If API call fails
    """
    return get_cost_and_usage(
        start_date=start_date,
        end_date=end_date,
        granularity="HOURLY",
        metrics=["BlendedCost", "UsageQuantity"],
        group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def get_costs_by_service_and_usage_type(
    start_date: str,
    end_date: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> dict:
    """
    Get costs grouped by both service and usage type.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        dict: Cost and usage data grouped by service and usage type

    Raises:
        ClientError: If API call fails
    """
    return get_cost_and_usage(
        start_date=start_date,
        end_date=end_date,
        granularity="DAILY",
        metrics=["BlendedCost", "UsageQuantity"],
        group_by=[
            {"Type": "DIMENSION", "Key": "SERVICE"},
            {"Type": "DIMENSION", "Key": "USAGE_TYPE"},
        ],
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def get_monthly_costs(
    start_date: str,
    end_date: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> dict:
    """
    Get monthly aggregated costs.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        dict: Cost and usage data with monthly granularity

    Raises:
        ClientError: If API call fails
    """
    return get_cost_and_usage(
        start_date=start_date,
        end_date=end_date,
        granularity="MONTHLY",
        metrics=["BlendedCost", "UsageQuantity"],
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def get_cost_forecast(
    start_date: str,
    end_date: str,
    metric: str = "BLENDED_COST",
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> dict:
    """
    Get cost forecast from AWS Cost Explorer.

    Args:
        start_date: Start date in YYYY-MM-DD format (must be in future)
        end_date: End date in YYYY-MM-DD format
        metric: Metric to forecast (default: BLENDED_COST)
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        dict: Cost forecast data

    Raises:
        ClientError: If API call fails
    """
    ce_client = create_cost_explorer_client(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    return ce_client.get_cost_forecast(
        TimePeriod={"Start": start_date, "End": end_date},
        Metric=metric,
        Granularity="MONTHLY",
    )


def calculate_cost_savings(
    current_monthly_cost: float,
    new_monthly_cost: float,
) -> dict:
    """
    Calculate cost savings between current and new monthly costs.

    Args:
        current_monthly_cost: Current monthly cost
        new_monthly_cost: Projected new monthly cost

    Returns:
        dict: Savings analysis with monthly_savings, annual_savings, and savings_percentage
    """
    monthly_savings = current_monthly_cost - new_monthly_cost
    annual_savings = monthly_savings * 12

    savings_percentage = 0.0
    if current_monthly_cost > 0:
        savings_percentage = (monthly_savings / current_monthly_cost) * 100

    return {
        "current_monthly_cost": current_monthly_cost,
        "new_monthly_cost": new_monthly_cost,
        "monthly_savings": monthly_savings,
        "annual_savings": annual_savings,
        "savings_percentage": savings_percentage,
    }


if __name__ == "__main__":  # pragma: no cover - script entry point
    pass
