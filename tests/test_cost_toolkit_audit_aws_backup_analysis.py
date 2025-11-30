"""Comprehensive tests for aws_backup_audit.py - Snapshots and service checks."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_backup_audit import (
    _categorize_snapshot,
    analyze_recent_snapshots,
    check_aws_backup_plans,
    check_data_lifecycle_manager,
    check_scheduled_events,
    main,
)


class TestCategorizeSnapshot:
    """Tests for _categorize_snapshot function."""

    def test_categorize_ami_creation(self):
        """Test categorizing AMI creation snapshot."""
        snapshot = {
            "SnapshotId": "snap-123",
            "Description": "Created by CreateImage for ami-123",
            "StartTime": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "VolumeSize": 100,
        }
        pattern, _ = _categorize_snapshot(snapshot)
        assert pattern == "AMI Creation (CreateImage)"

    def test_categorize_aws_backup(self):
        """Test categorizing AWS Backup snapshot."""
        snapshot = {
            "SnapshotId": "snap-456",
            "Description": "AWS Backup automated snapshot",
            "StartTime": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "VolumeSize": 50,
        }
        pattern, info = _categorize_snapshot(snapshot)
        assert pattern == "AWS Backup"
        assert info["id"] == "snap-456"

    def test_categorize_dlm(self):
        """Test categorizing DLM snapshot."""
        snapshot = {
            "SnapshotId": "snap-789",
            "Description": "DLM snapshot policy-123",
            "StartTime": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "VolumeSize": 75,
        }
        pattern, _ = _categorize_snapshot(snapshot)
        assert pattern == "Data Lifecycle Manager"

    def test_categorize_automated_other(self):
        """Test categorizing other automated snapshot."""
        snapshot = {
            "SnapshotId": "snap-999",
            "Description": "Created by automation script",
            "StartTime": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "VolumeSize": 25,
        }
        pattern, _ = _categorize_snapshot(snapshot)
        assert pattern == "Automated (Other)"

    def test_categorize_manual(self):
        """Test categorizing manual snapshot."""
        snapshot = {
            "SnapshotId": "snap-111",
            "Description": "Manual backup",
            "StartTime": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "VolumeSize": 30,
        }
        pattern, _ = _categorize_snapshot(snapshot)
        assert pattern == "Manual/Unknown"


class TestAnalyzeRecentSnapshots:
    """Tests for analyze_recent_snapshots function."""

    def test_analyze_with_recent_snapshots(self, capsys):
        """Test analyzing recent snapshots."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            snapshots = [
                {
                    "SnapshotId": "snap-1",
                    "Description": "Created by CreateImage for ami-123",
                    "StartTime": datetime.now(timezone.utc),
                    "VolumeSize": 100,
                },
                {
                    "SnapshotId": "snap-2",
                    "Description": "AWS Backup snapshot",
                    "StartTime": datetime.now(timezone.utc),
                    "VolumeSize": 50,
                },
            ]
            mock_ec2.describe_snapshots.return_value = {"Snapshots": snapshots}
            mock_client.return_value = mock_ec2

            analyze_recent_snapshots("us-east-1")

        captured = capsys.readouterr()
        assert "Recent Snapshots Analysis in us-east-1" in captured.out
        assert "AMI Creation (CreateImage)" in captured.out
        assert "AWS Backup" in captured.out

    def test_analyze_no_recent_snapshots(self, capsys):
        """Test analyzing when no recent snapshots exist."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            old_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
            snapshots = [
                {
                    "SnapshotId": "snap-old",
                    "Description": "Old snapshot",
                    "StartTime": old_date,
                    "VolumeSize": 100,
                }
            ]
            mock_ec2.describe_snapshots.return_value = {"Snapshots": snapshots}
            mock_client.return_value = mock_ec2
            analyze_recent_snapshots("us-east-1")
        captured = capsys.readouterr()
        assert "Recent Snapshots Analysis" not in captured.out

    def test_analyze_snapshots_error(self, capsys):
        """Test error when analyzing snapshots."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_snapshots.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "describe_snapshots"
            )
            mock_client.return_value = mock_ec2
            analyze_recent_snapshots("us-east-1")
        captured = capsys.readouterr()
        assert "Error analyzing snapshots" in captured.out


class TestCheckAwsBackupPlans:
    """Tests for check_aws_backup_plans function."""

    def test_check_plans_with_plans(self, capsys):
        """Test checking backup plans when plans exist."""
        plans = [
            {
                "BackupPlanId": "plan-1",
                "BackupPlanName": "test-plan",
                "CreationDate": datetime(2024, 1, 1, tzinfo=timezone.utc),
            }
        ]
        with patch("boto3.client") as mock_client:
            mock_backup = MagicMock()
            mock_backup.list_backup_jobs.return_value = {"BackupJobs": []}
            mock_client.return_value = mock_backup
            with patch(
                "cost_toolkit.scripts.audit.aws_backup_audit.get_backup_plans", return_value=plans
            ):
                with patch("cost_toolkit.scripts.audit.aws_backup_audit._display_backup_plan"):
                    check_aws_backup_plans("us-east-1")
        captured = capsys.readouterr()
        assert "AWS Backup Plans in us-east-1" in captured.out

    def test_check_plans_service_not_available(self):
        """Test when Backup service not available."""
        with patch("boto3.client") as mock_client:
            mock_backup = MagicMock()
            mock_client.return_value = mock_backup
            with patch("cost_toolkit.scripts.audit.aws_backup_audit.get_backup_plans") as mock_get:
                mock_get.side_effect = ClientError(
                    {"Error": {"Code": "UnrecognizedClientException"}}, "list_backup_plans"
                )
                check_aws_backup_plans("us-east-1")

    def test_check_plans_other_error(self, capsys):
        """Test handling of non-UnrecognizedClient errors."""
        with patch("boto3.client") as mock_client:
            mock_backup = MagicMock()
            mock_client.return_value = mock_backup
            with patch("cost_toolkit.scripts.audit.aws_backup_audit.get_backup_plans") as mock_get:
                mock_get.side_effect = ClientError(
                    {"Error": {"Code": "ServiceError"}}, "list_backup_plans"
                )
                check_aws_backup_plans("us-east-1")
        captured = capsys.readouterr()
        assert "Error checking AWS Backup" in captured.out

    def test_check_plans_with_backup_jobs(self, capsys):
        """Test checking backup plans with associated backup jobs."""
        plans = [
            {
                "BackupPlanId": "plan-1",
                "BackupPlanName": "test-plan",
                "CreationDate": datetime(2024, 1, 1, tzinfo=timezone.utc),
            }
        ]
        with patch("boto3.client") as mock_client:
            mock_backup = MagicMock()
            mock_backup.list_backup_jobs.return_value = {
                "BackupJobs": [
                    {
                        "BackupJobId": "job-1",
                        "State": "COMPLETED",
                        "CreationDate": datetime(2024, 1, 1, tzinfo=timezone.utc),
                    }
                ]
            }
            mock_client.return_value = mock_backup
            with patch(
                "cost_toolkit.scripts.audit.aws_backup_audit.get_backup_plans", return_value=plans
            ):
                with patch("cost_toolkit.scripts.audit.aws_backup_audit._display_backup_plan"):
                    check_aws_backup_plans("us-east-1")
        captured = capsys.readouterr()
        assert "AWS Backup Plans in us-east-1" in captured.out


class TestCheckDataLifecycleManager:
    """Tests for check_data_lifecycle_manager function."""

    def test_check_dlm_with_policies(self, capsys):
        """Test checking DLM with policies."""
        policies = [
            {
                "PolicyId": "policy-1",
                "Description": "Test policy",
                "State": "ENABLED",
            }
        ]

        with patch("boto3.client") as mock_client:
            mock_dlm = MagicMock()
            mock_client.return_value = mock_dlm

            with patch(
                "cost_toolkit.scripts.audit.aws_backup_audit.check_dlm_lifecycle_policies",
                return_value=policies,
            ):
                with patch("cost_toolkit.scripts.audit.aws_backup_audit._display_policy_schedules"):
                    check_data_lifecycle_manager("us-east-1")

        captured = capsys.readouterr()
        assert "Data Lifecycle Manager Policies" in captured.out
        assert "policy-1" in captured.out

    def test_check_dlm_no_policies(self):
        """Test when no DLM policies exist."""
        with patch(
            "cost_toolkit.scripts.audit.aws_backup_audit.check_dlm_lifecycle_policies",
            return_value=[],
        ):
            # Should not raise exception
            check_data_lifecycle_manager("us-east-1")

    def test_check_dlm_unrecognized_client(self):
        """Test when DLM service not available."""
        policies = [{"PolicyId": "policy-1", "State": "ENABLED"}]

        with patch("boto3.client") as mock_client:
            mock_client.side_effect = ClientError(
                {"Error": {"Code": "UnrecognizedClientException"}}, "dlm"
            )

            with patch(
                "cost_toolkit.scripts.audit.aws_backup_audit.check_dlm_lifecycle_policies",
                return_value=policies,
            ):
                check_data_lifecycle_manager("us-east-1")

    def test_check_dlm_other_error(self, capsys):
        """Test handling of non-UnrecognizedClient errors during client creation."""
        policies = [{"PolicyId": "policy-1", "State": "ENABLED"}]

        with patch("boto3.client") as mock_client:
            mock_client.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "dlm")

            with patch(
                "cost_toolkit.scripts.audit.aws_backup_audit.check_dlm_lifecycle_policies",
                return_value=policies,
            ):
                check_data_lifecycle_manager("us-east-1")

        captured = capsys.readouterr()
        assert "Error checking DLM" in captured.out


class TestCheckScheduledEvents:
    """Tests for check_scheduled_events function."""

    def test_check_events_with_snapshot_rules(self, capsys):
        """Test checking scheduled events with snapshot-related rules."""
        rules = [
            {
                "Name": "daily-snapshot",
                "Description": "Create snapshots",
                "State": "ENABLED",
            },
            {
                "Name": "monitoring-rule",
                "Description": "Monitor resources",
                "State": "ENABLED",
            },
        ]

        with patch("boto3.client") as mock_client:
            mock_events = MagicMock()
            mock_events.list_targets_by_rule.return_value = {"Targets": []}
            mock_client.return_value = mock_events

            with patch(
                "cost_toolkit.scripts.audit.aws_backup_audit.check_eventbridge_scheduled_rules",
                return_value=rules,
            ):
                check_scheduled_events("us-east-1")

        captured = capsys.readouterr()
        assert "EventBridge Rules (Snapshot/AMI related)" in captured.out
        assert "daily-snapshot" in captured.out
        assert "monitoring-rule" not in captured.out

    def test_check_events_no_rules(self):
        """Test when no EventBridge rules exist."""
        with patch(
            "cost_toolkit.scripts.audit.aws_backup_audit.check_eventbridge_scheduled_rules",
            return_value=[],
        ):
            check_scheduled_events("us-east-1")

    def test_check_events_no_snapshot_rules(self):
        """Test when rules exist but none are snapshot-related."""
        rules = [
            {
                "Name": "monitoring-rule",
                "Description": "Monitor resources",
                "State": "ENABLED",
            }
        ]

        with patch(
            "cost_toolkit.scripts.audit.aws_backup_audit.check_eventbridge_scheduled_rules",
            return_value=rules,
        ):
            check_scheduled_events("us-east-1")


class TestMain:
    """Tests for main function."""

    def test_main_execution(self, capsys):
        """Test main function execution."""
        regions = ["eu-west-2", "us-east-2", "us-east-1"]
        with patch("cost_toolkit.scripts.audit.aws_backup_audit.setup_aws_credentials"):
            with patch("cost_toolkit.scripts.audit.aws_backup_audit.check_aws_backup_plans"):
                with patch(
                    "cost_toolkit.scripts.audit.aws_backup_audit.check_data_lifecycle_manager"
                ):
                    with patch(
                        "cost_toolkit.scripts.audit.aws_backup_audit.check_scheduled_events"
                    ):
                        with patch(
                            "cost_toolkit.scripts.audit.aws_backup_audit.analyze_recent_snapshots"
                        ):
                            with patch(
                                "cost_toolkit.scripts.audit.aws_backup_audit.get_all_aws_regions",
                                return_value=regions,
                            ):
                                main()

        captured = capsys.readouterr()
        assert "AWS Backup and Automated Snapshot Audit" in captured.out
        assert "eu-west-2" in captured.out
        assert "us-east-2" in captured.out
        assert "us-east-1" in captured.out

    def test_main_with_client_error(self, capsys):
        """Test main function with ClientError during execution."""
        with patch("cost_toolkit.scripts.audit.aws_backup_audit.setup_aws_credentials"):
            with patch(
                "cost_toolkit.scripts.audit.aws_backup_audit.check_aws_backup_plans",
                side_effect=ClientError({"Error": {"Code": "AccessDenied"}}, "operation"),
            ):
                with patch(
                    "cost_toolkit.scripts.audit.aws_backup_audit.check_data_lifecycle_manager"
                ):
                    with patch(
                        "cost_toolkit.scripts.audit.aws_backup_audit.check_scheduled_events"
                    ):
                        with patch(
                            "cost_toolkit.scripts.audit.aws_backup_audit.analyze_recent_snapshots"
                        ):
                            with patch(
                                "cost_toolkit.scripts.audit.aws_backup_audit.get_all_aws_regions",
                                return_value=["eu-west-2", "us-east-2", "us-east-1"],
                            ):
                                try:
                                    main()
                                except ClientError:
                                    pass

        captured = capsys.readouterr()
        assert "AWS Backup and Automated Snapshot Audit" in captured.out
