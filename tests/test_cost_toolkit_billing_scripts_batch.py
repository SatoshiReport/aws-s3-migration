"""Batch tests for cost_toolkit billing scripts."""

from __future__ import annotations

from cost_toolkit.scripts.billing import (
    aws_hourly_billing_report,
    aws_today_billing_report,
)
from cost_toolkit.scripts.billing.billing_report import (
    service_checks,
    service_checks_extended,
)


class TestAwsHourlyBillingReport:
    """Tests for aws_hourly_billing_report.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_hourly_billing_report is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_hourly_billing_report, "main")


class TestAwsTodayBillingReport:
    """Tests for aws_today_billing_report.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_today_billing_report is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_today_billing_report, "main")


class TestBillingReportModules:
    """Tests for billing_report sub-modules."""

    def test_service_checks_imports(self):
        """Test service_checks module can be imported."""
        assert service_checks is not None

    def test_service_checks_extended_imports(self):
        """Test service_checks_extended module can be imported."""
        assert service_checks_extended is not None
