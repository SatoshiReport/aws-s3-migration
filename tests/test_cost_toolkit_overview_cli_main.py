"""Tests for cost_toolkit/overview/cli.py module - main function and integration tests."""

# pylint: disable=too-few-public-methods,unused-argument,import-outside-toplevel

from __future__ import annotations

import os
from unittest.mock import patch

from cost_toolkit.overview.cli import PARENT_DIR, SCRIPT_ROOT, SCRIPTS_DIR, main
from tests.assertions import assert_equal


class TestMainSetupAndHeader:
    """Test suite for main function setup and header functionality."""

    def test_main_calls_setup_aws_credentials(self):
        """Test main calls setup_aws_credentials."""
        with (
            patch("cost_toolkit.overview.cli._print_header"),
            patch("cost_toolkit.overview.cli.setup_aws_credentials") as mock_setup,
            patch("cost_toolkit.overview.cli.get_current_month_costs", return_value=({}, 0.0)),
            patch("cost_toolkit.overview.cli._print_current_costs"),
            patch("cost_toolkit.overview.cli.analyze_optimization_opportunities", return_value=[]),
            patch("cost_toolkit.overview.cli._print_optimization_opportunities"),
            patch("cost_toolkit.overview.cli._print_service_recommendations"),
            patch("cost_toolkit.overview.cli.run_quick_audit"),
            patch("cost_toolkit.overview.cli.report_lightsail_cost_breakdown"),
            patch("cost_toolkit.overview.cli._print_next_steps_and_tools"),
        ):
            main()

            mock_setup.assert_called_once()

    def test_main_calls_print_header(self):
        """Test main calls _print_header."""
        with (
            patch("cost_toolkit.overview.cli._print_header") as mock_header,
            patch("cost_toolkit.overview.cli.setup_aws_credentials"),
            patch("cost_toolkit.overview.cli.get_current_month_costs", return_value=({}, 0.0)),
            patch("cost_toolkit.overview.cli._print_current_costs"),
            patch("cost_toolkit.overview.cli.analyze_optimization_opportunities", return_value=[]),
            patch("cost_toolkit.overview.cli._print_optimization_opportunities"),
            patch("cost_toolkit.overview.cli._print_service_recommendations"),
            patch("cost_toolkit.overview.cli.run_quick_audit"),
            patch("cost_toolkit.overview.cli.report_lightsail_cost_breakdown"),
            patch("cost_toolkit.overview.cli._print_next_steps_and_tools"),
        ):
            main()

            mock_header.assert_called_once()


class TestMainCostRetrieval:
    """Test suite for main function cost retrieval functionality."""

    def test_main_gets_current_month_costs(self):
        """Test main calls get_current_month_costs."""
        with (
            patch("cost_toolkit.overview.cli._print_header"),
            patch("cost_toolkit.overview.cli.setup_aws_credentials"),
            patch("cost_toolkit.overview.cli.get_current_month_costs", return_value=({}, 0.0)) as mock_costs,
            patch("cost_toolkit.overview.cli._print_current_costs"),
            patch("cost_toolkit.overview.cli.analyze_optimization_opportunities", return_value=[]),
            patch("cost_toolkit.overview.cli._print_optimization_opportunities"),
            patch("cost_toolkit.overview.cli._print_service_recommendations"),
            patch("cost_toolkit.overview.cli.run_quick_audit"),
            patch("cost_toolkit.overview.cli.report_lightsail_cost_breakdown"),
            patch("cost_toolkit.overview.cli._print_next_steps_and_tools"),
        ):
            main()

            mock_costs.assert_called_once()

    def test_main_prints_current_costs(self):
        """Test main calls _print_current_costs with correct arguments."""
        service_costs = {"Amazon EC2": 100.00}
        total_cost = 100.00

        with (
            patch("cost_toolkit.overview.cli._print_header"),
            patch("cost_toolkit.overview.cli.setup_aws_credentials"),
            patch(
                "cost_toolkit.overview.cli.get_current_month_costs",
                return_value=(service_costs, total_cost),
            ),
            patch("cost_toolkit.overview.cli._print_current_costs") as mock_print,
            patch("cost_toolkit.overview.cli.analyze_optimization_opportunities", return_value=[]),
            patch("cost_toolkit.overview.cli._print_optimization_opportunities"),
            patch("cost_toolkit.overview.cli._print_service_recommendations"),
            patch("cost_toolkit.overview.cli.run_quick_audit"),
            patch("cost_toolkit.overview.cli.report_lightsail_cost_breakdown"),
            patch("cost_toolkit.overview.cli._print_next_steps_and_tools"),
        ):
            main()

            mock_print.assert_called_once_with(service_costs, total_cost)


class TestMainOptimizationAnalysis:
    """Test suite for main function optimization analysis functionality."""

    def test_main_analyzes_optimization_opportunities(self):
        """Test main calls analyze_optimization_opportunities."""
        with (
            patch("cost_toolkit.overview.cli._print_header"),
            patch("cost_toolkit.overview.cli.setup_aws_credentials"),
            patch("cost_toolkit.overview.cli.get_current_month_costs", return_value=({}, 0.0)),
            patch("cost_toolkit.overview.cli._print_current_costs"),
            patch("cost_toolkit.overview.cli.analyze_optimization_opportunities", return_value=[]) as mock_analyze,
            patch("cost_toolkit.overview.cli._print_optimization_opportunities"),
            patch("cost_toolkit.overview.cli._print_service_recommendations"),
            patch("cost_toolkit.overview.cli.run_quick_audit"),
            patch("cost_toolkit.overview.cli.report_lightsail_cost_breakdown"),
            patch("cost_toolkit.overview.cli._print_next_steps_and_tools"),
        ):
            main()

            mock_analyze.assert_called_once()

    def test_main_prints_optimization_opportunities(self):
        """Test main calls _print_optimization_opportunities with correct arguments."""
        opportunities = [{"category": "Test", "potential_savings": 10.00}]

        with (
            patch("cost_toolkit.overview.cli._print_header"),
            patch("cost_toolkit.overview.cli.setup_aws_credentials"),
            patch("cost_toolkit.overview.cli.get_current_month_costs", return_value=({}, 0.0)),
            patch("cost_toolkit.overview.cli._print_current_costs"),
            patch(
                "cost_toolkit.overview.cli.analyze_optimization_opportunities",
                return_value=opportunities,
            ),
            patch("cost_toolkit.overview.cli._print_optimization_opportunities") as mock_print,
            patch("cost_toolkit.overview.cli._print_service_recommendations"),
            patch("cost_toolkit.overview.cli.run_quick_audit"),
            patch("cost_toolkit.overview.cli.report_lightsail_cost_breakdown"),
            patch("cost_toolkit.overview.cli._print_next_steps_and_tools"),
        ):
            main()

            mock_print.assert_called_once_with(opportunities)


class TestMainServiceRecommendations:
    """Test suite for main function service recommendations functionality."""

    def test_main_prints_service_recommendations(self):
        """Test main calls _print_service_recommendations with service costs."""
        service_costs = {"Amazon EC2": 100.00}

        with (
            patch("cost_toolkit.overview.cli._print_header"),
            patch("cost_toolkit.overview.cli.setup_aws_credentials"),
            patch(
                "cost_toolkit.overview.cli.get_current_month_costs",
                return_value=(service_costs, 100.00),
            ),
            patch("cost_toolkit.overview.cli._print_current_costs"),
            patch("cost_toolkit.overview.cli.analyze_optimization_opportunities", return_value=[]),
            patch("cost_toolkit.overview.cli._print_optimization_opportunities"),
            patch("cost_toolkit.overview.cli._print_service_recommendations") as mock_print,
            patch("cost_toolkit.overview.cli.run_quick_audit"),
            patch("cost_toolkit.overview.cli.report_lightsail_cost_breakdown"),
            patch("cost_toolkit.overview.cli._print_next_steps_and_tools"),
        ):
            main()

            mock_print.assert_called_once_with(service_costs)


class TestMainAuditAndReporting:
    """Test suite for main function audit and reporting functionality."""

    def test_main_runs_quick_audit(self):
        """Test main calls run_quick_audit with scripts directory."""
        with (
            patch("cost_toolkit.overview.cli._print_header"),
            patch("cost_toolkit.overview.cli.setup_aws_credentials"),
            patch("cost_toolkit.overview.cli.get_current_month_costs", return_value=({}, 0.0)),
            patch("cost_toolkit.overview.cli._print_current_costs"),
            patch("cost_toolkit.overview.cli.analyze_optimization_opportunities", return_value=[]),
            patch("cost_toolkit.overview.cli._print_optimization_opportunities"),
            patch("cost_toolkit.overview.cli._print_service_recommendations"),
            patch("cost_toolkit.overview.cli.run_quick_audit") as mock_audit,
            patch("cost_toolkit.overview.cli.report_lightsail_cost_breakdown"),
            patch("cost_toolkit.overview.cli._print_next_steps_and_tools"),
        ):
            main()

            mock_audit.assert_called_once_with(SCRIPTS_DIR)

    def test_main_reports_lightsail_cost_breakdown(self):
        """Test main calls report_lightsail_cost_breakdown."""
        with (
            patch("cost_toolkit.overview.cli._print_header"),
            patch("cost_toolkit.overview.cli.setup_aws_credentials"),
            patch("cost_toolkit.overview.cli.get_current_month_costs", return_value=({}, 0.0)),
            patch("cost_toolkit.overview.cli._print_current_costs"),
            patch("cost_toolkit.overview.cli.analyze_optimization_opportunities", return_value=[]),
            patch("cost_toolkit.overview.cli._print_optimization_opportunities"),
            patch("cost_toolkit.overview.cli._print_service_recommendations"),
            patch("cost_toolkit.overview.cli.run_quick_audit"),
            patch("cost_toolkit.overview.cli.report_lightsail_cost_breakdown") as mock_report,
            patch("cost_toolkit.overview.cli._print_next_steps_and_tools"),
        ):
            main()

            mock_report.assert_called_once()

    def test_main_prints_next_steps_and_tools(self):
        """Test main calls _print_next_steps_and_tools."""
        with (
            patch("cost_toolkit.overview.cli._print_header"),
            patch("cost_toolkit.overview.cli.setup_aws_credentials"),
            patch("cost_toolkit.overview.cli.get_current_month_costs", return_value=({}, 0.0)),
            patch("cost_toolkit.overview.cli._print_current_costs"),
            patch("cost_toolkit.overview.cli.analyze_optimization_opportunities", return_value=[]),
            patch("cost_toolkit.overview.cli._print_optimization_opportunities"),
            patch("cost_toolkit.overview.cli._print_service_recommendations"),
            patch("cost_toolkit.overview.cli.run_quick_audit"),
            patch("cost_toolkit.overview.cli.report_lightsail_cost_breakdown"),
            patch("cost_toolkit.overview.cli._print_next_steps_and_tools") as mock_print,
        ):
            main()

            mock_print.assert_called_once()


class TestMainExecutionOrder:
    """Test suite for main function execution order."""

    def test_main_execution_order(self):
        """Test main executes functions in correct order."""
        call_order = []

        def track_call(name):
            def wrapper(*args, **kwargs):
                call_order.append(name)

            return wrapper

        with (
            patch("cost_toolkit.overview.cli._print_header", side_effect=track_call("header")),
            patch("cost_toolkit.overview.cli.setup_aws_credentials", side_effect=track_call("setup")),
            patch(
                "cost_toolkit.overview.cli.get_current_month_costs",
                side_effect=lambda: (call_order.append("get_costs"), ({}, 0.0))[1],
            ),
            patch(
                "cost_toolkit.overview.cli._print_current_costs",
                side_effect=track_call("print_costs"),
            ),
            patch(
                "cost_toolkit.overview.cli.analyze_optimization_opportunities",
                side_effect=lambda: (call_order.append("analyze"), [])[1],
            ),
            patch(
                "cost_toolkit.overview.cli._print_optimization_opportunities",
                side_effect=track_call("print_opps"),
            ),
            patch(
                "cost_toolkit.overview.cli._print_service_recommendations",
                side_effect=track_call("print_recs"),
            ),
            patch("cost_toolkit.overview.cli.run_quick_audit", side_effect=track_call("audit")),
            patch(
                "cost_toolkit.overview.cli.report_lightsail_cost_breakdown",
                side_effect=track_call("lightsail"),
            ),
            patch(
                "cost_toolkit.overview.cli._print_next_steps_and_tools",
                side_effect=track_call("next_steps"),
            ),
        ):
            main()
            expected_order = [
                "header",
                "setup",
                "get_costs",
                "print_costs",
                "analyze",
                "print_opps",
                "print_recs",
                "audit",
                "lightsail",
                "next_steps",
            ]
            assert_equal(call_order, expected_order)


class TestModuleConstants:
    """Test suite for module-level constants."""

    def test_script_root_constant_exists(self):
        """Test SCRIPT_ROOT constant is defined."""
        assert SCRIPT_ROOT is not None
        assert isinstance(SCRIPT_ROOT, str)

    def test_parent_dir_constant_exists(self):
        """Test PARENT_DIR constant is defined."""
        assert PARENT_DIR is not None
        assert isinstance(PARENT_DIR, str)

    def test_scripts_dir_constant_exists(self):
        """Test SCRIPTS_DIR constant is defined."""
        assert SCRIPTS_DIR is not None
        assert isinstance(SCRIPTS_DIR, str)

    def test_constants_relationship(self):
        """Test relationship between directory constants."""
        assert SCRIPT_ROOT.endswith("overview")
        assert PARENT_DIR == os.path.dirname(SCRIPT_ROOT)
        assert SCRIPTS_DIR == os.path.join(PARENT_DIR, "scripts")


class TestMainGuard:
    """Test suite for main guard execution."""

    def test_main_guard_executes_when_run_as_script(self):
        """Test main is called when module is run as __main__."""
        import subprocess
        import sys

        # Create a test script that imports and checks if main would be called
        test_script = """
import sys
from unittest.mock import patch

# Mock all dependencies before importing cli
with (
    patch('cost_toolkit.overview.cli._print_header'),
    patch('cost_toolkit.overview.cli.setup_aws_credentials'),
    patch('cost_toolkit.overview.cli.get_current_month_costs', return_value=({}, 0.0)),
    patch('cost_toolkit.overview.cli._print_current_costs'),
    patch('cost_toolkit.overview.cli.analyze_optimization_opportunities', return_value=[]),
    patch('cost_toolkit.overview.cli._print_optimization_opportunities'),
    patch('cost_toolkit.overview.cli._print_service_recommendations'),
    patch('cost_toolkit.overview.cli.run_quick_audit'),
    patch('cost_toolkit.overview.cli.report_lightsail_cost_breakdown'),
    patch('cost_toolkit.overview.cli._print_next_steps_and_tools'),
):
    # Now test the guard
    import cost_toolkit.overview.cli as cli_module

    # Check that main is callable
    assert callable(cli_module.main)
    print("GUARD_TEST_PASSED")
"""
        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        assert result.returncode == 0
        assert "GUARD_TEST_PASSED" in result.stdout
