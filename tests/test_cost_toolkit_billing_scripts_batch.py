"""Batch tests for cost_toolkit billing scripts."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestAwsHourlyBillingReport:
    """Tests for aws_hourly_billing_report.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.billing import aws_hourly_billing_report

        assert aws_hourly_billing_report is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        from cost_toolkit.scripts.billing import aws_hourly_billing_report

        assert hasattr(aws_hourly_billing_report, "main")


class TestAwsTodayBillingReport:
    """Tests for aws_today_billing_report.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.billing import aws_today_billing_report

        assert aws_today_billing_report is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        from cost_toolkit.scripts.billing import aws_today_billing_report

        assert hasattr(aws_today_billing_report, "main")


class TestBillingReportServiceChecks:
    """Tests for billing_report/service_checks.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.billing.billing_report import service_checks

        assert service_checks is not None


class TestBillingReportServiceChecksExtended:
    """Tests for billing_report/service_checks_extended.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.billing.billing_report import service_checks_extended

        assert service_checks_extended is not None
