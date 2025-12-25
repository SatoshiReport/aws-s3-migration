"""Comprehensive tests for aws_ec2_usage_audit.py."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_ec2_usage_audit import (  # pyright: ignore[reportPrivateUsage]
    _print_cost_reduction_options,
    _print_low_usage_recommendations,
    _print_summary_header,
    get_instance_details_in_region,
    main,
)


class TestGetInstanceDetailsInRegion:
    """Tests for get_instance_details_in_region function."""

    def test_get_instance_details_success(self):
        """Test successful instance retrieval."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_cloudwatch = MagicMock()

            def client_factory(service, **_kwargs):
                if service == "ec2":
                    return mock_ec2
                return mock_cloudwatch

            mock_client.side_effect = client_factory

            mock_ec2.describe_instances.return_value = {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-123",
                                "InstanceType": "t2.micro",
                                "State": {"Name": "running"},
                                "LaunchTime": datetime(2024, 1, 1, tzinfo=timezone.utc),
                                "Tags": [{"Key": "Name", "Value": "test"}],
                            }
                        ]
                    }
                ]
            }
            mock_cloudwatch.get_metric_statistics.side_effect = [
                {"Datapoints": []},
                {"Datapoints": []},
            ]

            result = get_instance_details_in_region("us-east-1")

            assert len(result) == 1
            assert result[0]["instance_id"] == "i-123"

    def test_get_instance_details_no_instances(self, capsys):
        """Test with no instances."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_cloudwatch = MagicMock()

            def client_factory(service, **_kwargs):
                if service == "ec2":
                    return mock_ec2
                return mock_cloudwatch

            mock_client.side_effect = client_factory

            mock_ec2.describe_instances.return_value = {"Reservations": []}

            result = get_instance_details_in_region("us-east-1")

        assert not result
        captured = capsys.readouterr()
        assert "No EC2 instances found" in captured.out

    def test_get_instance_details_error(self, capsys):
        """Test error handling."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_instances.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "describe_instances")

            result = get_instance_details_in_region("us-east-1")

        assert not result
        captured = capsys.readouterr()
        assert "Error auditing instances" in captured.out


class TestPrintSummaryHeader:
    """Tests for _print_summary_header function."""

    def test_print_summary_with_instances(self, capsys):
        """Test printing summary with running and stopped instances."""
        instances = [
            {
                "instance_id": "i-1",
                "state": "running",
                "estimated_monthly_cost": 10.0,
            },
            {
                "instance_id": "i-2",
                "state": "running",
                "estimated_monthly_cost": 20.0,
            },
            {
                "instance_id": "i-3",
                "state": "stopped",
                "estimated_monthly_cost": 0,
            },
        ]

        _print_summary_header(instances, 30.0)

        captured = capsys.readouterr()
        assert "Total instances found: 3" in captured.out
        assert "Running: 2" in captured.out
        assert "Stopped: 1" in captured.out
        assert "$30.00" in captured.out

    def test_print_summary_with_empty_instances(self, capsys):
        """Test printing summary with no instances."""
        _print_summary_header([], 0.0)

        captured = capsys.readouterr()
        assert "Total instances found: 0" in captured.out
        assert "Running: 0" in captured.out
        assert "Stopped: 0" in captured.out


class TestPrintLowUsageRecommendations:
    """Tests for _print_low_usage_recommendations function."""

    def test_print_recommendations_with_low_usage(self, capsys):
        """Test printing recommendations with low usage instances."""
        instances = [
            {
                "instance_id": "i-1",
                "name": "low-use-1",
                "region": "us-east-1",
                "usage_level": "LOW (<5% avg)",
                "estimated_monthly_cost": 10.0,
            },
            {
                "instance_id": "i-2",
                "name": "normal-use",
                "region": "us-east-1",
                "usage_level": "MODERATE (5-20% avg)",
                "estimated_monthly_cost": 15.0,
            },
        ]

        _print_low_usage_recommendations(instances)

        captured = capsys.readouterr()
        assert "1 instances with low CPU usage" in captured.out
        assert "low-use-1" in captured.out
        assert "normal-use" not in captured.out

    def test_print_recommendations_no_low_usage(self, capsys):
        """Test printing recommendations with no low usage instances."""
        instances = [
            {
                "instance_id": "i-1",
                "name": "normal-use",
                "region": "us-east-1",
                "usage_level": "HIGH (>20% avg)",
                "estimated_monthly_cost": 20.0,
            }
        ]

        _print_low_usage_recommendations(instances)

        captured = capsys.readouterr()
        assert "instances with low CPU usage" not in captured.out


class TestPrintCostReductionOptions:
    """Tests for _print_cost_reduction_options function."""

    def test_print_cost_reduction_options(self, capsys):
        """Test printing cost reduction options."""
        _print_cost_reduction_options()

        captured = capsys.readouterr()
        assert "OPTIONS FOR COST REDUCTION:" in captured.out
        assert "STOP instances" in captured.out
        assert "TERMINATE unused instances" in captured.out
        assert "DOWNSIZE over-provisioned instances" in captured.out
        assert "SCHEDULE instances" in captured.out
        assert "RELEASE Elastic IPs" in captured.out
        assert "IMPORTANT NOTES:" in captured.out

    def test_print_cost_reduction_warnings(self, capsys):
        """Test that important warnings are included."""
        _print_cost_reduction_options()

        captured = capsys.readouterr()
        assert "IMPORTANT NOTES:" in captured.out
        assert "storage" in captured.out.lower() or "ebs" in captured.out.lower()


class TestMain:
    """Tests for main function."""

    def test_main_success(self, capsys):
        """Test main function execution."""
        with patch(
            "cost_toolkit.scripts.audit.aws_ec2_usage_audit.get_instance_details_in_region",
            return_value=[
                {
                    "instance_id": "i-123",
                    "name": "test",
                    "region": "us-east-1",
                    "state": "running",
                    "usage_level": "LOW (<5% avg)",
                    "estimated_monthly_cost": 10.0,
                }
            ],
        ):
            main()

            captured = capsys.readouterr()
            assert "AWS EC2 Usage Audit" in captured.out
            assert "OVERALL SUMMARY" in captured.out
            assert "OPTIMIZATION RECOMMENDATIONS:" in captured.out

    def test_main_multiple_regions(self, capsys):
        """Test main function with multiple regions."""
        call_count = {"count": 0}

        def side_effect(*_args, **_kwargs):
            current = call_count["count"]
            call_count["count"] += 1
            if current == 0:
                return [
                    {
                        "instance_id": "i-1",
                        "name": "test-1",
                        "region": "us-east-1",
                        "state": "running",
                        "usage_level": "MODERATE",
                        "estimated_monthly_cost": 10.0,
                    }
                ]
            if current == 1:
                return [
                    {
                        "instance_id": "i-2",
                        "name": "test-2",
                        "region": "eu-west-2",
                        "state": "stopped",
                        "usage_level": "NO DATA",
                        "estimated_monthly_cost": 0,
                    }
                ]
            return []

        with patch(
            "cost_toolkit.scripts.audit.aws_ec2_usage_audit.get_instance_details_in_region",
            side_effect=side_effect,
        ):
            main()

            captured = capsys.readouterr()
            assert "OVERALL SUMMARY" in captured.out
