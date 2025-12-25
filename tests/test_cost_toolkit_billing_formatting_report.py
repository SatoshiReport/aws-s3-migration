"""Tests for format_combined_billing_report in cost_toolkit/scripts/billing/
billing_report/formatting.py"""

# pylint: disable=redefined-outer-name

from __future__ import annotations

from unittest.mock import patch

import pytest

from cost_toolkit.scripts.billing.billing_report.formatting import (
    format_combined_billing_report,
)


@pytest.fixture
def mock_formatting_dependencies():
    """Fixture to mock all dependencies of format_combined_billing_report."""
    fmt_base = "cost_toolkit.scripts.billing.billing_report.formatting"
    with (
        patch(f"{fmt_base}.process_cost_data") as m_cost,
        patch(f"{fmt_base}.process_usage_data") as m_usage,
        patch(f"{fmt_base}.get_resolved_services_status") as m_resolved,
        patch(f"{fmt_base}.categorize_services") as m_categorize,
        patch(f"{fmt_base}.display_regional_breakdown") as m_regional,
        patch(f"{fmt_base}.display_usage_details") as m_usage_details,
    ):
        yield {
            "process_cost": m_cost,
            "process_usage": m_usage,
            "resolved_services": m_resolved,
            "categorize": m_categorize,
            "display_regional": m_regional,
            "display_usage": m_usage_details,
        }


def test_format_combined_billing_report_no_data(mock_formatting_dependencies, capsys):
    """Test format_combined_billing_report with no billing data."""
    cost_data = {}
    usage_data = {}

    format_combined_billing_report(cost_data, usage_data)

    captured = capsys.readouterr()
    assert "No billing data available" in captured.out
    mock_formatting_dependencies["process_cost"].assert_not_called()


def test_format_combined_billing_report_none_data(mock_formatting_dependencies, capsys):
    """Test format_combined_billing_report with None cost_data."""
    cost_data = None
    usage_data = {}

    format_combined_billing_report(cost_data, usage_data)

    captured = capsys.readouterr()
    assert "No billing data available" in captured.out
    mock_formatting_dependencies["process_cost"].assert_not_called()


def test_format_combined_billing_report_missing_results_by_time(mock_formatting_dependencies, capsys):
    """Test format_combined_billing_report when cost_data lacks ResultsByTime."""
    cost_data = {"SomeOtherKey": "value"}
    usage_data = {}

    format_combined_billing_report(cost_data, usage_data)

    captured = capsys.readouterr()
    assert "No billing data available" in captured.out
    mock_formatting_dependencies["process_cost"].assert_not_called()


def test_format_combined_billing_report_with_valid_data(mock_formatting_dependencies, capsys):
    """Test format_combined_billing_report with valid billing data."""
    cost_data = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2025-01-01", "End": "2025-01-31"},
                "Groups": [],
            }
        ]
    }
    usage_data = {"ResultsByTime": []}

    service_costs = {
        "Amazon EC2": {
            "cost": 150.50,
            "regions": {"us-east-1": 100.0, "us-west-2": 50.50},
        },
        "Amazon S3": {
            "cost": 50.25,
            "regions": {"us-east-1": 50.25},
        },
    }
    total_cost = 200.75

    service_usage = {
        "Amazon EC2": [("BoxUsage:t3.micro", 100.0, "Hrs")],
        "Amazon S3": [("PutRequests", 1000.0, "Requests")],
    }

    resolved_services = {
        "AMAZON EC2": "✅ RESOLVED - Instances stopped",
        "AMAZON S3": "",
    }

    mocks = mock_formatting_dependencies
    mocks["process_cost"].return_value = (service_costs, total_cost)
    mocks["process_usage"].return_value = service_usage
    mocks["resolved_services"].return_value = resolved_services
    mocks["categorize"].return_value = [
        ("Amazon EC2", service_costs["Amazon EC2"]),
        ("Amazon S3", service_costs["Amazon S3"]),
    ]

    format_combined_billing_report(cost_data, usage_data)

    captured = capsys.readouterr()
    assert "COMBINED AWS BILLING & USAGE REPORT" in captured.out
    assert "AMAZON EC2" in captured.out
    assert "AMAZON S3" in captured.out
    assert "$150.50" in captured.out
    assert "$50.25" in captured.out
    assert "$200.75" in captured.out

    mocks["process_cost"].assert_called_once_with(cost_data)
    mocks["process_usage"].assert_called_once_with(usage_data)
    mocks["resolved_services"].assert_called_once()
    mocks["categorize"].assert_called_once_with(service_costs, resolved_services)

    # Verify display functions called for each service
    assert mocks["display_regional"].call_count == 2
    assert mocks["display_usage"].call_count == 2


def test_format_combined_billing_report_with_status_message(mock_formatting_dependencies, capsys):
    """Test format_combined_billing_report displays status messages."""
    cost_data = {"ResultsByTime": [{}]}
    usage_data = {}

    service_costs = {
        "Amazon Lambda": {
            "cost": 25.0,
            "regions": {"us-east-1": 25.0},
        },
    }
    total_cost = 25.0

    resolved_services = {
        "AMAZON LAMBDA": "✅ RESOLVED - All functions deleted",
    }

    mocks = mock_formatting_dependencies
    mocks["process_cost"].return_value = (service_costs, total_cost)
    mocks["process_usage"].return_value = {}
    mocks["resolved_services"].return_value = resolved_services
    mocks["categorize"].return_value = [
        ("Amazon Lambda", service_costs["Amazon Lambda"]),
    ]

    format_combined_billing_report(cost_data, usage_data)

    captured = capsys.readouterr()
    assert "AMAZON LAMBDA" in captured.out
    assert "STATUS: ✅ RESOLVED - All functions deleted" in captured.out


def test_format_combined_billing_report_percentage_calculation(mock_formatting_dependencies, capsys):
    """Test format_combined_billing_report calculates service percentages correctly."""
    cost_data = {"ResultsByTime": [{}]}
    usage_data = {}

    service_costs = {
        "Amazon EC2": {
            "cost": 75.0,
            "regions": {"us-east-1": 75.0},
        },
        "Amazon S3": {
            "cost": 25.0,
            "regions": {"us-east-1": 25.0},
        },
    }
    total_cost = 100.0

    mocks = mock_formatting_dependencies
    mocks["process_cost"].return_value = (service_costs, total_cost)
    mocks["process_usage"].return_value = {}
    mocks["resolved_services"].return_value = {}
    mocks["categorize"].return_value = [
        ("Amazon EC2", service_costs["Amazon EC2"]),
        ("Amazon S3", service_costs["Amazon S3"]),
    ]

    format_combined_billing_report(cost_data, usage_data)

    captured = capsys.readouterr()
    # EC2 should be 75% of total
    assert "(75.0% of total)" in captured.out
    # S3 should be 25% of total
    assert "(25.0% of total)" in captured.out


def test_format_combined_billing_report_zero_total_cost(mock_formatting_dependencies, capsys):
    """Test format_combined_billing_report handles zero total cost without division error."""
    cost_data = {"ResultsByTime": [{}]}
    usage_data = {}

    service_costs = {
        "Amazon EC2": {
            "cost": 0.0,
            "regions": {"us-east-1": 0.0},
        },
    }
    total_cost = 0.0

    mocks = mock_formatting_dependencies
    mocks["process_cost"].return_value = (service_costs, total_cost)
    mocks["process_usage"].return_value = {}
    mocks["resolved_services"].return_value = {}
    mocks["categorize"].return_value = [
        ("Amazon EC2", service_costs["Amazon EC2"]),
    ]

    format_combined_billing_report(cost_data, usage_data)

    captured = capsys.readouterr()
    assert "COMBINED AWS BILLING & USAGE REPORT" in captured.out
    assert "TOTAL AWS COST: $0.00" in captured.out
    # Should not raise division by zero error


def test_format_combined_billing_report_service_without_status(mock_formatting_dependencies, capsys):
    """Test format_combined_billing_report handles service without status message."""
    cost_data = {"ResultsByTime": [{}]}
    usage_data = {}

    service_costs = {
        "Amazon EC2": {
            "cost": 100.0,
            "regions": {"us-east-1": 100.0},
        },
    }
    total_cost = 100.0

    resolved_services = {}  # No status for EC2

    mocks = mock_formatting_dependencies
    mocks["process_cost"].return_value = (service_costs, total_cost)
    mocks["process_usage"].return_value = {}
    mocks["resolved_services"].return_value = resolved_services
    mocks["categorize"].return_value = [
        ("Amazon EC2", service_costs["Amazon EC2"]),
    ]

    format_combined_billing_report(cost_data, usage_data)

    captured = capsys.readouterr()
    assert "AMAZON EC2" in captured.out
    assert "STATUS:" not in captured.out  # No status message should be printed


def test_format_combined_billing_report_calls_display_functions_correctly(
    mock_formatting_dependencies,
):
    """Test format_combined_billing_report calls display functions with correct arguments."""
    cost_data = {"ResultsByTime": [{}]}
    usage_data = {}

    service_costs = {
        "Amazon EC2": {
            "cost": 100.0,
            "regions": {"us-east-1": 60.0, "us-west-2": 40.0},
        },
    }
    total_cost = 100.0

    service_usage = {
        "Amazon EC2": [("BoxUsage:t3.micro", 100.0, "Hrs")],
    }

    mocks = mock_formatting_dependencies
    mocks["process_cost"].return_value = (service_costs, total_cost)
    mocks["process_usage"].return_value = service_usage
    mocks["resolved_services"].return_value = {}
    mocks["categorize"].return_value = [
        ("Amazon EC2", service_costs["Amazon EC2"]),
    ]

    format_combined_billing_report(cost_data, usage_data)

    # Verify display_regional_breakdown called with correct args
    mocks["display_regional"].assert_called_once_with(100.0, {"us-east-1": 60.0, "us-west-2": 40.0})

    # Verify display_usage_details called with correct args
    mocks["display_usage"].assert_called_once_with("Amazon EC2", service_usage)
