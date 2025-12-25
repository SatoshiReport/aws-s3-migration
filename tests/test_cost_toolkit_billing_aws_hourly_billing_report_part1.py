"""Comprehensive tests for aws_hourly_billing_report.py - Part 1 (Core Functions)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.billing.aws_hourly_billing_report import (
    _display_current_hour_section,
    _display_daily_summary,
    _display_hourly_trends,
    _process_daily_data,
    _process_hourly_data,
    get_hourly_billing_data,
)


class TestGetHourlyBillingData:
    """Tests for get_hourly_billing_data function."""

    def test_get_hourly_billing_data_success(self, capsys):
        """Test successful hourly billing data retrieval."""
        mod = "cost_toolkit.scripts.billing.aws_hourly_billing_report"
        with (
            patch(f"{mod}.get_today_date_range") as mock_get_date_range,
            patch(f"{mod}.get_hourly_costs_by_service") as mock_get_hourly,
            patch(f"{mod}.get_daily_costs_by_service") as mock_get_daily,
        ):
            mock_get_date_range.return_value = ("2025-11-13", "2025-11-14")

            hourly_response = {
                "ResultsByTime": [
                    {
                        "TimePeriod": {
                            "Start": "2025-11-13T00:00:00Z",
                            "End": "2025-11-13T01:00:00Z",
                        },
                        "Groups": [{"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "0.50"}}}],
                    }
                ]
            }
            daily_response = {
                "ResultsByTime": [
                    {
                        "TimePeriod": {"Start": "2025-11-13", "End": "2025-11-14"},
                        "Groups": [{"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "10.00"}}}],
                    }
                ]
            }

            mock_get_hourly.return_value = hourly_response
            mock_get_daily.return_value = daily_response

            hourly_data, daily_data = get_hourly_billing_data()

            assert hourly_data == hourly_response
            assert daily_data == daily_response

            captured = capsys.readouterr()
            assert "Retrieving hourly billing data" in captured.out

    @patch("cost_toolkit.scripts.billing.aws_hourly_billing_report.get_today_date_range")
    @patch("cost_toolkit.scripts.billing.aws_hourly_billing_report.get_hourly_costs_by_service")
    def test_get_hourly_billing_data_error(
        self,
        mock_get_hourly,
        mock_get_date_range,
        capsys,
    ):
        """Test hourly billing data retrieval with error."""
        mock_get_date_range.return_value = ("2025-11-13", "2025-11-14")
        mock_get_hourly.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "get_cost_and_usage")

        hourly_data, daily_data = get_hourly_billing_data()

        assert hourly_data is None
        assert daily_data is None

        captured = capsys.readouterr()
        assert "Error retrieving billing data" in captured.out


class TestProcessDailyData:
    """Tests for _process_daily_data function."""

    def test_process_daily_data_with_services(self):
        """Test processing daily data with multiple services."""
        daily_data = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "10.00"}}},
                        {"Keys": ["S3"], "Metrics": {"BlendedCost": {"Amount": "5.00"}}},
                    ]
                }
            ]
        }

        result = _process_daily_data(daily_data)

        assert result["EC2"] == 10.00
        assert result["S3"] == 5.00

    def test_process_daily_data_empty(self):
        """Test processing empty daily data."""
        result = _process_daily_data(None)

        assert len(result) == 0

    def test_process_daily_data_no_results(self):
        """Test processing daily data with no results."""
        result = _process_daily_data({})

        assert len(result) == 0

    def test_process_daily_data_aggregates_costs(self):
        """Test daily data aggregates costs for same service."""
        daily_data = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "7.00"}}},
                        {"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "3.00"}}},
                    ]
                }
            ]
        }

        result = _process_daily_data(daily_data)

        assert result["EC2"] == 10.00


class TestProcessHourlyData:
    """Tests for _process_hourly_data function."""

    def test_process_hourly_data_with_services(self):
        """Test processing hourly data with multiple services."""
        current_hour = datetime(2025, 11, 13, 12, 0, 0)

        hourly_data = {
            "ResultsByTime": [
                {
                    "TimePeriod": {
                        "Start": "2025-11-13T12:00:00+00:00",
                        "End": "2025-11-13T13:00:00+00:00",
                    },
                    "Groups": [{"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "1.50"}}}],
                },
                {
                    "TimePeriod": {
                        "Start": "2025-11-13T11:00:00+00:00",
                        "End": "2025-11-13T12:00:00+00:00",
                    },
                    "Groups": [{"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "1.00"}}}],
                },
            ]
        }

        hourly_service_costs, current_hour_costs = _process_hourly_data(hourly_data, current_hour)

        assert len(hourly_service_costs["EC2"]) == 2
        assert current_hour_costs["EC2"] == 1.50

    def test_process_hourly_data_filters_zero_cost(self):
        """Test processing hourly data filters zero cost entries."""
        current_hour = datetime(2025, 11, 13, 12, 0, 0)

        hourly_data = {
            "ResultsByTime": [
                {
                    "TimePeriod": {
                        "Start": "2025-11-13T12:00:00Z",
                        "End": "2025-11-13T13:00:00Z",
                    },
                    "Groups": [{"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "0.00"}}}],
                }
            ]
        }

        hourly_service_costs, current_hour_costs = _process_hourly_data(hourly_data, current_hour)

        assert len(hourly_service_costs["EC2"]) == 0
        assert "EC2" not in current_hour_costs

    def test_process_hourly_data_unknown_service(self):
        """Test processing hourly data with unknown service."""
        current_hour = datetime(2025, 11, 13, 12, 0, 0)

        hourly_data = {
            "ResultsByTime": [
                {
                    "TimePeriod": {
                        "Start": "2025-11-13T12:00:00Z",
                        "End": "2025-11-13T13:00:00Z",
                    },
                    "Groups": [{"Keys": [], "Metrics": {"BlendedCost": {"Amount": "1.00"}}}],
                }
            ]
        }

        hourly_service_costs, current_hour_costs = _process_hourly_data(hourly_data, current_hour)

        assert "Unknown Service" in hourly_service_costs
        assert current_hour_costs["Unknown Service"] == 1.00


class TestDisplayCurrentHourSection:
    """Tests for _display_current_hour_section function."""

    def test_display_current_hour_with_services(self, capsys):
        """Test displaying current hour section with active services."""
        current_hour_costs = {"EC2": 1.50, "S3": 0.75}
        current_hour = datetime(2025, 11, 13, 12, 0, 0)
        now = datetime(2025, 11, 13, 12, 30, 0)
        daily_service_costs = {"EC2": 10.00, "S3": 5.00}

        _display_current_hour_section(current_hour_costs, current_hour, now, daily_service_costs)

        captured = capsys.readouterr()
        assert "ACTIVE SERVICES IN CURRENT HOUR" in captured.out
        assert "EC2" in captured.out
        assert "$1.500000" in captured.out
        assert "Current Hour Total" in captured.out

    def test_display_current_hour_no_services(self, capsys):
        """Test displaying current hour section with no active services."""
        current_hour_costs = {}
        current_hour = datetime(2025, 11, 13, 12, 0, 0)
        now = datetime(2025, 11, 13, 12, 30, 0)
        daily_service_costs = {}

        _display_current_hour_section(current_hour_costs, current_hour, now, daily_service_costs)

        captured = capsys.readouterr()
        assert "NO ACTIVE SERVICES IN CURRENT HOUR" in captured.out

    def test_display_current_hour_sorted_by_cost(self, capsys):
        """Test services are sorted by cost in current hour section."""
        current_hour_costs = {"S3": 0.75, "EC2": 1.50, "RDS": 0.25}
        current_hour = datetime(2025, 11, 13, 12, 0, 0)
        now = datetime(2025, 11, 13, 12, 30, 0)
        daily_service_costs = {"EC2": 10.00, "S3": 5.00, "RDS": 2.00}

        _display_current_hour_section(current_hour_costs, current_hour, now, daily_service_costs)

        captured = capsys.readouterr()
        ec2_pos = captured.out.find("EC2")
        s3_pos = captured.out.find("S3")
        rds_pos = captured.out.find("RDS")
        assert ec2_pos < s3_pos < rds_pos


class TestDisplayDailySummary:
    """Tests for _display_daily_summary function."""

    def test_display_daily_summary_with_services(self, capsys):
        """Test displaying daily summary with services."""
        daily_service_costs = {"EC2": 10.00, "S3": 5.00}
        hourly_service_costs = {
            "EC2": [
                {"hour": datetime(2025, 11, 13, 10, 0, 0), "cost": 1.00},
                {"hour": datetime(2025, 11, 13, 11, 0, 0), "cost": 1.50},
            ]
        }

        _display_daily_summary(daily_service_costs, hourly_service_costs)

        captured = capsys.readouterr()
        assert "TODAY'S COST SUMMARY BY SERVICE" in captured.out
        assert "EC2" in captured.out
        assert "$10.000000" in captured.out
        assert "Today's Total" in captured.out

    def test_display_daily_summary_no_services(self, capsys):
        """Test displaying daily summary with no services."""
        _display_daily_summary({}, {})

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_display_daily_summary_with_hourly_breakdown(self, capsys):
        """Test daily summary includes hourly breakdown."""
        daily_service_costs = {"EC2": 12.00}
        hourly_service_costs = {
            "EC2": [
                {"hour": datetime(2025, 11, 13, 10, 0, 0), "cost": 2.00},
                {"hour": datetime(2025, 11, 13, 11, 0, 0), "cost": 3.00},
                {"hour": datetime(2025, 11, 13, 12, 0, 0), "cost": 4.00},
            ]
        }

        _display_daily_summary(daily_service_costs, hourly_service_costs)

        captured = capsys.readouterr()
        assert "3h active" in captured.out
        assert "avg $4.000000/h" in captured.out


class TestDisplayHourlyTrends:
    """Tests for _display_hourly_trends function."""

    def test_display_hourly_trends_with_data(self, capsys):
        """Test displaying hourly trends."""
        hourly_service_costs = {
            "EC2": [
                {"hour": datetime(2025, 11, 13, 10, 0, 0), "cost": 1.00},
                {"hour": datetime(2025, 11, 13, 11, 0, 0), "cost": 1.50},
            ]
        }
        daily_service_costs = {"EC2": 10.00}

        _display_hourly_trends(hourly_service_costs, daily_service_costs)

        captured = capsys.readouterr()
        assert "HOURLY COST TRENDS" in captured.out
        assert "EC2" in captured.out
        assert "10:00" in captured.out
        assert "$1.000000" in captured.out

    def test_display_hourly_trends_no_data(self, capsys):
        """Test displaying hourly trends with no data."""
        _display_hourly_trends({}, {})

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_display_hourly_trends_top_five_only(self, capsys):
        """Test displaying only top 5 services."""
        hourly_service_costs = {f"Service{i}": [{"hour": datetime(2025, 11, 13, 10, 0, 0), "cost": 1.00}] for i in range(10)}
        daily_service_costs = {f"Service{i}": float(10 - i) for i in range(10)}

        _display_hourly_trends(hourly_service_costs, daily_service_costs)

        captured = capsys.readouterr()
        assert "Service0" in captured.out
        assert "Service9" not in captured.out
