"""Tests for cost_toolkit/overview/cli.py module - display and formatting functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cost_toolkit.overview.cli import (
    _print_current_costs,
    _print_header,
    _print_next_steps_and_tools,
    _print_optimization_opportunities,
    _print_service_recommendations,
)


class TestPrintHeader:
    """Test suite for _print_header function."""

    def test_print_header_outputs_title(self, capsys):
        """Test _print_header outputs correct title."""
        _print_header()

        captured = capsys.readouterr()
        assert "AWS Cost Management Overview" in captured.out

    def test_print_header_outputs_separator(self, capsys):
        """Test _print_header outputs separator lines."""
        _print_header()

        captured = capsys.readouterr()
        assert "=" * 80 in captured.out

    def test_print_header_outputs_timestamp(self, capsys):
        """Test _print_header outputs generated timestamp."""
        with patch("cost_toolkit.overview.cli.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2025-11-12 10:30:00"
            _print_header()

            captured = capsys.readouterr()
            assert "Generated: 2025-11-12 10:30:00" in captured.out

    def test_print_header_calls_datetime_now(self):
        """Test _print_header calls datetime.now()."""
        with patch("cost_toolkit.overview.cli.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_datetime.now.return_value = mock_now

            _print_header()

            mock_datetime.now.assert_called_once()
            mock_now.strftime.assert_called_once_with("%Y-%m-%d %H:%M:%S")


class TestPrintCurrentCostsBasic:
    """Test suite for _print_current_costs basic functionality."""

    def test_print_current_costs_with_costs(self, capsys):
        """Test _print_current_costs with valid cost data."""
        service_costs = {"Amazon EC2": 150.75, "Amazon S3": 25.50, "Amazon RDS": 50.00}
        total_cost = 226.25

        _print_current_costs(service_costs, total_cost)

        captured = capsys.readouterr()
        assert "CURRENT MONTH COSTS" in captured.out
        assert "$226.25" in captured.out
        assert "Amazon EC2" in captured.out
        assert "Amazon S3" in captured.out
        assert "Amazon RDS" in captured.out

    def test_print_current_costs_shows_percentages(self, capsys):
        """Test _print_current_costs displays cost percentages."""
        service_costs = {"Amazon EC2": 80.00, "Amazon S3": 20.00}
        total_cost = 100.00

        _print_current_costs(service_costs, total_cost)

        captured = capsys.readouterr()
        assert "80.0%" in captured.out
        assert "20.0%" in captured.out

    def test_print_current_costs_formats_currency(self, capsys):
        """Test _print_current_costs formats currency correctly."""
        service_costs = {"Amazon EC2": 1234.567}
        total_cost = 1234.567

        _print_current_costs(service_costs, total_cost)

        captured = capsys.readouterr()
        assert "$1234.57" in captured.out


class TestPrintCurrentCostsSorting:
    """Test suite for _print_current_costs sorting and filtering."""

    def test_print_current_costs_limits_to_top_10(self, capsys):
        """Test _print_current_costs shows only top 10 services."""
        service_costs = {f"Service {i}": float(i * 10) for i in range(15)}
        total_cost = sum(service_costs.values())

        _print_current_costs(service_costs, total_cost)

        captured = capsys.readouterr()
        # Top services should be present
        assert "Service 14" in captured.out
        # Lower services should not be present
        assert "Service 0" not in captured.out

    def test_print_current_costs_sorts_by_cost_descending(self, capsys):
        """Test _print_current_costs sorts services by cost in descending order."""
        service_costs = {"Amazon S3": 10.00, "Amazon EC2": 100.00, "Amazon RDS": 50.00}
        total_cost = 160.00

        _print_current_costs(service_costs, total_cost)

        captured = capsys.readouterr()
        output_lines = captured.out.split("\n")

        # Find the position of each service in output
        ec2_pos = next(i for i, line in enumerate(output_lines) if "Amazon EC2" in line)
        rds_pos = next(i for i, line in enumerate(output_lines) if "Amazon RDS" in line)
        s3_pos = next(i for i, line in enumerate(output_lines) if "Amazon S3" in line)

        # Verify order: EC2 ($100) should come before RDS ($50) before S3 ($10)
        assert ec2_pos < rds_pos < s3_pos


class TestPrintCurrentCostsEdgeCases:
    """Test suite for _print_current_costs edge cases."""

    def test_print_current_costs_with_zero_total(self, capsys):
        """Test _print_current_costs when total cost is zero."""
        service_costs = {}
        total_cost = 0.0

        _print_current_costs(service_costs, total_cost)

        captured = capsys.readouterr()
        assert "No cost data available" in captured.out

    def test_print_current_costs_with_empty_dict(self, capsys):
        """Test _print_current_costs with empty service costs."""
        _print_current_costs({}, 0.0)

        captured = capsys.readouterr()
        assert "No cost data available" in captured.out


class TestPrintOptimizationOpportunitiesBasic:
    """Test suite for _print_optimization_opportunities basic functionality."""

    def test_print_optimization_opportunities_with_opportunities(self, capsys):
        """Test _print_optimization_opportunities with valid opportunities."""
        opportunities = [
            {
                "category": "EBS Optimization",
                "description": "5 unattached EBS volumes",
                "potential_savings": 100.00,
                "risk": "Low",
                "action": "Delete unused volumes",
            }
        ]

        _print_optimization_opportunities(opportunities)

        captured = capsys.readouterr()
        assert "OPTIMIZATION OPPORTUNITIES" in captured.out
        assert "EBS Optimization" in captured.out
        assert "$100.00" in captured.out
        assert "Low" in captured.out
        assert "Delete unused volumes" in captured.out

    def test_print_optimization_opportunities_empty_list(self, capsys):
        """Test _print_optimization_opportunities with empty opportunities list."""
        _print_optimization_opportunities([])

        captured = capsys.readouterr()
        assert "No immediate optimization opportunities identified" in captured.out

    def test_print_optimization_opportunities_shows_all_fields(self, capsys):
        """Test _print_optimization_opportunities displays all opportunity fields."""
        opportunities = [
            {
                "category": "Test Category",
                "description": "Test Description",
                "potential_savings": 42.50,
                "risk": "Medium",
                "action": "Test Action",
            }
        ]

        _print_optimization_opportunities(opportunities)

        captured = capsys.readouterr()
        assert "Test Category" in captured.out
        assert "Test Description" in captured.out
        assert "$42.50" in captured.out
        assert "Medium" in captured.out
        assert "Test Action" in captured.out


class TestPrintOptimizationOpportunitiesCalculations:
    """Test suite for _print_optimization_opportunities calculations and sorting."""

    def test_print_optimization_opportunities_calculates_total_savings(self, capsys):
        """Test _print_optimization_opportunities calculates total savings."""
        opportunities = [
            {
                "category": "EBS",
                "description": "Test",
                "potential_savings": 50.00,
                "risk": "Low",
                "action": "Fix",
            },
            {
                "category": "S3",
                "description": "Test",
                "potential_savings": 30.00,
                "risk": "Low",
                "action": "Fix",
            },
        ]
        _print_optimization_opportunities(opportunities)
        captured = capsys.readouterr()
        assert "$80.00" in captured.out

    def test_print_optimization_opportunities_sorts_by_savings(self, capsys):
        """Test _print_optimization_opportunities sorts by savings descending."""
        opportunities = [
            {
                "category": "Small",
                "description": "Test",
                "potential_savings": 10.00,
                "risk": "Low",
                "action": "Fix",
            },
            {
                "category": "Large",
                "description": "Test",
                "potential_savings": 100.00,
                "risk": "Low",
                "action": "Fix",
            },
            {
                "category": "Medium",
                "description": "Test",
                "potential_savings": 50.00,
                "risk": "Low",
                "action": "Fix",
            },
        ]
        _print_optimization_opportunities(opportunities)
        captured = capsys.readouterr()
        output_lines = captured.out.split("\n")
        large_pos = next(i for i, line in enumerate(output_lines) if "Large" in line)
        medium_pos = next(i for i, line in enumerate(output_lines) if "Medium" in line)
        small_pos = next(i for i, line in enumerate(output_lines) if "Small" in line)
        assert large_pos < medium_pos < small_pos


class TestPrintServiceRecommendations:
    """Test suite for _print_service_recommendations function."""

    def test_print_service_recommendations_with_costs(self, capsys):
        """Test _print_service_recommendations with valid service costs."""
        service_costs = {"Amazon EC2": 100.00, "Amazon S3": 50.00}
        with patch(
            "cost_toolkit.overview.cli.get_service_recommendations",
            return_value=["Recommendation 1", "Recommendation 2"],
        ):
            _print_service_recommendations(service_costs)
            captured = capsys.readouterr()
            assert "SERVICE-SPECIFIC RECOMMENDATIONS" in captured.out
            assert "Recommendation 1" in captured.out
            assert "Recommendation 2" in captured.out

    def test_print_service_recommendations_calls_get_service_recommendations(self):
        """Test _print_service_recommendations calls get_service_recommendations."""
        service_costs = {"Amazon EC2": 100.00}
        with patch(
            "cost_toolkit.overview.cli.get_service_recommendations", return_value=[]
        ) as mock_get:
            _print_service_recommendations(service_costs)
            mock_get.assert_called_once_with(service_costs)

    def test_print_service_recommendations_with_empty_costs(self):
        """Test _print_service_recommendations with empty service costs returns early."""
        with patch("cost_toolkit.overview.cli.get_service_recommendations") as mock_get:
            _print_service_recommendations({})
            mock_get.assert_not_called()

    def test_print_service_recommendations_with_none(self):
        """Test _print_service_recommendations with None returns early."""
        with patch("cost_toolkit.overview.cli.get_service_recommendations") as mock_get:
            _print_service_recommendations(None)
            mock_get.assert_not_called()

    def test_print_service_recommendations_no_recommendations(self, capsys):
        """Test _print_service_recommendations when no recommendations returned."""
        service_costs = {"Amazon EC2": 100.00}
        with patch("cost_toolkit.overview.cli.get_service_recommendations", return_value=[]):
            _print_service_recommendations(service_costs)
            captured = capsys.readouterr()
            assert "No specific service recommendations" in captured.out

    def test_print_service_recommendations_multiple_recommendations(self, capsys):
        """Test _print_service_recommendations with multiple recommendations."""
        service_costs = {"Amazon EC2": 100.00}
        recommendations = ["Rec 1", "Rec 2", "Rec 3"]
        with patch(
            "cost_toolkit.overview.cli.get_service_recommendations", return_value=recommendations
        ):
            _print_service_recommendations(service_costs)
            captured = capsys.readouterr()
            for rec in recommendations:
                assert rec in captured.out


class TestPrintNextStepsAndTools:
    """Test suite for _print_next_steps_and_tools function."""

    def test_print_next_steps_and_tools_outputs_next_steps(self, capsys):
        """Test _print_next_steps_and_tools outputs next steps section."""
        _print_next_steps_and_tools()

        captured = capsys.readouterr()
        assert "RECOMMENDED NEXT STEPS" in captured.out

    def test_print_next_steps_and_tools_outputs_tools(self, capsys):
        """Test _print_next_steps_and_tools outputs available tools section."""
        _print_next_steps_and_tools()

        captured = capsys.readouterr()
        assert "AVAILABLE TOOLS" in captured.out

    def test_print_next_steps_and_tools_mentions_audit_scripts(self, capsys):
        """Test _print_next_steps_and_tools mentions audit scripts."""
        _print_next_steps_and_tools()

        captured = capsys.readouterr()
        assert "audit" in captured.out.lower()

    def test_print_next_steps_and_tools_mentions_cleanup_scripts(self, capsys):
        """Test _print_next_steps_and_tools mentions cleanup scripts."""
        _print_next_steps_and_tools()

        captured = capsys.readouterr()
        assert "cleanup" in captured.out.lower()

    def test_print_next_steps_and_tools_mentions_migration(self, capsys):
        """Test _print_next_steps_and_tools mentions migration tools."""
        _print_next_steps_and_tools()

        captured = capsys.readouterr()
        assert "migration" in captured.out.lower()

    def test_print_next_steps_and_tools_mentions_billing(self, capsys):
        """Test _print_next_steps_and_tools mentions billing reports."""
        _print_next_steps_and_tools()

        captured = capsys.readouterr()
        assert "billing" in captured.out.lower()

    def test_print_next_steps_and_tools_mentions_readme(self, capsys):
        """Test _print_next_steps_and_tools mentions README documentation."""
        _print_next_steps_and_tools()

        captured = capsys.readouterr()
        assert "README.md" in captured.out
