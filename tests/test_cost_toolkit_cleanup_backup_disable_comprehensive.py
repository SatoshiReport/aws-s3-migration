"""Comprehensive tests for aws_backup_disable.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_backup_disable import (
    _delete_backup_selection,
    _delete_plan_selections,
    _delete_single_backup_plan,
    check_backup_vault_policies,
    disable_aws_backup_plans,
    disable_dlm_policies,
    disable_eventbridge_backup_rules,
)


class TestDeleteBackupSelection:
    def test_delete_selection_success(self, capsys):
        mock_client = MagicMock()
        selection = {
            "SelectionId": "sel-123",
            "SelectionName": "test-selection",
        }
        _delete_backup_selection(mock_client, "plan-123", selection)
        mock_client.delete_backup_selection.assert_called_once_with(
            BackupPlanId="plan-123", SelectionId="sel-123"
        )
        captured = capsys.readouterr()
        assert "Successfully removed backup selection" in captured.out

    def test_delete_selection_error(self, capsys):
        mock_client = MagicMock()
        mock_client.delete_backup_selection.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "delete_backup_selection"
        )
        selection = {
            "SelectionId": "sel-123",
            "SelectionName": "test-selection",
        }
        _delete_backup_selection(mock_client, "plan-123", selection)
        captured = capsys.readouterr()
        assert "Error removing backup selection" in captured.out


class TestDeletePlanSelections:
    def test_delete_multiple_selections(self, capsys):
        mock_client = MagicMock()
        mock_client.list_backup_selections.return_value = {
            "BackupSelectionsList": [
                {"SelectionId": "sel-1", "SelectionName": "selection-1"},
                {"SelectionId": "sel-2", "SelectionName": "selection-2"},
            ]
        }
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable._delete_backup_selection"):
            _delete_plan_selections(mock_client, "plan-123")
        captured = capsys.readouterr()
        assert "Found 2 backup selection(s)" in captured.out

    def test_delete_no_selections(self):
        mock_client = MagicMock()
        mock_client.list_backup_selections.return_value = {"BackupSelectionsList": []}
        with patch(
            "cost_toolkit.scripts.cleanup.aws_backup_disable._delete_backup_selection"
        ) as mock_delete:
            _delete_plan_selections(mock_client, "plan-123")
        mock_delete.assert_not_called()


class TestDeleteSingleBackupPlan:
    def test_delete_plan_success(self, capsys):
        mock_client = MagicMock()
        plan = {
            "BackupPlanId": "plan-123",
            "BackupPlanName": "test-plan",
            "CreationDate": "2024-01-01",
        }
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable._delete_plan_selections"):
            _delete_single_backup_plan(mock_client, plan)
        mock_client.delete_backup_plan.assert_called_once_with(BackupPlanId="plan-123")
        captured = capsys.readouterr()
        assert "Successfully deleted backup plan" in captured.out

    def test_delete_plan_error(self, capsys):
        mock_client = MagicMock()
        mock_client.delete_backup_plan.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "delete_backup_plan"
        )
        plan = {
            "BackupPlanId": "plan-123",
            "BackupPlanName": "test-plan",
            "CreationDate": "2024-01-01",
        }
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable._delete_plan_selections"):
            _delete_single_backup_plan(mock_client, plan)
        captured = capsys.readouterr()
        assert "Error deleting backup plan" in captured.out


class TestDisableAwsBackupPlans:
    def test_combined(self, capsys):

        plans = [
            {
                "BackupPlanId": "plan-1",
                "BackupPlanName": "plan-1",
                "CreationDate": "2024-01-01",
            }
        ]
        with patch("boto3.client") as mock_client:
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.get_backup_plans",
                return_value=plans,
            ):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_backup_disable._delete_single_backup_plan"
                ):
                    disable_aws_backup_plans("us-east-1")
        captured = capsys.readouterr()
        assert "Found 1 AWS Backup plan(s)" in captured.out

        with patch("boto3.client"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.get_backup_plans", return_value=[]
            ):
                disable_aws_backup_plans("us-east-1")
        captured = capsys.readouterr()
        assert "No AWS Backup plans found" in captured.out

        with patch("boto3.client"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.get_backup_plans"
            ) as mock_get:
                mock_get.side_effect = ClientError(
                    {"Error": {"Code": "UnrecognizedClientException"}}, "list_backup_plans"
                )
                disable_aws_backup_plans("us-east-1")
        captured = capsys.readouterr()
        assert "service not available" in captured.out

        with patch("boto3.client"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.get_backup_plans"
            ) as mock_get:
                mock_get.side_effect = ClientError(
                    {"Error": {"Code": "ServiceError"}}, "list_backup_plans"
                )
                disable_aws_backup_plans("us-east-1")
        captured = capsys.readouterr()
        assert "Error checking AWS Backup" in captured.out


class TestDisableDlmPolicies:
    def test_combined(self, capsys):

        policies = [{"PolicyId": "policy-1", "Description": "Test policy", "State": "ENABLED"}]
        with patch("boto3.client") as mock_client:
            mock_dlm = MagicMock()
            mock_client.return_value = mock_dlm
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.check_dlm_lifecycle_policies",
                return_value=policies,
            ):
                disable_dlm_policies("us-east-1")
        mock_dlm.update_lifecycle_policy.assert_called_once_with(
            PolicyId="policy-1", State="DISABLED"
        )
        captured = capsys.readouterr()
        assert "Successfully disabled DLM policy" in captured.out

        policies = [{"PolicyId": "policy-1", "Description": "Test policy", "State": "DISABLED"}]
        with patch("boto3.client") as mock_client:
            mock_dlm = MagicMock()
            mock_client.return_value = mock_dlm
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.check_dlm_lifecycle_policies",
                return_value=policies,
            ):
                disable_dlm_policies("us-east-1")
        mock_dlm.update_lifecycle_policy.assert_not_called()
        captured = capsys.readouterr()
        assert "already disabled" in captured.out

        with patch("boto3.client"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.check_dlm_lifecycle_policies",
                return_value=[],
            ):
                disable_dlm_policies("us-east-1")
        captured = capsys.readouterr()
        assert "No Data Lifecycle Manager policies found" in captured.out

        policies = [{"PolicyId": "policy-1", "Description": "Test policy", "State": "ENABLED"}]
        with patch("boto3.client") as mock_client:
            mock_dlm = MagicMock()
            mock_dlm.update_lifecycle_policy.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "update_lifecycle_policy"
            )
            mock_client.return_value = mock_dlm
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.check_dlm_lifecycle_policies",
                return_value=policies,
            ):
                disable_dlm_policies("us-east-1")
        captured = capsys.readouterr()
        assert "Error disabling DLM policy" in captured.out

        with patch("boto3.client"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.check_dlm_lifecycle_policies"
            ) as mock_check:
                mock_check.side_effect = ClientError(
                    {"Error": {"Code": "UnrecognizedClientException"}}, "get_lifecycle_policies"
                )
                disable_dlm_policies("us-east-1")
        captured = capsys.readouterr()
        assert "service not available" in captured.out

        with patch("boto3.client"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.check_dlm_lifecycle_policies"
            ) as mock_check:
                mock_check.side_effect = ClientError(
                    {"Error": {"Code": "ServiceError"}}, "get_lifecycle_policies"
                )
                disable_dlm_policies("us-east-1")
        captured = capsys.readouterr()
        assert "Error checking DLM" in captured.out


class TestDisableEventbridgeBackupRules:
    def test_disable_rules(self, capsys):
        rules = [
            {
                "Name": "daily-snapshot-rule",
                "Description": "Create daily snapshots",
                "State": "ENABLED",
                "ScheduleExpression": "rate(1 day)",
            },
            {
                "Name": "backup-ami-rule",
                "Description": "Backup AMI weekly",
                "State": "ENABLED",
                "ScheduleExpression": "rate(7 days)",
            },
        ]
        with patch("boto3.client") as mock_client:
            mock_events = MagicMock()
            mock_client.return_value = mock_events
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.check_eventbridge_scheduled_rules",
                return_value=rules,
            ):
                disable_eventbridge_backup_rules("us-east-1")
        assert mock_events.disable_rule.call_count == 2
        captured = capsys.readouterr()
        assert "Found 2 EventBridge backup-related rules" in captured.out

    def test_skip_disabled(self, capsys):
        rules = [
            {"Name": "snapshot-rule", "Description": "Snapshots", "State": "DISABLED"},
            {"Name": "other-rule", "Description": "Some other rule", "State": "ENABLED"},
        ]
        with patch("boto3.client") as mock_client:
            mock_events = MagicMock()
            mock_client.return_value = mock_events
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.check_eventbridge_scheduled_rules",
                return_value=rules,
            ):
                disable_eventbridge_backup_rules("us-east-1")
        mock_events.disable_rule.assert_not_called()
        captured = capsys.readouterr()
        assert "already disabled" in captured.out or "No backup-related" in captured.out

    def test_error_handling(self, capsys):
        rules = [{"Name": "snapshot-rule", "Description": "Snapshots", "State": "ENABLED"}]
        with patch("boto3.client") as mock_client:
            mock_events = MagicMock()
            mock_events.disable_rule.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "disable_rule"
            )
            mock_client.return_value = mock_events
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.check_eventbridge_scheduled_rules",
                return_value=rules,
            ):
                disable_eventbridge_backup_rules("us-east-1")
        captured = capsys.readouterr()
        assert "Error disabling EventBridge rule" in captured.out
        with patch("boto3.client") as mock_client:
            with patch(
                "cost_toolkit.scripts.cleanup.aws_backup_disable.check_eventbridge_scheduled_rules"
            ) as mock_check:
                mock_check.side_effect = ClientError(
                    {"Error": {"Code": "ServiceError"}}, "list_rules"
                )
                disable_eventbridge_backup_rules("us-east-1")
        captured = capsys.readouterr()
        assert "Error checking EventBridge rules" in captured.out


class TestCheckBackupVaultPolicies:
    def test_vault_with_recovery_points(self, capsys):
        with patch("boto3.client") as mock_client:
            mock_backup = MagicMock()
            mock_backup.list_backup_vaults.return_value = {
                "BackupVaultList": [
                    {
                        "BackupVaultName": "test-vault",
                        "CreationDate": "2024-01-01",
                    }
                ]
            }
            mock_backup.list_recovery_points_by_backup_vault.return_value = {
                "RecoveryPoints": [{"RecoveryPointArn": "arn:aws:backup:::recovery-point/123"}]
            }
            mock_client.return_value = mock_backup
            check_backup_vault_policies("us-east-1")
        captured = capsys.readouterr()
        assert "Found 1 backup vault(s)" in captured.out
        assert "contains recovery points" in captured.out

    def test_empty_and_no_vaults(self, capsys):
        with patch("boto3.client") as mock_client:
            mock_backup = MagicMock()
            mock_backup.list_backup_vaults.return_value = {
                "BackupVaultList": [
                    {
                        "BackupVaultName": "empty-vault",
                        "CreationDate": "2024-01-01",
                    }
                ]
            }
            mock_backup.list_recovery_points_by_backup_vault.return_value = {"RecoveryPoints": []}
            mock_client.return_value = mock_backup
            check_backup_vault_policies("us-east-1")
        captured = capsys.readouterr()
        assert "Vault is empty" in captured.out
        with patch("boto3.client") as mock_client:
            mock_backup = MagicMock()
            mock_backup.list_backup_vaults.return_value = {"BackupVaultList": []}
            mock_client.return_value = mock_backup
            check_backup_vault_policies("us-east-1")
        captured = capsys.readouterr()
        assert "No backup vaults found" in captured.out

    def test_unrecognized_client(self):
        with patch("boto3.client") as mock_client:
            mock_backup = MagicMock()
            mock_backup.list_backup_vaults.side_effect = ClientError(
                {"Error": {"Code": "UnrecognizedClientException"}}, "list_backup_vaults"
            )
            mock_client.return_value = mock_backup
            check_backup_vault_policies("us-east-1")

    def test_error_handling(self, capsys):
        with patch("boto3.client") as mock_client:
            mock_backup = MagicMock()
            mock_backup.list_backup_vaults.return_value = {
                "BackupVaultList": [
                    {
                        "BackupVaultName": "test-vault",
                        "CreationDate": "2024-01-01",
                    }
                ]
            }
            mock_backup.list_recovery_points_by_backup_vault.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "list_recovery_points_by_backup_vault"
            )
            mock_client.return_value = mock_backup
            check_backup_vault_policies("us-east-1")
        captured = capsys.readouterr()
        assert "Error checking vault contents" in captured.out
        with patch("boto3.client") as mock_client:
            mock_backup = MagicMock()
            mock_backup.list_backup_vaults.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "list_backup_vaults"
            )
            mock_client.return_value = mock_backup
            check_backup_vault_policies("us-east-1")
        captured = capsys.readouterr()
        assert "Error checking backup vaults" in captured.out


class TestMain:

    def test_main_function(self, capsys):
        from cost_toolkit.scripts.cleanup.aws_backup_disable import main

        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable.setup_aws_credentials"):
            with patch("cost_toolkit.scripts.cleanup.aws_backup_disable.disable_aws_backup_plans"):
                with patch("cost_toolkit.scripts.cleanup.aws_backup_disable.disable_dlm_policies"):
                    with patch(
                        "cost_toolkit.scripts.cleanup.aws_backup_disable.disable_eventbridge_backup_rules"
                    ):
                        with patch(
                            "cost_toolkit.scripts.cleanup.aws_backup_disable.check_backup_vault_policies"
                        ):
                            main()
        captured = capsys.readouterr()
        assert "AWS Automated Backup Disable Script" in captured.out
        assert "SUMMARY" in captured.out
        assert "All automated backup services have been disabled" in captured.out
