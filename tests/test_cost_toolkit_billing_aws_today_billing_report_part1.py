"""Comprehensive tests for aws_today_billing_report.py - Part 1 (Core Functions)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.billing.aws_today_billing_report import (
    _process_today_data,
    _process_trend_data,
    _process_usage_details,
    get_recent_days_range,
    get_today_billing_data,
    get_today_date_range,
)


class TestDateFunctions:
    """Tests for date-related functions."""

    @patch("cost_toolkit.scripts.billing.aws_today_billing_report.datetime")
    def test_get_today_date_range(self, mock_datetime_module):
        """Test getting today's date range."""
        mock_now = datetime(2025, 11, 13, 12, 0, 0)
        mock_datetime_module.now.return_value = mock_now

        today, tomorrow = get_today_date_range()

        assert today == "2025-11-13"
        assert tomorrow == "2025-11-14"

    @patch("cost_toolkit.scripts.billing.aws_today_billing_report.datetime")
    def test_get_recent_days_range(self, mock_datetime):
        """Test getting recent days range for trends."""
        mock_now = MagicMock()
        mock_datetime.now.return_value = mock_now

        mock_three_days_ago = MagicMock()
        mock_three_days_ago.strftime.return_value = "2025-11-10"
        mock_tomorrow = MagicMock()
        mock_tomorrow.strftime.return_value = "2025-11-14"

        mock_now.__sub__.return_value = mock_three_days_ago
        mock_now.__add__.return_value = mock_tomorrow

        recent_start, recent_end = get_recent_days_range()

        assert recent_start == "2025-11-10"
        assert recent_end == "2025-11-14"


class TestGetTodayBillingData:
    """Tests for get_today_billing_data function."""

    def test_get_billing_data_success(self, capsys):
        """Test successful billing data retrieval."""
        mod = "cost_toolkit.scripts.billing.aws_today_billing_report"
        with (
            patch(f"{mod}.check_aws_credentials"),
            patch(f"{mod}.boto3.client") as mock_boto3_client,
            patch(f"{mod}.get_today_date_range") as mock_today_range,
            patch(f"{mod}.get_recent_days_range") as mock_recent_range,
        ):
            mock_today_range.return_value = ("2025-11-13", "2025-11-14")
            mock_recent_range.return_value = ("2025-11-11", "2025-11-14")

            mock_ce_client = MagicMock()
            mock_boto3_client.return_value = mock_ce_client

            today_response = {
                "ResultsByTime": [
                    {
                        "TimePeriod": {"Start": "2025-11-13", "End": "2025-11-14"},
                        "Groups": [{"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "10.50"}}}],
                    }
                ]
            }
            trend_response = {"ResultsByTime": []}
            usage_response = {"ResultsByTime": []}

            mock_ce_client.get_cost_and_usage.side_effect = [
                today_response,
                trend_response,
                usage_response,
            ]

            today_data, trend_data, usage_data = get_today_billing_data()

            assert today_data == today_response
            assert trend_data == trend_response
            assert usage_data == usage_response
            assert mock_ce_client.get_cost_and_usage.call_count == 3

            captured = capsys.readouterr()
            assert "Retrieving billing data" in captured.out

    def test_get_billing_data_client_error(self, capsys):
        """Test billing data retrieval with client error."""
        mod = "cost_toolkit.scripts.billing.aws_today_billing_report"
        with (
            patch(f"{mod}.check_aws_credentials"),
            patch(f"{mod}.boto3.client") as mock_boto3_client,
            patch(f"{mod}.get_today_date_range") as mock_today_range,
            patch(f"{mod}.get_recent_days_range") as mock_recent_range,
        ):
            mock_today_range.return_value = ("2025-11-13", "2025-11-14")
            mock_recent_range.return_value = ("2025-11-11", "2025-11-14")

            mock_ce_client = MagicMock()
            mock_boto3_client.return_value = mock_ce_client
            mock_ce_client.get_cost_and_usage.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "get_cost_and_usage")

            today_data, trend_data, usage_data = get_today_billing_data()

            assert today_data is None
            assert trend_data is None
            assert usage_data is None

            captured = capsys.readouterr()
            assert "Error retrieving billing data" in captured.out


class TestProcessTodayData:
    """Tests for _process_today_data function."""

    def test_process_today_data_with_services(self):
        """Test processing today's data with multiple services."""
        today_data = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "10.50"}}},
                        {"Keys": ["S3"], "Metrics": {"BlendedCost": {"Amount": "5.25"}}},
                    ]
                }
            ]
        }

        result = _process_today_data(today_data)

        assert result["EC2"] == 10.50
        assert result["S3"] == 5.25

    def test_process_today_data_empty(self):
        """Test processing empty today's data."""
        today_data = {"ResultsByTime": []}

        result = _process_today_data(today_data)

        assert len(result) == 0

    def test_process_today_data_unknown_service(self):
        """Test processing data with unknown service."""
        today_data = {"ResultsByTime": [{"Groups": [{"Keys": [], "Metrics": {"BlendedCost": {"Amount": "1.00"}}}]}]}

        result = _process_today_data(today_data)

        assert result["Unknown Service"] == 1.00

    def test_process_today_data_aggregates_same_service(self):
        """Test processing data aggregates costs for same service."""
        today_data = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "10.00"}}},
                        {"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "5.00"}}},
                    ]
                }
            ]
        }

        result = _process_today_data(today_data)

        assert result["EC2"] == 15.00


class TestProcessTrendData:
    """Tests for _process_trend_data function."""

    def test_process_trend_data_with_services(self):
        """Test processing trend data with multiple services."""
        trend_data = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-11-11"},
                    "Groups": [{"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "8.00"}}}],
                },
                {
                    "TimePeriod": {"Start": "2025-11-12"},
                    "Groups": [{"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "9.00"}}}],
                },
            ]
        }

        result = _process_trend_data(trend_data)

        assert len(result["EC2"]) == 2
        assert result["EC2"][0]["date"] == "2025-11-11"
        assert result["EC2"][0]["cost"] == 8.00
        assert result["EC2"][1]["date"] == "2025-11-12"
        assert result["EC2"][1]["cost"] == 9.00

    def test_process_trend_data_empty(self):
        """Test processing empty trend data."""
        result = _process_trend_data(None)

        assert len(result) == 0

    def test_process_trend_data_no_results(self):
        """Test processing trend data with no results."""
        result = _process_trend_data({})

        assert len(result) == 0


class TestProcessUsageDetails:
    """Tests for _process_usage_details function."""

    def test_process_usage_details_with_data(self):
        """Test processing usage details with data."""
        usage_data = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["EC2", "BoxUsage:t3.micro"],
                            "Metrics": {
                                "BlendedCost": {"Amount": "5.00"},
                                "UsageQuantity": {"Amount": "100", "Unit": "Hrs"},
                            },
                        }
                    ]
                }
            ]
        }

        result = _process_usage_details(usage_data)

        assert len(result["EC2"]) == 1
        assert result["EC2"][0]["usage_type"] == "BoxUsage:t3.micro"
        assert result["EC2"][0]["cost"] == 5.00
        assert result["EC2"][0]["quantity"] == 100
        assert result["EC2"][0]["unit"] == "Hrs"

    def test_process_usage_details_zero_cost_filtered(self):
        """Test processing usage details filters zero cost items."""
        usage_data = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["EC2", "BoxUsage:t3.micro"],
                            "Metrics": {
                                "BlendedCost": {"Amount": "0"},
                                "UsageQuantity": {"Amount": "100", "Unit": "Hrs"},
                            },
                        }
                    ]
                }
            ]
        }

        result = _process_usage_details(usage_data)

        assert len(result["EC2"]) == 0

    def test_process_usage_details_unknown_keys(self):
        """Test processing usage details with unknown keys."""
        usage_data = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": [],
                            "Metrics": {
                                "BlendedCost": {"Amount": "1.00"},
                                "UsageQuantity": {"Amount": "10", "Unit": "Units"},
                            },
                        }
                    ]
                }
            ]
        }

        result = _process_usage_details(usage_data)

        assert len(result["Unknown Service"]) == 1
        assert result["Unknown Service"][0]["usage_type"] == "Unknown Usage"
