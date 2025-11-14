"""Comprehensive tests for verify_iwannabenewyork_domain.py - Part 3."""

from __future__ import annotations

from unittest.mock import patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.setup.verify_iwannabenewyork_domain import (
    _print_overall_status,
    _print_summary,
    _run_tests,
    main,
)


class TestPrintSummary:
    """Tests for _print_summary function."""

    def test_print_summary_all_passed(self, capsys):
        """Test summary with all tests passed."""
        results = [("Test 1", True), ("Test 2", True), ("Test 3", True)]

        passed, failed = _print_summary(results, "example.com")

        assert len(passed) == 3
        assert len(failed) == 0
        captured = capsys.readouterr()
        assert "Passed tests: 3/3" in captured.out

    def test_print_summary_some_failed(self, capsys):
        """Test summary with some failed tests."""
        results = [("Test 1", True), ("Test 2", False), ("Test 3", True)]

        passed, failed = _print_summary(results, "example.com")

        assert len(passed) == 2
        assert len(failed) == 1
        assert "Test 2" in failed
        captured = capsys.readouterr()
        assert "Passed tests: 2/3" in captured.out
        assert "Failed tests: 1" in captured.out


class TestPrintOverallStatus:
    """Tests for _print_overall_status function."""

    def test_all_tests_passed(self, capsys):
        """Test overall status when all tests pass."""
        passed_tests = ["Test 1", "Test 2", "Test 3"]
        failed_tests = []

        _print_overall_status("example.com", passed_tests, failed_tests, 3)

        captured = capsys.readouterr()
        assert "SUCCESS" in captured.out
        assert "fully configured and working" in captured.out

    def test_mostly_working(self, capsys):
        """Test overall status when mostly working."""
        passed_tests = ["Test 1", "Test 2", "Test 3", "Test 4"]
        failed_tests = ["Test 5"]

        _print_overall_status("example.com", passed_tests, failed_tests, 5)

        captured = capsys.readouterr()
        assert "MOSTLY WORKING" in captured.out

    def test_significant_issues(self, capsys):
        """Test overall status with significant issues."""
        passed_tests = ["Test 1"]
        failed_tests = ["Test 2", "Test 3", "Test 4"]

        _print_overall_status("example.com", passed_tests, failed_tests, 4)

        captured = capsys.readouterr()
        assert "ISSUES DETECTED" in captured.out


class TestRunTests:
    """Tests for _run_tests function."""

    def test_run_all_tests_success(self):
        """Test running all tests successfully."""
        mod = "cost_toolkit.scripts.setup.verify_iwannabenewyork_domain"
        with (
            patch(f"{mod}.verify_dns_resolution") as mock_dns,
            patch(f"{mod}.verify_http_connectivity") as mock_http,
            patch(f"{mod}.verify_https_connectivity") as mock_https,
            patch(f"{mod}.check_ssl_certificate") as mock_ssl,
            patch(f"{mod}.verify_canva_verification") as mock_canva,
            patch(f"{mod}.check_route53_configuration") as mock_route53,
        ):
            mock_dns.return_value = (True, "192.168.1.1")
            mock_http.return_value = True
            mock_https.return_value = True
            mock_ssl.return_value = True
            mock_canva.return_value = True
            mock_route53.return_value = True

            results = _run_tests("example.com")

            assert len(results) == 6
            assert all(success for _, success in results)

    def test_run_tests_with_failures(self):
        """Test running tests with some failures."""
        mod = "cost_toolkit.scripts.setup.verify_iwannabenewyork_domain"
        with (
            patch(f"{mod}.verify_dns_resolution") as mock_dns,
            patch(f"{mod}.verify_http_connectivity") as mock_http,
            patch(f"{mod}.verify_https_connectivity"),
            patch(f"{mod}.check_ssl_certificate"),
            patch(f"{mod}.verify_canva_verification"),
            patch(f"{mod}.check_route53_configuration"),
        ):
            mock_dns.return_value = (False, None)
            mock_http.side_effect = ClientError(
                {"Error": {"Code": "Error", "Message": "Error"}}, "test"
            )

            results = _run_tests("example.com")

        assert len(results) == 6
        assert results[0][1] is False
        assert results[1][1] is False


class TestMain:
    """Tests for main function."""

    @patch("cost_toolkit.scripts.setup.verify_iwannabenewyork_domain._run_tests")
    @patch("cost_toolkit.scripts.setup.verify_iwannabenewyork_domain._print_summary")
    @patch("cost_toolkit.scripts.setup.verify_iwannabenewyork_domain._print_overall_status")
    def test_main_all_tests_pass(self, _mock_status, mock_summary, mock_run_tests):
        """Test main function with all tests passing."""
        mock_run_tests.return_value = [("Test 1", True), ("Test 2", True)]
        mock_summary.return_value = (["Test 1", "Test 2"], [])

        result = main()

        assert result == 0

    @patch("cost_toolkit.scripts.setup.verify_iwannabenewyork_domain._run_tests")
    @patch("cost_toolkit.scripts.setup.verify_iwannabenewyork_domain._print_summary")
    @patch("cost_toolkit.scripts.setup.verify_iwannabenewyork_domain._print_overall_status")
    def test_main_some_tests_fail(self, _mock_status, mock_summary, mock_run_tests):
        """Test main function with some tests failing."""
        mock_run_tests.return_value = [("Test 1", True), ("Test 2", False)]
        mock_summary.return_value = (["Test 1"], ["Test 2"])

        result = main()

        assert result == 1
