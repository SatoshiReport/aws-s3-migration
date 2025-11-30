"""Comprehensive tests for aws_ec2_usage_audit.py."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_ec2_usage_audit import (  # pyright: ignore[reportPrivateUsage]
    _calculate_cpu_metrics,
    _determine_usage_level,
    _estimate_monthly_cost,
    _get_network_metrics,
    _print_cpu_metrics,
    _process_instance_details,
)


class TestCalculateCpuMetrics:
    """Tests for _calculate_cpu_metrics function."""

    def test_calculate_cpu_metrics_success(self):
        """Test successful CPU metric calculation."""
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.return_value = {
            "Datapoints": [
                {
                    "Timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                    "Average": 10.0,
                    "Maximum": 20.0,
                },
                {
                    "Timestamp": datetime(2024, 1, 2, tzinfo=timezone.utc),
                    "Average": 15.0,
                    "Maximum": 25.0,
                },
            ]
        }

        avg_cpu, max_cpu, latest = _calculate_cpu_metrics(mock_cloudwatch, "i-123")

        assert avg_cpu == 12.5
        assert max_cpu == 25.0
        assert latest["Average"] == 15.0

    def test_calculate_cpu_metrics_no_data(self):
        """Test CPU metrics with no datapoints."""
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.return_value = {"Datapoints": []}

        avg_cpu, max_cpu, latest = _calculate_cpu_metrics(mock_cloudwatch, "i-123")

        assert avg_cpu is None
        assert max_cpu is None
        assert latest is None

    def test_calculate_cpu_metrics_error(self, capsys):
        """Test CPU metrics with error."""
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "get_metric_statistics"
        )

        avg_cpu, max_cpu, latest = _calculate_cpu_metrics(mock_cloudwatch, "i-123")

        assert avg_cpu is None
        assert max_cpu is None
        assert latest is None
        captured = capsys.readouterr()
        assert "Error getting metrics" in captured.out


class TestDetermineUsageLevel:
    """Tests for _determine_usage_level function."""

    def test_usage_level_no_data(self):
        """Test usage level with no data."""
        result = _determine_usage_level(None)

        assert result == "❓ NO DATA"

    def test_usage_level_very_low(self):
        """Test very low usage level."""
        result = _determine_usage_level(0.5)

        assert "VERY LOW" in result
        assert "<1%" in result

    def test_usage_level_low(self):
        """Test low usage level."""
        result = _determine_usage_level(3.0)

        assert "LOW" in result
        assert "<5%" in result

    def test_usage_level_moderate(self):
        """Test moderate usage level."""
        result = _determine_usage_level(10.0)

        assert "MODERATE" in result

    def test_usage_level_high(self):
        """Test high usage level."""
        result = _determine_usage_level(25.0)

        assert "HIGH" in result
        assert ">20%" in result


class TestPrintCpuMetrics:
    """Tests for _print_cpu_metrics function."""

    def test_print_cpu_metrics_with_data(self, capsys):
        """Test printing CPU metrics with valid data."""
        latest_datapoint = {
            "Timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "Average": 15.5,
        }

        _print_cpu_metrics(12.5, 20.0, latest_datapoint)

        captured = capsys.readouterr()
        assert "Last 7 days CPU usage:" in captured.out
        assert "Average: 12.5%" in captured.out
        assert "Maximum: 20.0%" in captured.out
        assert "15.5%" in captured.out

    def test_print_cpu_metrics_no_data(self, capsys):
        """Test printing CPU metrics with no data."""
        _print_cpu_metrics(None, None, None)

        captured = capsys.readouterr()
        assert "No CPU metrics available" in captured.out


class TestGetNetworkMetrics:
    """Tests for _get_network_metrics function."""

    def test_get_network_metrics_with_data(self, capsys):
        """Test getting network metrics with data."""
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.return_value = {
            "Datapoints": [
                {"Sum": 1024 * 1024 * 100},
                {"Sum": 1024 * 1024 * 50},
            ]
        }
        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 8, tzinfo=timezone.utc)

        _get_network_metrics(mock_cloudwatch, "i-123", start_time, end_time)

        captured = capsys.readouterr()
        assert "Network In (7 days): 150.0 MB" in captured.out

    def test_get_network_metrics_no_data(self, capsys):
        """Test getting network metrics with no data."""
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.return_value = {"Datapoints": []}
        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 8, tzinfo=timezone.utc)

        _get_network_metrics(mock_cloudwatch, "i-123", start_time, end_time)

        captured = capsys.readouterr()
        assert "Network In: No data" in captured.out

    def test_get_network_metrics_error(self, capsys):
        """Test network metrics with error."""
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "get_metric_statistics"
        )
        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 8, tzinfo=timezone.utc)

        _get_network_metrics(mock_cloudwatch, "i-123", start_time, end_time)

        captured = capsys.readouterr()
        assert "Network metrics error" in captured.out


class TestGetInstanceName:
    """Tests for _get_instance_name function."""

    def test_get_instance_name_with_tag(self):
        """Test getting instance name from tags."""
        instance = {"Tags": [{"Key": "Name", "Value": "web-server"}]}

        result = _get_instance_name(instance)

        assert result == "web-server"

    def test_get_instance_name_no_name_tag(self):
        """Test getting instance name without Name tag."""
        instance = {"Tags": [{"Key": "Environment", "Value": "prod"}]}

        result = _get_instance_name(instance)

        assert result is None

    def test_get_instance_name_no_tags(self):
        """Test getting instance name with no tags."""
        instance = {}

        result = _get_instance_name(instance)

        assert result is None


class TestEstimateMonthlyCost:
    """Tests for _estimate_monthly_cost function."""

    def test_estimate_cost_running_t2_micro(self):
        """Test cost estimate for running t2.micro."""
        cost = _estimate_monthly_cost("t2.micro", "running")

        assert cost == 8.35

    def test_estimate_cost_stopped_instance(self):
        """Test cost estimate for stopped instance."""
        cost = _estimate_monthly_cost("t2.micro", "stopped")

        assert cost == 0

    def test_estimate_cost_unknown_type(self):
        """Test cost estimate for unknown instance type."""
        cost = _estimate_monthly_cost("unknown.type", "running")

        assert cost == 50.0

    def test_estimate_cost_m5_xlarge(self):
        """Test cost estimate for m5.xlarge."""
        cost = _estimate_monthly_cost("m5.xlarge", "running")

        assert cost == 138.24


class TestProcessInstanceDetails:
    """Tests for _process_instance_details function."""

    def test_process_instance_running(self, capsys):
        """Test processing running instance."""
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.side_effect = [
            {
                "Datapoints": [
                    {
                        "Timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                        "Average": 15.0,
                        "Maximum": 25.0,
                    }
                ]
            },
            {"Datapoints": [{"Sum": 1024 * 1024 * 100}]},
        ]
        instance = {
            "instance_id": "i-123",
            "instance_type": "t2.micro",
            "state": "running",
            "launch_time": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "name": "test-instance",
        }
        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 8, tzinfo=timezone.utc)

        result = _process_instance_details(
            mock_cloudwatch, instance, "us-east-1", start_time, end_time
        )

        assert result["instance_id"] == "i-123"
        assert result["name"] == "test-instance"
        assert result["state"] == "running"
        assert result["estimated_monthly_cost"] == 8.35
        captured = capsys.readouterr()
        assert "i-123" in captured.out

    def test_process_instance_stopped(self, capsys):
        """Test processing stopped instance."""
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.side_effect = [
            {"Datapoints": []},
            {"Datapoints": []},
        ]
        instance = {
            "instance_id": "i-456",
            "instance_type": "t2.small",
            "state": "stopped",
            "launch_time": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "name": None,
        }
        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 8, tzinfo=timezone.utc)

        result = _process_instance_details(
            mock_cloudwatch, instance, "us-east-1", start_time, end_time
        )

        assert result["state"] == "stopped"
        assert result["estimated_monthly_cost"] == 0
        captured = capsys.readouterr()
        assert "stopped" in captured.out
