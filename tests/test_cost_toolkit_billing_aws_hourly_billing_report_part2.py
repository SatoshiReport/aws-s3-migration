"""Comprehensive tests for aws_hourly_billing_report.py - Part 2 (Display and Main)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.billing.aws_hourly_billing_report import (
    _display_optimization_insights,
    format_hourly_billing_report,
    main,
)


class TestDisplayOptimizationInsights:
    """Tests for _display_optimization_insights function."""

    def test_display_optimization_insights_with_current_services(self, capsys):
        """Test displaying optimization insights with current hour services."""
        current_hour_costs = {"EC2": 1.50, "S3": 0.75}
        daily_service_costs = {"EC2": 10.00, "S3": 5.00}

        _display_optimization_insights(current_hour_costs, daily_service_costs)

        captured = capsys.readouterr()
        assert "COST OPTIMIZATION INSIGHTS" in captured.out
        assert "Services currently generating costs" in captured.out
        assert "EC2" in captured.out
        assert "$1.500000 this hour" in captured.out

    def test_display_optimization_insights_no_current_services(self, capsys):
        """Test displaying insights with no current hour services."""
        current_hour_costs = {}
        daily_service_costs = {"EC2": 10.00}

        _display_optimization_insights(current_hour_costs, daily_service_costs)

        captured = capsys.readouterr()
        assert "No services generating costs in the current hour" in captured.out
        assert "cleanup efforts are working" in captured.out

    def test_display_optimization_insights_earlier_services(self, capsys):
        """Test displaying services active earlier but not in current hour."""
        current_hour_costs = {"EC2": 1.50}
        daily_service_costs = {"EC2": 10.00, "S3": 5.00, "RDS": 2.00}

        _display_optimization_insights(current_hour_costs, daily_service_costs)

        captured = capsys.readouterr()
        assert "Services active earlier today but not in current hour" in captured.out
        assert "S3" in captured.out
        assert "RDS" in captured.out

    def test_display_optimization_insights_sorted_by_cost(self, capsys):
        """Test insights display services sorted by cost."""
        current_hour_costs = {"S3": 0.50, "EC2": 1.50, "RDS": 0.25}
        daily_service_costs = {"EC2": 10.00, "S3": 5.00, "RDS": 2.00}

        _display_optimization_insights(current_hour_costs, daily_service_costs)

        captured = capsys.readouterr()
        ec2_pos = captured.out.find("EC2: $1.500000")
        s3_pos = captured.out.find("S3: $0.500000")
        rds_pos = captured.out.find("RDS: $0.250000")
        assert ec2_pos < s3_pos < rds_pos


class TestFormatHourlyBillingReport:
    """Tests for format_hourly_billing_report function."""

    @patch("cost_toolkit.scripts.billing.aws_hourly_billing_report.datetime")
    def test_format_report_with_data(self, mock_datetime_module, capsys):
        """Test formatting report with billing data."""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2025-11-13 12:30:00"
        mock_now.replace.return_value = datetime(2025, 11, 13, 12, 0, 0)
        mock_now.hour = 12
        mock_now.minute = 30
        mock_datetime_module.now.return_value = mock_now

        hourly_data = {
            "ResultsByTime": [
                {
                    "TimePeriod": {
                        "Start": "2025-11-13T12:00:00Z",
                        "End": "2025-11-13T13:00:00Z",
                    },
                    "Groups": [{"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "1.50"}}}],
                }
            ]
        }
        daily_data = {
            "ResultsByTime": [
                {"Groups": [{"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "10.00"}}}]}
            ]
        }

        format_hourly_billing_report(hourly_data, daily_data)

        captured = capsys.readouterr()
        assert "HOURLY AWS BILLING REPORT" in captured.out
        assert "EC2" in captured.out

    def test_format_report_no_data(self, capsys):
        """Test formatting report with no data."""
        format_hourly_billing_report(None, None)

        captured = capsys.readouterr()
        assert "No hourly billing data available" in captured.out

    def test_format_report_empty_results(self, capsys):
        """Test formatting report with empty results."""
        hourly_data = {}

        format_hourly_billing_report(hourly_data, {})

        captured = capsys.readouterr()
        assert "No hourly billing data available" in captured.out

    @patch("cost_toolkit.scripts.billing.aws_hourly_billing_report.datetime")
    def test_format_report_calls_all_display_functions(self, mock_datetime_module, capsys):
        """Test report calls all display functions."""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2025-11-13 12:30:00"
        mock_now.replace.return_value = datetime(2025, 11, 13, 12, 0, 0)
        mock_now.hour = 12
        mock_now.minute = 30
        mock_datetime_module.now.return_value = mock_now

        hourly_data = {
            "ResultsByTime": [
                {
                    "TimePeriod": {
                        "Start": "2025-11-13T12:00:00Z",
                        "End": "2025-11-13T13:00:00Z",
                    },
                    "Groups": [{"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "1.50"}}}],
                }
            ]
        }
        daily_data = {
            "ResultsByTime": [
                {"Groups": [{"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "10.00"}}}]}
            ]
        }

        format_hourly_billing_report(hourly_data, daily_data)

        captured = capsys.readouterr()
        assert "ACTIVE SERVICES IN CURRENT HOUR" in captured.out
        assert "TODAY'S COST SUMMARY BY SERVICE" in captured.out
        assert "HOURLY COST TRENDS" in captured.out
        assert "COST OPTIMIZATION INSIGHTS" in captured.out


class TestMain:
    """Tests for main function."""

    def test_main_success(self, capsys):
        """Test main function successful execution."""
        mod = "cost_toolkit.scripts.billing.aws_hourly_billing_report"
        with (
            patch(f"{mod}.clear_screen") as mock_clear_screen,
            patch(f"{mod}.get_hourly_billing_data") as mock_get_data,
            patch(f"{mod}.format_hourly_billing_report") as mock_format_report,
        ):
            mock_get_data.return_value = ({"ResultsByTime": []}, {"ResultsByTime": []})

            main()

            mock_clear_screen.assert_called_once()
            mock_get_data.assert_called_once()
            mock_format_report.assert_called_once()

            captured = capsys.readouterr()
            assert "AWS HOURLY BILLING REPORT" in captured.out

    @patch("cost_toolkit.scripts.billing.aws_hourly_billing_report.clear_screen")
    def test_main_no_credentials(self, mock_clear_screen):
        """Test main function with no credentials."""
        main()

        mock_clear_screen.assert_called_once()

    @patch("cost_toolkit.scripts.billing.aws_hourly_billing_report.clear_screen")
    @patch("cost_toolkit.scripts.billing.aws_hourly_billing_report.get_hourly_billing_data")
    def test_main_failed_data_retrieval(self, mock_get_data, _mock_clear_screen, capsys):
        """Test main function with failed data retrieval."""
        mock_get_data.return_value = (None, None)

        main()

        captured = capsys.readouterr()
        assert "Failed to retrieve billing data" in captured.out

    def test_main_partial_data_failure(self, capsys):
        """Test main function with partial data retrieval."""
        mod = "cost_toolkit.scripts.billing.aws_hourly_billing_report"
        with (
            patch(f"{mod}.clear_screen"),
            patch(f"{mod}.get_hourly_billing_data") as mock_get_data,
            patch(f"{mod}.format_hourly_billing_report") as mock_format_report,
        ):
            mock_get_data.return_value = ({"ResultsByTime": []}, None)

            main()

            mock_format_report.assert_not_called()
            captured = capsys.readouterr()
            assert "Failed to retrieve billing data" in captured.out

    def test_main_displays_usage_tips(self, capsys):
        """Test main function displays usage tips."""
        mod = "cost_toolkit.scripts.billing.aws_hourly_billing_report"
        with (
            patch(f"{mod}.clear_screen"),
            patch(f"{mod}.get_hourly_billing_data") as mock_get_data,
            patch(f"{mod}.format_hourly_billing_report"),
        ):
            mock_get_data.return_value = ({"ResultsByTime": []}, {"ResultsByTime": []})

            main()

            captured = capsys.readouterr()
            assert "identify services still generating costs" in captured.out
            assert "Focus cleanup efforts" in captured.out
