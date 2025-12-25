"""Tests for cost_toolkit/scripts/billing/billing_report/cost_analysis.py (core functions)."""

# pylint: disable=too-few-public-methods

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.billing.billing_report.cost_analysis import (
    get_combined_billing_data,
    get_date_range,
    process_cost_data,
)


class TestGetDateRange:
    """Tests for get_date_range function."""

    @patch("cost_toolkit.scripts.billing.billing_report.cost_analysis.datetime")
    def test_get_date_range_first_day_of_month(self, mock_datetime):
        """Test date range when today is the first day of the month."""
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2025, 11, 1).date()
        mock_datetime.now.return_value = mock_now

        start_date, end_date = get_date_range()

        assert start_date == "2025-11-01"
        assert end_date == "2025-11-01"

    @patch("cost_toolkit.scripts.billing.billing_report.cost_analysis.datetime")
    def test_get_date_range_mid_month(self, mock_datetime):
        """Test date range when today is mid-month."""
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2025, 11, 15).date()
        mock_datetime.now.return_value = mock_now

        start_date, end_date = get_date_range()

        assert start_date == "2025-11-01"
        assert end_date == "2025-11-15"

    @patch("cost_toolkit.scripts.billing.billing_report.cost_analysis.datetime")
    def test_get_date_range_end_of_month(self, mock_datetime):
        """Test date range when today is the last day of the month."""
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2025, 11, 30).date()
        mock_datetime.now.return_value = mock_now

        start_date, end_date = get_date_range()

        assert start_date == "2025-11-01"
        assert end_date == "2025-11-30"


class TestGetCombinedBillingDataSuccess:
    """Tests for successful billing data retrieval."""

    @patch("cost_toolkit.scripts.billing.billing_report.cost_analysis.boto3.client")
    @patch("cost_toolkit.scripts.billing.billing_report.cost_analysis.get_date_range")
    def test_get_combined_billing_data_success(self, mock_get_date_range, mock_boto3_client, capsys):
        """Test successful retrieval of billing data."""
        mock_get_date_range.return_value = ("2025-11-01", "2025-11-15")

        mock_ce_client = MagicMock()
        mock_boto3_client.return_value = mock_ce_client

        cost_response = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-11-01", "End": "2025-11-15"},
                    "Groups": [],
                }
            ]
        }
        usage_response = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-11-01", "End": "2025-11-15"},
                    "Groups": [],
                }
            ]
        }

        mock_ce_client.get_cost_and_usage.side_effect = [cost_response, usage_response]

        cost_result, usage_result = get_combined_billing_data()

        assert cost_result == cost_response
        assert usage_result == usage_response
        assert mock_ce_client.get_cost_and_usage.call_count == 2

        mock_boto3_client.assert_called_once_with("ce", region_name="us-east-1")

        captured = capsys.readouterr()
        assert "Retrieving billing data from 2025-11-01 to 2025-11-15" in captured.out


class TestGetCombinedBillingDataErrors:
    """Tests for error handling during billing data retrieval."""

    @patch("cost_toolkit.scripts.billing.billing_report.cost_analysis.boto3.client")
    @patch("cost_toolkit.scripts.billing.billing_report.cost_analysis.get_date_range")
    def test_get_combined_billing_data_client_error(self, mock_get_date_range, mock_boto3_client, capsys):
        """Test handling of ClientError during billing data retrieval."""
        mock_get_date_range.return_value = ("2025-11-01", "2025-11-15")

        mock_ce_client = MagicMock()
        mock_boto3_client.return_value = mock_ce_client

        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
        mock_ce_client.get_cost_and_usage.side_effect = ClientError(error_response, "GetCostAndUsage")

        cost_result, usage_result = get_combined_billing_data()

        assert cost_result is None
        assert usage_result is None

        captured = capsys.readouterr()
        assert "Error retrieving billing data:" in captured.out


class TestGetCombinedBillingDataApiCalls:
    """Tests for correct API call parameters."""

    @patch("cost_toolkit.scripts.billing.billing_report.cost_analysis.boto3.client")
    @patch("cost_toolkit.scripts.billing.billing_report.cost_analysis.get_date_range")
    def test_get_combined_billing_data_correct_api_calls(self, mock_get_date_range, mock_boto3_client):
        """Test that API calls are made with correct parameters."""
        mock_get_date_range.return_value = ("2025-11-01", "2025-11-15")

        mock_ce_client = MagicMock()
        mock_boto3_client.return_value = mock_ce_client

        mock_ce_client.get_cost_and_usage.return_value = {"ResultsByTime": [{"Groups": []}]}

        get_combined_billing_data()

        calls = mock_ce_client.get_cost_and_usage.call_args_list
        assert len(calls) == 2

        # First call for cost data
        first_call_kwargs = calls[0][1]
        assert first_call_kwargs["TimePeriod"] == {
            "Start": "2025-11-01",
            "End": "2025-11-15",
        }
        assert first_call_kwargs["Granularity"] == "MONTHLY"
        assert first_call_kwargs["Metrics"] == ["BlendedCost", "UsageQuantity"]
        assert first_call_kwargs["GroupBy"] == [
            {"Type": "DIMENSION", "Key": "SERVICE"},
            {"Type": "DIMENSION", "Key": "REGION"},
        ]

        # Second call for usage data
        second_call_kwargs = calls[1][1]
        assert second_call_kwargs["Metrics"] == ["UsageQuantity"]
        assert second_call_kwargs["GroupBy"] == [
            {"Type": "DIMENSION", "Key": "SERVICE"},
            {"Type": "DIMENSION", "Key": "USAGE_TYPE"},
        ]


class TestProcessCostDataSingleService:
    """Tests for processing cost data with single service scenarios."""

    def test_process_cost_data_single_service_single_region(self, capsys):
        """Test processing cost data with one service in one region."""
        cost_data = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-11-01", "End": "2025-11-15"},
                    "Groups": [
                        {
                            "Keys": ["Amazon S3", "us-east-1"],
                            "Metrics": {"BlendedCost": {"Amount": "100.50"}},
                        }
                    ],
                }
            ]
        }

        service_costs, total_cost = process_cost_data(cost_data)

        assert total_cost == 100.50
        assert "Amazon S3" in service_costs
        assert service_costs["Amazon S3"]["cost"] == 100.50
        assert service_costs["Amazon S3"]["regions"]["us-east-1"] == 100.50

        captured = capsys.readouterr()
        assert "Billing Period: 2025-11-01 to 2025-11-15" in captured.out


class TestProcessCostDataMultipleServices:
    """Tests for processing cost data with multiple services and regions."""

    def test_process_cost_data_multiple_services_multiple_regions(self):
        """Test processing cost data with multiple services and regions."""
        cost_data = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-11-01", "End": "2025-11-15"},
                    "Groups": [
                        {
                            "Keys": ["Amazon S3", "us-east-1"],
                            "Metrics": {"BlendedCost": {"Amount": "100.50"}},
                        },
                        {
                            "Keys": ["Amazon S3", "us-west-2"],
                            "Metrics": {"BlendedCost": {"Amount": "50.25"}},
                        },
                        {
                            "Keys": ["Amazon EC2", "us-east-1"],
                            "Metrics": {"BlendedCost": {"Amount": "200.75"}},
                        },
                    ],
                }
            ]
        }

        service_costs, total_cost = process_cost_data(cost_data)

        assert total_cost == 351.50
        assert service_costs["Amazon S3"]["cost"] == 150.75
        assert service_costs["Amazon S3"]["regions"]["us-east-1"] == 100.50
        assert service_costs["Amazon S3"]["regions"]["us-west-2"] == 50.25
        assert service_costs["Amazon EC2"]["cost"] == 200.75
        assert service_costs["Amazon EC2"]["regions"]["us-east-1"] == 200.75


class TestProcessCostDataEdgeCases:
    """Tests for edge cases in cost data processing."""

    def test_process_cost_data_zero_cost_excluded(self):
        """Test that zero-cost items are excluded from results."""
        cost_data = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-11-01", "End": "2025-11-15"},
                    "Groups": [
                        {
                            "Keys": ["Amazon S3", "us-east-1"],
                            "Metrics": {"BlendedCost": {"Amount": "0.00"}},
                        },
                        {
                            "Keys": ["Amazon EC2", "us-east-1"],
                            "Metrics": {"BlendedCost": {"Amount": "100.00"}},
                        },
                    ],
                }
            ]
        }

        service_costs, total_cost = process_cost_data(cost_data)

        assert total_cost == 100.00
        assert "Amazon S3" not in service_costs
        assert "Amazon EC2" in service_costs

    def test_process_cost_data_missing_keys(self):
        """Test processing data with missing keys defaults to Unknown."""
        cost_data = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-11-01", "End": "2025-11-15"},
                    "Groups": [
                        {
                            "Keys": [],
                            "Metrics": {"BlendedCost": {"Amount": "50.00"}},
                        },
                        {
                            "Keys": ["Amazon S3"],
                            "Metrics": {"BlendedCost": {"Amount": "75.00"}},
                        },
                    ],
                }
            ]
        }

        service_costs, total_cost = process_cost_data(cost_data)

        assert total_cost == 125.00
        assert "Unknown Service" in service_costs
        assert service_costs["Unknown Service"]["regions"]["Unknown Region"] == 50.00
        assert "Amazon S3" in service_costs
        assert service_costs["Amazon S3"]["regions"]["Unknown Region"] == 75.00


class TestProcessCostDataAccumulation:
    """Tests for cost accumulation across time periods."""

    def test_process_cost_data_accumulates_across_periods(self):
        """Test that costs accumulate across multiple time periods."""
        cost_data = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-11-01", "End": "2025-11-08"},
                    "Groups": [
                        {
                            "Keys": ["Amazon S3", "us-east-1"],
                            "Metrics": {"BlendedCost": {"Amount": "50.00"}},
                        }
                    ],
                },
                {
                    "TimePeriod": {"Start": "2025-11-08", "End": "2025-11-15"},
                    "Groups": [
                        {
                            "Keys": ["Amazon S3", "us-east-1"],
                            "Metrics": {"BlendedCost": {"Amount": "60.00"}},
                        }
                    ],
                },
            ]
        }

        service_costs, total_cost = process_cost_data(cost_data)

        assert total_cost == 110.00
        assert service_costs["Amazon S3"]["cost"] == 110.00
        assert service_costs["Amazon S3"]["regions"]["us-east-1"] == 110.00
