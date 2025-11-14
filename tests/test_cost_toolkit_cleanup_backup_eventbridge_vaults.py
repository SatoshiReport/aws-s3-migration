"""Tests for EventBridge backup rules and vault operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_backup_disable import (
    check_backup_vault_policies,
    disable_eventbridge_backup_rules,
    main,
)


class TestDisableEventbridgeBackupRules:
    """Test disabling EventBridge backup-related rules."""

    def test_disable_rules(self, capsys):
        """Test disabling multiple EventBridge backup rules."""
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
        """Test skipping already disabled EventBridge rules."""
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
        """Test error handling when disabling EventBridge rules."""
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
    """Test checking backup vault policies and contents."""

    def test_vault_with_recovery_points(self, capsys):
        """Test checking vault containing recovery points."""
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
        """Test checking empty vaults and cases with no vaults."""
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
        """Test handling unrecognized client exception."""
        with patch("boto3.client") as mock_client:
            mock_backup = MagicMock()
            mock_backup.list_backup_vaults.side_effect = ClientError(
                {"Error": {"Code": "UnrecognizedClientException"}}, "list_backup_vaults"
            )
            mock_client.return_value = mock_backup
            check_backup_vault_policies("us-east-1")

    def test_error_handling(self, capsys):
        """Test error handling when checking backup vaults."""
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


def test_main_main_function(capsys):
    """Test main function runs all backup disable operations."""
    with patch("cost_toolkit.scripts.cleanup.aws_backup_disable.setup_aws_credentials"):
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable.disable_aws_backup_plans"):
            with patch("cost_toolkit.scripts.cleanup.aws_backup_disable.disable_dlm_policies"):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_backup_disable."
                    "disable_eventbridge_backup_rules"
                ):
                    with patch(
                        "cost_toolkit.scripts.cleanup.aws_backup_disable."
                        "check_backup_vault_policies"
                    ):
                        main()
    captured = capsys.readouterr()
    assert "AWS Automated Backup Disable Script" in captured.out
    assert "SUMMARY" in captured.out
    assert "All automated backup services have been disabled" in captured.out
