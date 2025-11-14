"""Comprehensive tests for aws_backup_audit.py - Display functions for jobs and plans."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_backup_audit import (
    _display_backup_jobs,
    _display_backup_plan,
    _display_backup_rules,
    _display_policy_schedules,
    _display_rule_details,
    _display_single_job,
    _display_single_schedule,
    _display_snapshot_pattern,
    _is_snapshot_related_rule,
    get_all_aws_regions,
)


def test_get_all_aws_regions_get_regions_success():
    """Test successful retrieval of all regions."""
    with patch("boto3.client") as mock_client:
        mock_ec2 = MagicMock()
        mock_ec2.describe_regions.return_value = {
            "Regions": [
                {"RegionName": "us-east-1"},
                {"RegionName": "us-west-2"},
            ]
        }
        mock_client.return_value = mock_ec2

        regions = get_all_aws_regions()

    assert len(regions) == 2
    assert "us-east-1" in regions


class TestDisplayBackupRules:
    """Tests for _display_backup_rules function."""

    def test_display_rules_with_schedule(self, capsys):
        """Test displaying rules with schedule."""
        rules = [
            {
                "RuleName": "daily-backup",
                "ScheduleExpression": "cron(0 5 ? * * *)",
                "Lifecycle": {"DeleteAfterDays": 30},
            }
        ]

        _display_backup_rules(rules)

        captured = capsys.readouterr()
        assert "Rule: daily-backup" in captured.out
        assert "Schedule: cron(0 5 ? * * *)" in captured.out
        assert "Lifecycle:" in captured.out

    def test_display_rules_no_schedule(self, capsys):
        """Test displaying rules without schedule."""
        rules = [
            {
                "RuleName": "on-demand",
            }
        ]

        _display_backup_rules(rules)

        captured = capsys.readouterr()
        assert "Rule: on-demand" in captured.out
        assert "Schedule: No schedule" in captured.out


class TestDisplayBackupPlan:
    """Tests for _display_backup_plan function."""

    def test_display_plan_success(self, capsys):
        """Test successful display of backup plan."""
        mock_client = MagicMock()
        mock_client.get_backup_plan.return_value = {
            "BackupPlan": {
                "Rules": [
                    {
                        "RuleName": "test-rule",
                        "ScheduleExpression": "cron(0 5 ? * * *)",
                    }
                ]
            }
        }

        plan = {
            "BackupPlanId": "plan-123",
            "BackupPlanName": "test-plan",
            "CreationDate": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }

        with patch("cost_toolkit.scripts.audit.aws_backup_audit._display_backup_rules"):
            _display_backup_plan(mock_client, plan)

        captured = capsys.readouterr()
        assert "Plan: test-plan" in captured.out
        assert "plan-123" in captured.out

    def test_display_plan_error(self, capsys):
        """Test error when displaying backup plan."""
        mock_client = MagicMock()
        mock_client.get_backup_plan.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "get_backup_plan"
        )

        plan = {
            "BackupPlanId": "plan-123",
            "BackupPlanName": "test-plan",
            "CreationDate": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }

        _display_backup_plan(mock_client, plan)

        captured = capsys.readouterr()
        assert "Error getting plan details" in captured.out


def test_display_single_job_display_job(capsys):
    """Test displaying backup job."""
    job = {
        "BackupJobId": "job-123",
        "ResourceArn": "arn:aws:ec2:us-east-1:123456789012:volume/vol-123",
        "State": "COMPLETED",
        "CreationDate": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }

    _display_single_job(job)

    captured = capsys.readouterr()
    assert "Job: job-123" in captured.out
    assert "State: COMPLETED" in captured.out
    assert "vol-123" in captured.out


def test_display_single_schedule_display_schedule(capsys):
    """Test displaying schedule."""
    schedule = {
        "Name": "daily-schedule",
        "CreateRule": {
            "Interval": 1,
            "IntervalUnit": "days",
        },
        "RetainRule": {
            "Count": 7,
        },
    }

    _display_single_schedule(schedule)

    captured = capsys.readouterr()
    assert "Schedule: daily-schedule" in captured.out
    assert "Frequency: Every 1 days" in captured.out
    assert "Retention: 7 snapshots" in captured.out


class TestIsSnapshotRelatedRule:
    """Tests for _is_snapshot_related_rule function."""

    def test_snapshot_in_name(self):
        """Test rule with snapshot in name."""
        rule = {
            "Name": "daily-snapshot-rule",
            "Description": "Creates daily snapshots",
        }

        assert _is_snapshot_related_rule(rule) is True

    def test_ami_in_description(self):
        """Test rule with AMI in description."""
        rule = {
            "Name": "nightly-rule",
            "Description": "Create AMI backup nightly",
        }

        assert _is_snapshot_related_rule(rule) is True

    def test_backup_in_name(self):
        """Test rule with backup in name."""
        rule = {
            "Name": "backup-rule",
            "Description": "Regular backup",
        }

        assert _is_snapshot_related_rule(rule) is True

    def test_not_snapshot_related(self):
        """Test rule not related to snapshots."""
        rule = {
            "Name": "monitoring-rule",
            "Description": "Monitoring alerts",
        }

        assert _is_snapshot_related_rule(rule) is False


class TestDisplayBackupJobs:
    """Tests for _display_backup_jobs function."""

    def test_display_jobs_with_jobs(self, capsys):
        """Test displaying backup jobs when jobs exist."""
        mock_client = MagicMock()
        jobs = [
            {
                "BackupJobId": "job-1",
                "ResourceArn": "arn:aws:ec2:us-east-1:123456789012:volume/vol-1",
                "State": "COMPLETED",
                "CreationDate": datetime(2024, 1, 1, tzinfo=timezone.utc),
            },
            {
                "BackupJobId": "job-2",
                "ResourceArn": "arn:aws:ec2:us-east-1:123456789012:volume/vol-2",
                "State": "RUNNING",
                "CreationDate": datetime(2024, 1, 2, tzinfo=timezone.utc),
            },
        ]
        mock_client.list_backup_jobs.return_value = {"BackupJobs": jobs}

        _display_backup_jobs(mock_client, "us-east-1")

        captured = capsys.readouterr()
        assert "Recent Backup Jobs in us-east-1" in captured.out
        assert "job-1" in captured.out
        assert "COMPLETED" in captured.out

    def test_display_jobs_no_jobs(self, capsys):
        """Test displaying backup jobs when no jobs exist."""
        mock_client = MagicMock()
        mock_client.list_backup_jobs.return_value = {"BackupJobs": []}

        _display_backup_jobs(mock_client, "us-east-1")

        captured = capsys.readouterr()
        assert "Recent Backup Jobs" not in captured.out

    def test_display_jobs_error(self, capsys):
        """Test error when listing backup jobs."""
        mock_client = MagicMock()
        mock_client.list_backup_jobs.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "list_backup_jobs"
        )

        _display_backup_jobs(mock_client, "us-east-1")

        captured = capsys.readouterr()
        assert "Error listing backup jobs" in captured.out


class TestDisplayPolicySchedules:
    """Tests for _display_policy_schedules function."""

    def test_display_schedules_success(self, capsys):
        """Test successfully displaying policy schedules."""
        mock_client = MagicMock()
        mock_client.get_lifecycle_policy.return_value = {
            "Policy": {
                "PolicyDetails": {
                    "Schedules": [
                        {
                            "Name": "daily-schedule",
                            "CreateRule": {"Interval": 1, "IntervalUnit": "days"},
                            "RetainRule": {"Count": 7},
                        }
                    ]
                }
            }
        }

        _display_policy_schedules(mock_client, "policy-123")

        captured = capsys.readouterr()
        assert "Schedule: daily-schedule" in captured.out
        assert "Frequency: Every 1 days" in captured.out

    def test_display_schedules_error(self, capsys):
        """Test error when getting policy schedules."""
        mock_client = MagicMock()
        mock_client.get_lifecycle_policy.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "get_lifecycle_policy"
        )

        _display_policy_schedules(mock_client, "policy-123")

        captured = capsys.readouterr()
        assert "Error getting policy details" in captured.out


class TestDisplayRuleDetails:
    """Tests for _display_rule_details function."""

    def test_display_rule_with_targets(self, capsys):
        """Test displaying rule with targets."""
        mock_client = MagicMock()
        mock_client.list_targets_by_rule.return_value = {
            "Targets": [{"Arn": "arn:aws:lambda:us-east-1:123456789012:function:create-snapshot"}]
        }

        rule = {
            "Name": "snapshot-rule",
            "Description": "Create daily snapshots",
            "State": "ENABLED",
            "ScheduleExpression": "cron(0 5 * * ? *)",
        }

        _display_rule_details(mock_client, rule)

        captured = capsys.readouterr()
        assert "Rule: snapshot-rule" in captured.out
        assert "Description: Create daily snapshots" in captured.out
        assert "State: ENABLED" in captured.out
        assert "Schedule: cron(0 5 * * ? *)" in captured.out
        assert "Target: arn:aws:lambda" in captured.out

    def test_display_rule_no_schedule(self, capsys):
        """Test displaying rule without schedule expression."""
        mock_client = MagicMock()
        mock_client.list_targets_by_rule.return_value = {"Targets": []}

        rule = {
            "Name": "event-rule",
            "State": "DISABLED",
        }

        _display_rule_details(mock_client, rule)

        captured = capsys.readouterr()
        assert "Rule: event-rule" in captured.out
        assert "Schedule: Event-driven" in captured.out
        assert "State: DISABLED" in captured.out

    def test_display_rule_targets_error(self, capsys):
        """Test error when getting rule targets."""
        mock_client = MagicMock()
        mock_client.list_targets_by_rule.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "list_targets_by_rule"
        )

        rule = {
            "Name": "test-rule",
            "State": "ENABLED",
        }

        _display_rule_details(mock_client, rule)

        captured = capsys.readouterr()
        assert "Error getting targets" in captured.out


class TestDisplaySnapshotPattern:
    """Tests for _display_snapshot_pattern function."""

    def test_display_automated_pattern(self, capsys):
        """Test displaying automated snapshot pattern."""
        snapshots = [
            {
                "id": "snap-1",
                "description": "AWS Backup snapshot",
                "start_time": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "size": 100,
            },
            {
                "id": "snap-2",
                "description": "AWS Backup snapshot",
                "start_time": datetime(2024, 1, 2, tzinfo=timezone.utc),
                "size": 150,
            },
        ]

        _display_snapshot_pattern("AWS Backup", snapshots)

        captured = capsys.readouterr()
        assert "AWS Backup: 2 snapshots" in captured.out
        assert "Total size: 250 GB" in captured.out
        assert "$12.50" in captured.out
        assert "snap-2" in captured.out

    def test_display_manual_pattern_skipped(self, capsys):
        """Test that manual/unknown patterns are skipped."""
        snapshots = [
            {
                "id": "snap-1",
                "description": "Manual snapshot",
                "start_time": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "size": 50,
            }
        ]

        _display_snapshot_pattern("Manual/Unknown", snapshots)

        captured = capsys.readouterr()
        assert "Manual/Unknown" not in captured.out
