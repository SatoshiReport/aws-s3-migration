"""Comprehensive tests for aws_today_billing_report.py - Part 2 (Display and Main)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.billing.aws_today_billing_report import (
    MIN_TREND_DATA_POINTS,
    MINIMUM_COST_THRESHOLD,
    _display_active_services,
    _display_optimization_insights,
    _display_service_usage_details,
    _get_service_recommendation,
    format_today_billing_report,
    main,
)


class TestDisplayServiceUsageDetails:
    """Tests for _display_service_usage_details function."""

    def test_display_service_usage_details_with_data(self, capsys):
        """Test displaying service usage details."""
        service_usage_details = {
            "EC2": [
                {"usage_type": "BoxUsage:t3.micro", "cost": 5.00, "quantity": 100, "unit": "Hrs"},
                {"usage_type": "DataTransfer", "cost": 2.00, "quantity": 50, "unit": "GB"},
            ]
        }

        _display_service_usage_details("EC2", service_usage_details, 10.00)

        captured = capsys.readouterr()
        assert "BoxUsage:t3.micro" in captured.out
        assert "$5.000000" in captured.out

    def test_display_service_usage_details_below_threshold(self, capsys):
        """Test not displaying details below cost threshold."""
        service_usage_details = {"EC2": [{"usage_type": "BoxUsage:t3.micro", "cost": 0.0005, "quantity": 1, "unit": "Hrs"}]}

        _display_service_usage_details("EC2", service_usage_details, 0.0001)

        captured = capsys.readouterr()
        assert "BoxUsage:t3.micro" not in captured.out

    def test_display_service_usage_details_no_data(self, capsys):
        """Test displaying usage details when no data exists."""
        service_usage_details = {}

        _display_service_usage_details("EC2", service_usage_details, 10.00)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_display_service_usage_details_top_three_only(self, capsys):
        """Test displaying only top 3 usage details."""
        service_usage_details = {
            "EC2": [
                {"usage_type": "Type1", "cost": 5.00, "quantity": 100, "unit": "Hrs"},
                {"usage_type": "Type2", "cost": 4.00, "quantity": 90, "unit": "Hrs"},
                {"usage_type": "Type3", "cost": 3.00, "quantity": 80, "unit": "Hrs"},
                {"usage_type": "Type4", "cost": 2.00, "quantity": 70, "unit": "Hrs"},
            ]
        }

        _display_service_usage_details("EC2", service_usage_details, 14.00)

        captured = capsys.readouterr()
        assert "Type1" in captured.out
        assert "Type2" in captured.out
        assert "Type3" in captured.out
        assert "Type4" not in captured.out


class TestDisplayActiveServices:
    """Tests for _display_active_services function."""

    def test_display_active_services_with_data(self, capsys):
        """Test displaying active services."""
        today_service_costs = {"EC2": 10.50, "S3": 5.25}
        daily_trends = {}
        service_usage_details = {}
        now = MagicMock()
        now.hour = 12
        now.minute = 0

        _display_active_services(today_service_costs, daily_trends, service_usage_details, now)

        captured = capsys.readouterr()
        assert "SERVICES GENERATING COSTS TODAY" in captured.out
        assert "EC2" in captured.out
        assert "$10.500000" in captured.out
        assert "S3" in captured.out
        assert "$5.250000" in captured.out

    def test_display_active_services_no_services(self, capsys):
        """Test displaying when no services are active."""
        today_service_costs = {}
        daily_trends = {}
        service_usage_details = {}
        now = MagicMock()

        _display_active_services(today_service_costs, daily_trends, service_usage_details, now)

        captured = capsys.readouterr()
        assert "NO SERVICES GENERATING COSTS TODAY" in captured.out
        assert "Excellent" in captured.out

    def test_display_active_services_sorted_by_cost(self, capsys):
        """Test services are displayed sorted by cost."""
        today_service_costs = {"S3": 5.25, "EC2": 10.50, "RDS": 2.00}
        daily_trends = {}
        service_usage_details = {}
        now = MagicMock()
        now.hour = 12
        now.minute = 0

        _display_active_services(today_service_costs, daily_trends, service_usage_details, now)

        captured = capsys.readouterr()
        ec2_pos = captured.out.find("EC2")
        s3_pos = captured.out.find("S3")
        rds_pos = captured.out.find("RDS")
        assert ec2_pos < s3_pos < rds_pos


class TestGetServiceRecommendation:
    """Tests for _get_service_recommendation function."""

    def test_get_recommendation_ec2(self):
        """Test EC2 service recommendation."""
        result = _get_service_recommendation("Amazon Elastic Compute Cloud - EC2")

        assert result is not None
        assert "instance" in result.lower() or "EC2" in result

    def test_get_recommendation_rds(self):
        """Test RDS service recommendation."""
        result = _get_service_recommendation("Amazon RDS Service")

        assert result is not None
        assert "database" in result.lower()

    def test_get_recommendation_s3(self):
        """Test S3 service recommendation."""
        result = _get_service_recommendation("Amazon S3")

        assert result is not None
        assert "storage" in result.lower()

    def test_get_recommendation_vpc(self):
        """Test VPC service recommendation."""
        result = _get_service_recommendation("Amazon VPC")

        assert result is not None
        assert "NAT" in result or "VPC" in result

    def test_get_recommendation_route53(self):
        """Test Route53 service recommendation."""
        result = _get_service_recommendation("Amazon Route 53")

        assert result is not None
        assert "hosted zones" in result.lower() or "DNS" in result

    def test_get_recommendation_unknown(self):
        """Test unknown service recommendation."""
        result = _get_service_recommendation("Unknown Service")

        assert result is None


class TestDisplayOptimizationInsights:
    """Tests for _display_optimization_insights function."""

    def test_display_optimization_insights_with_services(self, capsys):
        """Test displaying optimization insights."""
        today_service_costs = {"EC2": 10.00, "S3": 5.00}

        _display_optimization_insights(today_service_costs)

        captured = capsys.readouterr()
        assert "COST OPTIMIZATION INSIGHTS" in captured.out
        assert "EC2" in captured.out
        assert "Total daily cost to eliminate" in captured.out
        assert "MONTHLY PROJECTION" in captured.out

    def test_display_optimization_insights_no_services(self, capsys):
        """Test displaying insights with no services."""
        _display_optimization_insights({})

        captured = capsys.readouterr()
        assert "No active cost-generating services" in captured.out
        assert "optimally configured" in captured.out

    def test_display_optimization_insights_monthly_projection(self, capsys):
        """Test monthly projection calculation."""
        today_service_costs = {"EC2": 10.00}

        _display_optimization_insights(today_service_costs)

        captured = capsys.readouterr()
        assert "$300.00" in captured.out


class TestFormatTodayBillingReport:
    """Tests for format_today_billing_report function."""

    @patch("cost_toolkit.scripts.billing.aws_today_billing_report.datetime")
    def test_format_report_with_data(self, mock_datetime, capsys):
        """Test formatting report with billing data."""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2025-11-13 12:00:00"
        mock_now.hour = 12
        mock_now.minute = 0
        mock_datetime.now.return_value = mock_now

        today_data = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {"Keys": ["EC2"], "Metrics": {"BlendedCost": {"Amount": "10.00"}}},
                    ]
                }
            ]
        }
        trend_data = {"ResultsByTime": []}
        usage_data = {"ResultsByTime": []}

        format_today_billing_report(today_data, trend_data, usage_data)

        captured = capsys.readouterr()
        assert "TODAY'S AWS BILLING REPORT" in captured.out
        assert "EC2" in captured.out

    def test_format_report_no_data(self, capsys):
        """Test formatting report with no data."""
        format_today_billing_report(None, None, None)

        captured = capsys.readouterr()
        assert "No billing data available" in captured.out

    def test_format_report_empty_results(self, capsys):
        """Test formatting report with empty results."""
        today_data = {}

        format_today_billing_report(today_data, {}, {})

        captured = capsys.readouterr()
        assert "No billing data available" in captured.out


class TestMain:
    """Tests for main function."""

    def test_main_success(self, capsys):
        """Test main function successful execution."""
        mod = "cost_toolkit.scripts.billing.aws_today_billing_report"
        with (
            patch(f"{mod}.clear_screen") as mock_clear_screen,
            patch(f"{mod}.check_aws_credentials") as mock_check_creds,
            patch(f"{mod}.get_today_billing_data") as mock_get_data,
            patch(f"{mod}.format_today_billing_report") as mock_format_report,
        ):
            mock_check_creds.return_value = True
            mock_get_data.return_value = ({"ResultsByTime": []}, {}, {})

            main()

            mock_clear_screen.assert_called_once()
            mock_get_data.assert_called_once()
            mock_format_report.assert_called_once()

            captured = capsys.readouterr()
            assert "AWS TODAY'S BILLING REPORT" in captured.out

    @patch("cost_toolkit.scripts.billing.aws_today_billing_report.clear_screen")
    @patch("cost_toolkit.scripts.billing.aws_today_billing_report.check_aws_credentials")
    def test_main_no_credentials(self, mock_check_creds, mock_clear_screen):
        """Test main function with no credentials."""
        mock_check_creds.return_value = False

        main()

        mock_clear_screen.assert_called_once()

    @patch("cost_toolkit.scripts.billing.aws_today_billing_report.clear_screen")
    @patch("cost_toolkit.scripts.billing.aws_today_billing_report.check_aws_credentials")
    @patch("cost_toolkit.scripts.billing.aws_today_billing_report.get_today_billing_data")
    def test_main_failed_data_retrieval(self, mock_get_data, mock_check_creds, _mock_clear_screen, capsys):
        """Test main function with failed data retrieval."""
        mock_check_creds.return_value = True
        mock_get_data.return_value = (None, None, None)

        main()

        captured = capsys.readouterr()
        assert "Failed to retrieve billing data" in captured.out


class TestConstants:
    """Tests for module constants."""

    def test_min_trend_data_points_constant(self):
        """Test MIN_TREND_DATA_POINTS constant."""
        assert MIN_TREND_DATA_POINTS == 2

    def test_minimum_cost_threshold_constant(self):
        """Test MINIMUM_COST_THRESHOLD constant."""
        assert MINIMUM_COST_THRESHOLD == 0.001
