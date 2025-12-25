"""Tests for display functions in cost_toolkit/scripts/billing/billing_report/formatting.py"""

from __future__ import annotations

from cost_toolkit.scripts.billing.billing_report.formatting import (
    display_regional_breakdown,
    display_usage_details,
)


def test_display_regional_breakdown_single_region(capsys):
    """Test display_regional_breakdown with a single region."""
    service_cost = 100.0
    regions = {"us-east-1": 100.0}

    display_regional_breakdown(service_cost, regions)

    captured = capsys.readouterr()
    assert "Regional Breakdown:" in captured.out
    assert "Region" in captured.out
    assert "Cost" in captured.out
    assert "% of Service" in captured.out
    assert "us-east-1" in captured.out
    assert "$      100.00" in captured.out
    assert "100.0%" in captured.out


def test_display_regional_breakdown_multiple_regions_sorted(capsys):
    """Test display_regional_breakdown with multiple regions sorted by cost."""
    service_cost = 300.0
    regions = {
        "us-east-1": 100.0,
        "us-west-2": 150.0,
        "eu-west-1": 50.0,
    }

    display_regional_breakdown(service_cost, regions)

    captured = capsys.readouterr()
    output_lines = captured.out.split("\n")

    # Find the region lines (after the header and separator)
    region_lines = [line for line in output_lines if line and "$" in line and ("us-" in line or "eu-" in line)]

    # Verify sorting by cost (highest first)
    assert len(region_lines) == 3
    assert "us-west-2" in region_lines[0]
    assert "us-east-1" in region_lines[1]
    assert "eu-west-1" in region_lines[2]


def test_display_regional_breakdown_with_zero_cost_regions(capsys):
    """Test display_regional_breakdown filters out zero-cost regions."""
    service_cost = 100.0
    regions = {
        "us-east-1": 100.0,
        "us-west-2": 0.0,
        "eu-west-1": 0.0,
    }

    display_regional_breakdown(service_cost, regions)

    captured = capsys.readouterr()
    assert "us-east-1" in captured.out
    assert "us-west-2" not in captured.out
    assert "eu-west-1" not in captured.out


def test_display_regional_breakdown_zero_service_cost(capsys):
    """Test display_regional_breakdown handles zero service cost without division error."""
    service_cost = 0.0
    regions = {"us-east-1": 0.0}

    display_regional_breakdown(service_cost, regions)

    captured = capsys.readouterr()
    assert "Regional Breakdown:" in captured.out
    # Should not raise division by zero error


def test_display_regional_breakdown_percentage_calculation(capsys):
    """Test display_regional_breakdown calculates percentages correctly."""
    service_cost = 200.0
    regions = {
        "us-east-1": 150.0,  # 75%
        "us-west-2": 50.0,  # 25%
    }

    display_regional_breakdown(service_cost, regions)

    captured = capsys.readouterr()
    assert "75.0%" in captured.out
    assert "25.0%" in captured.out


def test_display_usage_details_with_usage_data(capsys):
    """Test display_usage_details with valid usage data."""
    service = "Amazon EC2"
    service_usage = {
        "Amazon EC2": [
            ("BoxUsage:t3.micro", 100.5, "Hrs"),
            ("DataTransfer-Out-Bytes", 1000000.0, "Bytes"),
            ("EBS:VolumeUsage", 50.0, "GB-Mo"),
        ]
    }

    display_usage_details(service, service_usage)

    captured = capsys.readouterr()
    assert "Usage Details:" in captured.out
    assert "Usage Type" in captured.out
    assert "Quantity" in captured.out
    assert "Unit" in captured.out
    assert "BoxUsage:t3.micro" in captured.out
    assert "100.50" in captured.out
    assert "Hrs" in captured.out
    assert "DataTransfer-Out-Bytes" in captured.out
    assert "EBS:VolumeUsage" in captured.out


def test_display_usage_details_no_usage_data(capsys):
    """Test display_usage_details when service has no usage data."""
    service = "Amazon S3"
    service_usage = {}

    display_usage_details(service, service_usage)

    captured = capsys.readouterr()
    assert captured.out == ""


def test_display_usage_details_empty_usage_list(capsys):
    """Test display_usage_details when service has empty usage list."""
    service = "Amazon S3"
    service_usage = {"Amazon S3": []}

    display_usage_details(service, service_usage)

    captured = capsys.readouterr()
    assert captured.out == ""


def test_display_usage_details_limits_to_top_10(capsys):
    """Test display_usage_details limits output to top 10 usage types."""
    service = "Amazon EC2"
    # Create 15 usage items
    usage_items = [(f"UsageType{i}", float(100 - i), "Unit") for i in range(15)]
    service_usage = {"Amazon EC2": usage_items}

    display_usage_details(service, service_usage)

    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.split("\n") if "UsageType" in line]

    # Should only show top 10
    assert len(output_lines) == 10
    assert "UsageType0" in captured.out  # Highest
    assert "UsageType9" in captured.out  # 10th highest
    assert "UsageType14" not in captured.out  # Should be excluded


def test_display_usage_details_sorted_by_quantity(capsys):
    """Test display_usage_details sorts by quantity descending."""
    service = "Amazon S3"
    service_usage = {
        "Amazon S3": [
            ("PutRequests", 50.0, "Requests"),
            ("GetRequests", 1000.0, "Requests"),
            ("DataTransfer", 200.0, "GB"),
        ]
    }

    display_usage_details(service, service_usage)

    captured = capsys.readouterr()
    output_lines = captured.out.split("\n")
    usage_lines = [line for line in output_lines if "Requests" in line or "GB" in line]

    # Verify sorting (GetRequests should be first, PutRequests last)
    assert len(usage_lines) == 3
    assert "GetRequests" in usage_lines[0]
    assert "DataTransfer" in usage_lines[1]
    assert "PutRequests" in usage_lines[2]
