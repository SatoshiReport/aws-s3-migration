"""Tests for cost_toolkit/overview/cli.py module - data retrieval functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.overview.cli import get_current_month_costs
from tests.assertions import assert_equal


class TestGetCurrentMonthCostsSuccess:
    """Test suite for get_current_month_costs successful scenarios."""

    def test_get_current_month_costs_success(self):
        """Test get_current_month_costs with successful API response."""
        mock_ce_client = MagicMock()
        mock_ce_client.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {"Keys": ["Amazon EC2"], "Metrics": {"BlendedCost": {"Amount": "150.75"}}},
                        {"Keys": ["Amazon S3"], "Metrics": {"BlendedCost": {"Amount": "25.50"}}},
                    ]
                }
            ]
        }
        with patch("boto3.client", return_value=mock_ce_client):
            service_costs, total_cost = get_current_month_costs()
            assert_equal(service_costs, {"Amazon EC2": 150.75, "Amazon S3": 25.50})
            assert_equal(total_cost, 176.25)
            mock_ce_client.get_cost_and_usage.assert_called_once()

    def test_get_current_month_costs_filters_zero_costs(self):
        """Test get_current_month_costs filters out zero-cost services."""
        mock_ce_client = MagicMock()
        mock_ce_client.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {"Keys": ["Amazon EC2"], "Metrics": {"BlendedCost": {"Amount": "100.00"}}},
                        {"Keys": ["Amazon S3"], "Metrics": {"BlendedCost": {"Amount": "0.00"}}},
                        {"Keys": ["Amazon RDS"], "Metrics": {"BlendedCost": {"Amount": "50.00"}}},
                    ]
                }
            ]
        }
        with patch("boto3.client", return_value=mock_ce_client):
            service_costs, total_cost = get_current_month_costs()
            assert_equal(service_costs, {"Amazon EC2": 100.00, "Amazon RDS": 50.00})
            assert "Amazon S3" not in service_costs
            assert_equal(total_cost, 150.00)


class TestGetCurrentMonthCostsConfiguration:
    """Test suite for get_current_month_costs client and parameter configuration."""

    def test_get_current_month_costs_creates_correct_client(self):
        """Test get_current_month_costs creates CE client with correct parameters."""
        mock_ce_client = MagicMock()
        mock_ce_client.get_cost_and_usage.return_value = {"ResultsByTime": []}

        with patch("boto3.client", return_value=mock_ce_client) as mock_boto:
            get_current_month_costs()

            mock_boto.assert_called_once_with("ce", region_name="us-east-1")

    def test_get_current_month_costs_correct_time_period(self):
        """Test get_current_month_costs uses correct time period."""
        mock_ce_client = MagicMock()
        mock_ce_client.get_cost_and_usage.return_value = {"ResultsByTime": []}

        with (
            patch("boto3.client", return_value=mock_ce_client),
            patch("cost_toolkit.overview.cli.datetime") as mock_datetime,
        ):
            mock_now = MagicMock()
            mock_now.date.return_value.replace.return_value.strftime.return_value = "2025-11-01"
            mock_now.date.return_value.strftime.return_value = "2025-11-12"
            mock_datetime.now.return_value = mock_now

            get_current_month_costs()

            call_args = mock_ce_client.get_cost_and_usage.call_args
            time_period = call_args.kwargs["TimePeriod"]
            assert "Start" in time_period
            assert "End" in time_period

    def test_get_current_month_costs_correct_api_parameters(self):
        """Test get_current_month_costs passes correct parameters to API."""
        mock_ce_client = MagicMock()
        mock_ce_client.get_cost_and_usage.return_value = {"ResultsByTime": []}

        with patch("boto3.client", return_value=mock_ce_client):
            get_current_month_costs()

            call_args = mock_ce_client.get_cost_and_usage.call_args
            assert_equal(call_args.kwargs["Granularity"], "MONTHLY")
            assert_equal(call_args.kwargs["Metrics"], ["BlendedCost"])
            assert_equal(call_args.kwargs["GroupBy"], [{"Type": "DIMENSION", "Key": "SERVICE"}])


class TestGetCurrentMonthCostsErrorHandling:
    """Test suite for get_current_month_costs error handling and edge cases."""

    def test_get_current_month_costs_handles_client_error(self, capsys):
        """Test get_current_month_costs handles ClientError gracefully."""
        mock_ce_client = MagicMock()
        mock_ce_client.get_cost_and_usage.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "GetCostAndUsage",
        )
        with patch("boto3.client", return_value=mock_ce_client):
            service_costs, total_cost = get_current_month_costs()
            assert_equal(service_costs, {})
            assert_equal(total_cost, 0.0)
            captured = capsys.readouterr()
            assert "Error retrieving cost data" in captured.out

    def test_get_current_month_costs_empty_response(self):
        """Test get_current_month_costs with empty API response."""
        mock_ce_client = MagicMock()
        mock_ce_client.get_cost_and_usage.return_value = {"ResultsByTime": []}
        with patch("boto3.client", return_value=mock_ce_client):
            service_costs, total_cost = get_current_month_costs()
            assert_equal(service_costs, {})
            assert_equal(total_cost, 0.0)

    def test_get_current_month_costs_multiple_result_periods(self):
        """Test get_current_month_costs handles multiple result periods."""
        mock_ce_client = MagicMock()
        mock_ce_client.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {"Keys": ["Amazon EC2"], "Metrics": {"BlendedCost": {"Amount": "100.00"}}}
                    ]
                },
                {
                    "Groups": [
                        {"Keys": ["Amazon S3"], "Metrics": {"BlendedCost": {"Amount": "50.00"}}}
                    ]
                },
            ]
        }
        with patch("boto3.client", return_value=mock_ce_client):
            service_costs, total_cost = get_current_month_costs()
            assert_equal(service_costs, {"Amazon EC2": 100.00, "Amazon S3": 50.00})
            assert_equal(total_cost, 150.00)
