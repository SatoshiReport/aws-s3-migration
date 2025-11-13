"""Comprehensive tests for aws_ec2_instance_cleanup.py."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup import (
    _analyze_instances,
    _calculate_ebs_savings,
    _get_instance_name_tag,
    _get_last_activity_from_metrics,
    _print_instance_age,
    _print_instance_details,
    _terminate_instances,
    get_instance_detailed_info,
    rename_instance,
    terminate_instance,
)


class TestTerminateInstance:

    def test_terminate_instance_success(self, capsys):
        """Test successful instance termination."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_instances.return_value = {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceType": "t2.micro",
                                "State": {"Name": "running"},
                                "Tags": [{"Key": "Name", "Value": "test-instance"}],
                            }
                        ]
                    }
                ]
            }
            mock_client.return_value = mock_ec2
            result = terminate_instance("i-123", "us-east-1")
        assert result is True
        mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=["i-123"])
        captured = capsys.readouterr()
        assert "Termination initiated" in captured.out

    def test_terminate_already_terminated(self, capsys):
        """Test terminating already terminated instance."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_instances.return_value = {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceType": "t2.micro",
                                "State": {"Name": "terminated"},
                                "Tags": [],
                            }
                        ]
                    }
                ]
            }
            mock_client.return_value = mock_ec2
            result = terminate_instance("i-123", "us-east-1")
        assert result is True
        mock_ec2.terminate_instances.assert_not_called()
        captured = capsys.readouterr()
        assert "already terminated" in captured.out

    def test_terminate_instance_error(self, capsys):
        """Test error during termination."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_instances.side_effect = ClientError(
                {"Error": {"Code": "InvalidInstanceID.NotFound"}}, "describe_instances"
            )
            mock_client.return_value = mock_ec2
            result = terminate_instance("i-notfound", "us-east-1")
        assert result is False
        captured = capsys.readouterr()
        assert "Error terminating instance" in captured.out


class TestRenameInstance:

    def test_rename_instance_success(self, capsys):
        """Test successful instance renaming."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            result = rename_instance("i-123", "new-name", "us-east-1")
        assert result is True
        mock_ec2.create_tags.assert_called_once_with(
            Resources=["i-123"], Tags=[{"Key": "Name", "Value": "new-name"}]
        )
        captured = capsys.readouterr()
        assert "renamed to 'new-name'" in captured.out

    def test_rename_instance_error(self, capsys):
        """Test error during renaming."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.create_tags.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "create_tags"
            )
            mock_client.return_value = mock_ec2
            result = rename_instance("i-123", "new-name", "us-east-1")
        assert result is False
        captured = capsys.readouterr()
        assert "Error renaming instance" in captured.out


class TestGetInstanceNameTag:

    def test_get_name_from_tags(self):
        """Test extracting name from tags."""
        instance = {
            "Tags": [
                {"Key": "Name", "Value": "my-instance"},
                {"Key": "Environment", "Value": "prod"},
            ]
        }
        name = _get_instance_name_tag(instance)
        assert name == "my-instance"

    def test_get_name_no_tags(self):
        """Test when no tags exist."""
        instance = {"Tags": []}
        name = _get_instance_name_tag(instance)
        assert name == "Unknown"

    def test_get_name_no_name_tag(self):
        """Test when Name tag missing."""
        instance = {"Tags": [{"Key": "Environment", "Value": "dev"}]}
        name = _get_instance_name_tag(instance)
        assert name == "Unknown"


class TestGetLastActivityFromMetrics:
    """Tests for _get_last_activity_from_metrics function."""

    def test_get_activity_with_datapoints(self, capsys):
        """Test getting activity when datapoints exist."""
        mock_cw = MagicMock()
        mock_cw.get_metric_statistics.return_value = {
            "Datapoints": [
                {"Timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc), "Average": 10},
                {"Timestamp": datetime(2024, 1, 5, tzinfo=timezone.utc), "Average": 20},
            ]
        }
        _get_last_activity_from_metrics(mock_cw, "i-123")
        captured = capsys.readouterr()
        assert "Last Activity (CPU metrics)" in captured.out

    def test_get_activity_no_datapoints(self, capsys):
        """Test when no datapoints found."""
        mock_cw = MagicMock()
        mock_cw.get_metric_statistics.return_value = {"Datapoints": []}
        _get_last_activity_from_metrics(mock_cw, "i-123")
        captured = capsys.readouterr()
        assert "No CPU metrics found" in captured.out

    def test_get_activity_error(self, capsys):
        """Test error when retrieving metrics."""
        mock_cw = MagicMock()
        mock_cw.get_metric_statistics.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "get_metric_statistics"
        )
        _get_last_activity_from_metrics(mock_cw, "i-123")
        captured = capsys.readouterr()
        assert "Could not retrieve metrics" in captured.out


class TestPrintInstanceDetails:
    """Tests for _print_instance_details function."""

    def test_print_details(self, capsys):
        """Test printing instance details."""
        _print_instance_details("i-123", "test-instance", "t2.micro", "running", "2024-01-01")
        captured = capsys.readouterr()
        assert "i-123" in captured.out
        assert "test-instance" in captured.out
        assert "t2.micro" in captured.out
        assert "running" in captured.out


class TestPrintInstanceAge:
    """Tests for _print_instance_age function."""

    def test_print_age(self, capsys):
        """Test printing instance age."""
        launch_time = datetime.now(timezone.utc)
        _print_instance_age(launch_time)
        captured = capsys.readouterr()
        assert "Age: 0 days" in captured.out

    def test_print_age_none(self, capsys):
        """Test when launch time is None."""
        _print_instance_age(None)
        captured = capsys.readouterr()
        assert "Age:" not in captured.out


class TestGetInstanceDetailedInfo:
    """Tests for get_instance_detailed_info function."""

    def test_get_detailed_info_success(self, capsys):
        """Test successful retrieval of detailed info."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_cw = MagicMock()
            mock_ec2.describe_instances.return_value = {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceType": "t2.micro",
                                "State": {"Name": "running"},
                                "LaunchTime": datetime(2024, 1, 1, tzinfo=timezone.utc),
                                "Tags": [{"Key": "Name", "Value": "test"}],
                            }
                        ]
                    }
                ]
            }
            mock_client.side_effect = [mock_ec2, mock_cw]
            with patch(
                "cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup._get_last_activity_from_metrics"
            ):
                result = get_instance_detailed_info("i-123", "us-east-1")
        assert result is not None
        assert result["instance_id"] == "i-123"
        assert result["name"] == "test"
        assert result["instance_type"] == "t2.micro"

    def test_get_detailed_info_error(self, capsys):
        """Test error when getting detailed info."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_instances.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "describe_instances"
            )
            mock_client.return_value = mock_ec2
            result = get_instance_detailed_info("i-123", "us-east-1")
        assert result is None
        captured = capsys.readouterr()
        assert "Error getting instance info" in captured.out


class TestCalculateEbsSavings:
    """Tests for _calculate_ebs_savings function."""

    def test_calculate_known_instance(self):
        """Test calculating savings for known instance."""
        savings = _calculate_ebs_savings("Talker GPU")
        assert savings == 5.12

    def test_calculate_unknown_instance(self):
        """Test calculating savings for unknown instance."""
        savings = _calculate_ebs_savings("unknown-instance")
        assert savings == 0


class TestTerminateInstances:
    """Tests for _terminate_instances function."""

    def test_terminate_instances_all_successful(self):
        """Test terminating multiple instances successfully."""
        instances = [
            ("i-1", "us-east-1", "instance-1"),
            ("i-2", "us-east-2", "instance-2"),
        ]
        with patch(
            "cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup.terminate_instance",
            return_value=True,
        ):
            results, savings = _terminate_instances(instances)
        assert len(results) == 2
        assert all(result[2] for result in results)

    def test_terminate_instances_partial_failures(self):
        """Test with some failures."""
        instances = [
            ("i-1", "us-east-1", "Talker GPU"),
            ("i-2", "us-east-2", "unknown"),
        ]
        with patch(
            "cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup.terminate_instance",
            side_effect=[True, False],
        ):
            results, savings = _terminate_instances(instances)
        assert len(results) == 2
        assert results[0][2] is True
        assert results[1][2] is False
        assert savings == 5.12  # Only from Talker GPU


class TestAnalyzeInstances:
    """Tests for _analyze_instances function."""

    def test_analyze_multiple_instances(self):
        """Test analyzing multiple instances."""
        instances = [
            ("i-1", "us-east-1"),
            ("i-2", "us-east-2"),
        ]
        mock_details = {
            "instance_id": "i-1",
            "name": "test",
            "instance_type": "t2.micro",
            "state": "running",
            "launch_time": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "region": "us-east-1",
        }
        with patch(
            "cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup.get_instance_detailed_info",
            return_value=mock_details,
        ):
            result = _analyze_instances(instances)
        assert len(result) == 2

    def test_analyze_with_failures(self):
        """Test analyzing with some failures."""
        instances = [
            ("i-1", "us-east-1"),
            ("i-2", "us-east-2"),
        ]
        with patch(
            "cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup.get_instance_detailed_info",
            side_effect=[
                {"instance_id": "i-1", "name": "test"},
                None,
            ],
        ):
            result = _analyze_instances(instances)
        assert len(result) == 1


class TestPrintSummary:
    """Tests for _print_summary function."""

    def test_print_summary_success(self, capsys):
        """Test printing summary with successful operations."""
        from cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup import _print_summary

        termination_results = [
            ("i-1", "instance-1", True),
            ("i-2", "instance-2", True),
        ]
        instance_details = [
            {
                "instance_id": "i-3",
                "name": "test",
                "instance_type": "t2.micro",
                "launch_time": "2024-01-01",
                "state": "running",
            }
        ]
        _print_summary(termination_results, True, instance_details, 10.24)
        captured = capsys.readouterr()
        assert "OPERATION SUMMARY" in captured.out
        assert "Successfully terminated: 2" in captured.out
        assert "Instance rename: ✅ Success" in captured.out
        assert "Estimated monthly savings: $10.24" in captured.out

    def test_print_summary_with_failures(self, capsys):
        """Test printing summary with some failures."""
        from cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup import _print_summary

        termination_results = [
            ("i-1", "instance-1", True),
            ("i-2", "instance-2", False),
        ]
        _print_summary(termination_results, False, [], 5.12)
        captured = capsys.readouterr()
        assert "Successfully terminated: 1" in captured.out
        assert "Failed to terminate: 1" in captured.out
        assert "Instance rename: ❌ Failed" in captured.out


class TestMain:
    """Tests for main function."""

    def test_main_function(self, capsys):
        """Test main function execution."""
        from cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup import main

        with patch(
            "cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup._terminate_instances"
        ) as mock_term:
            with patch(
                "cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup.rename_instance"
            ) as mock_rename:
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup._analyze_instances"
                ) as mock_analyze:
                    with patch(
                        "cost_toolkit.scripts.cleanup.aws_ec2_instance_cleanup._print_summary"
                    ) as mock_summary:
                        mock_term.return_value = ([], 0)
                        mock_rename.return_value = True
                        mock_analyze.return_value = []
                        main()
        captured = capsys.readouterr()
        assert "AWS EC2 Instance Cleanup and Analysis" in captured.out
        assert "WARNING" in captured.out
        mock_term.assert_called_once()
        mock_rename.assert_called_once()
        mock_analyze.assert_called_once()
        mock_summary.assert_called_once()
