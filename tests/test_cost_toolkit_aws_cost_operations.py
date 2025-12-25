"""Tests for cost_toolkit/scripts/aws_cost_operations.py"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.aws_cost_operations import (
    calculate_cost_savings,
    get_cost_and_usage,
    get_cost_forecast,
    get_daily_costs_by_service,
    get_hourly_costs_by_service,
    get_today_date_range,
)
from tests.assertions import assert_equal


def test_get_today_date_range():
    """Test get_today_date_range returns today and tomorrow."""
    with patch("cost_toolkit.scripts.aws_cost_operations.datetime") as mock_dt:
        mock_now = datetime(2025, 3, 15, 14, 30, 0)
        mock_dt.now.return_value = mock_now

        start, end = get_today_date_range()

        assert_equal(start, "2025-03-15")
        assert_equal(end, "2025-03-16")


@patch("cost_toolkit.scripts.aws_cost_operations.create_cost_explorer_client")
def test_get_cost_and_usage_default_params(mock_create_client):
    """Test get_cost_and_usage with default parameters."""
    mock_ce = MagicMock()
    mock_create_client.return_value = mock_ce
    mock_ce.get_cost_and_usage.return_value = {"ResultsByTime": []}

    result = get_cost_and_usage("2025-03-01", "2025-03-15")

    mock_create_client.assert_called_once_with(aws_access_key_id=None, aws_secret_access_key=None)
    mock_ce.get_cost_and_usage.assert_called_once_with(
        TimePeriod={"Start": "2025-03-01", "End": "2025-03-15"},
        Granularity="DAILY",
        Metrics=["BlendedCost", "UsageQuantity"],
    )
    assert_equal(result, {"ResultsByTime": []})


@patch("cost_toolkit.scripts.aws_cost_operations.create_cost_explorer_client")
def test_get_cost_and_usage_with_group_by(mock_create_client):
    """Test get_cost_and_usage with group_by parameter."""
    mock_ce = MagicMock()
    mock_create_client.return_value = mock_ce
    mock_ce.get_cost_and_usage.return_value = {"ResultsByTime": []}

    group_by = [{"Type": "DIMENSION", "Key": "SERVICE"}]
    _ = get_cost_and_usage("2025-03-01", "2025-03-15", group_by=group_by)

    call_args = mock_ce.get_cost_and_usage.call_args[1]
    assert_equal(call_args["GroupBy"], group_by)


@patch("cost_toolkit.scripts.aws_cost_operations.create_cost_explorer_client")
def test_get_cost_and_usage_with_credentials(mock_create_client):
    """Test get_cost_and_usage with AWS credentials."""
    mock_ce = MagicMock()
    mock_create_client.return_value = mock_ce
    mock_ce.get_cost_and_usage.return_value = {"ResultsByTime": []}

    get_cost_and_usage(
        "2025-03-01",
        "2025-03-15",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    mock_create_client.assert_called_once_with(aws_access_key_id="test_key", aws_secret_access_key="test_secret")


@patch("cost_toolkit.scripts.aws_cost_operations.get_cost_and_usage")
def test_get_daily_costs_by_service(mock_get_cost):
    """Test get_daily_costs_by_service calls get_cost_and_usage correctly."""
    mock_get_cost.return_value = {"ResultsByTime": []}

    result = get_daily_costs_by_service("2025-03-01", "2025-03-15")

    mock_get_cost.assert_called_once_with(
        start_date="2025-03-01",
        end_date="2025-03-15",
        granularity="DAILY",
        metrics=["BlendedCost", "UsageQuantity"],
        group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        aws_access_key_id=None,
        aws_secret_access_key=None,
    )
    assert_equal(result, {"ResultsByTime": []})


@patch("cost_toolkit.scripts.aws_cost_operations.get_cost_and_usage")
def test_get_hourly_costs_by_service(mock_get_cost):
    """Test get_hourly_costs_by_service uses HOURLY granularity."""
    mock_get_cost.return_value = {"ResultsByTime": []}

    result = get_hourly_costs_by_service("2025-03-01", "2025-03-15")

    call_args = mock_get_cost.call_args[1]
    assert_equal(call_args["granularity"], "HOURLY")
    assert_equal(result, {"ResultsByTime": []})


@patch("cost_toolkit.scripts.aws_cost_operations.create_cost_explorer_client")
def test_get_cost_forecast(mock_create_client):
    """Test get_cost_forecast calls get_cost_forecast API."""
    mock_ce = MagicMock()
    mock_create_client.return_value = mock_ce
    mock_ce.get_cost_forecast.return_value = {"Total": {"Amount": "1234.56"}}

    result = get_cost_forecast("2025-04-01", "2025-04-30")

    mock_create_client.assert_called_once_with(aws_access_key_id=None, aws_secret_access_key=None)
    mock_ce.get_cost_forecast.assert_called_once_with(
        TimePeriod={"Start": "2025-04-01", "End": "2025-04-30"},
        Metric="BLENDED_COST",
        Granularity="MONTHLY",
    )
    assert_equal(result, {"Total": {"Amount": "1234.56"}})


@patch("cost_toolkit.scripts.aws_cost_operations.create_cost_explorer_client")
def test_get_cost_forecast_with_custom_metric(mock_create_client):
    """Test get_cost_forecast with custom metric."""
    mock_ce = MagicMock()
    mock_create_client.return_value = mock_ce
    mock_ce.get_cost_forecast.return_value = {"Total": {"Amount": "5678.90"}}

    _ = get_cost_forecast("2025-04-01", "2025-04-30", metric="UNBLENDED_COST")

    call_args = mock_ce.get_cost_forecast.call_args[1]
    assert_equal(call_args["Metric"], "UNBLENDED_COST")


def test_calculate_cost_savings():
    """Test calculate_cost_savings calculates correctly."""
    result = calculate_cost_savings(1000.0, 700.0)

    assert_equal(result["current_monthly_cost"], 1000.0)
    assert_equal(result["new_monthly_cost"], 700.0)
    assert_equal(result["monthly_savings"], 300.0)
    assert_equal(result["annual_savings"], 3600.0)
    assert_equal(result["savings_percentage"], 30.0)


def test_calculate_cost_savings_zero_current_cost():
    """Test calculate_cost_savings with zero current cost."""
    result = calculate_cost_savings(0.0, 100.0)

    assert_equal(result["monthly_savings"], -100.0)
    assert_equal(result["annual_savings"], -1200.0)
    assert_equal(result["savings_percentage"], 0.0)


def test_calculate_cost_savings_equal_costs():
    """Test calculate_cost_savings with equal costs."""
    result = calculate_cost_savings(500.0, 500.0)

    assert_equal(result["monthly_savings"], 0.0)
    assert_equal(result["annual_savings"], 0.0)
    assert_equal(result["savings_percentage"], 0.0)
