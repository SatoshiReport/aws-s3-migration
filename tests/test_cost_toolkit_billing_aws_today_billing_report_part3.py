"""Comprehensive tests for aws_today_billing_report.py - Part 3 (Trend and Hourly Calculation)."""

from __future__ import annotations

from unittest.mock import MagicMock

from cost_toolkit.scripts.billing.aws_today_billing_report import (
    _calculate_hourly_info,
    _calculate_trend_indicator,
)


class TestCalculateTrendIndicator:
    """Tests for _calculate_trend_indicator function."""

    def test_calculate_trend_increasing(self):
        """Test trend indicator for increasing costs."""
        daily_trends = {
            "EC2": [
                {"date": "2025-11-11", "cost": 5.00},
                {"date": "2025-11-12", "cost": 8.00},
            ]
        }

        result = _calculate_trend_indicator("EC2", daily_trends, 10.00)

        assert "INCREASING" in result

    def test_calculate_trend_decreasing(self):
        """Test trend indicator for decreasing costs."""
        daily_trends = {
            "EC2": [
                {"date": "2025-11-11", "cost": 10.00},
                {"date": "2025-11-12", "cost": 8.00},
            ]
        }

        result = _calculate_trend_indicator("EC2", daily_trends, 6.00)

        assert "DECREASING" in result

    def test_calculate_trend_stable(self):
        """Test trend indicator for stable costs."""
        daily_trends = {
            "EC2": [
                {"date": "2025-11-11", "cost": 10.00},
                {"date": "2025-11-12", "cost": 10.00},
            ]
        }

        result = _calculate_trend_indicator("EC2", daily_trends, 10.00)

        assert "STABLE" in result

    def test_calculate_trend_no_data(self):
        """Test trend indicator with no data."""
        result = _calculate_trend_indicator("EC2", {}, 10.00)

        assert result == ""

    def test_calculate_trend_insufficient_data(self):
        """Test trend indicator with insufficient data points."""
        daily_trends = {"EC2": [{"date": "2025-11-12", "cost": 9.00}]}

        result = _calculate_trend_indicator("EC2", daily_trends, 10.00)

        assert result == ""


class TestCalculateHourlyInfo:
    """Tests for _calculate_hourly_info function."""

    def test_calculate_hourly_info_mid_day(self):
        """Test hourly info calculation mid-day."""
        mock_now = MagicMock()
        mock_now.hour = 12
        mock_now.minute = 0

        result = _calculate_hourly_info(6.00, mock_now)

        assert "0.500000/hr" in result
        assert "12.000000/day" in result

    def test_calculate_hourly_info_start_of_day(self):
        """Test hourly info calculation at start of day."""
        mock_now = MagicMock()
        mock_now.hour = 0
        mock_now.minute = 0

        result = _calculate_hourly_info(1.00, mock_now)

        assert result == ""

    def test_calculate_hourly_info_with_minutes(self):
        """Test hourly info calculation with partial hours."""
        mock_now = MagicMock()
        mock_now.hour = 6
        mock_now.minute = 30

        result = _calculate_hourly_info(6.50, mock_now)

        assert "/hr" in result
        assert "/day" in result
