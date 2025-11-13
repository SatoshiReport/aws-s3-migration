"""Comprehensive tests for aws_backup_audit.py."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_backup_audit import (
    _display_backup_plan,
    _display_backup_rules,
    _display_single_job,
    _display_single_schedule,
    _is_snapshot_related_rule,
    check_aws_backup_plans,
    check_data_lifecycle_manager,
    get_all_aws_regions,
)


class TestGetAllAwsRegions:
    """Tests for get_all_aws_regions function."""

    def test_get_regions_success(self):
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


class TestDisplaySingleJob:
    """Tests for _display_single_job function."""

    def test_display_job(self, capsys):
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

                # Should not raise exception
                check_aws_backup_plans("us-east-1")


class TestDisplaySingleSchedule:
    """Tests for _display_single_schedule function."""

    def test_display_schedule(self, capsys):
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
