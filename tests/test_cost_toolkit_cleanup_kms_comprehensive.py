"""Comprehensive tests for aws_kms_cleanup.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_kms_cleanup import (
    cleanup_kms_keys,
    get_keys_to_remove,
    process_single_key,
    schedule_key_deletion,
)


class TestGetKeysToRemove:
    """Tests for get_keys_to_remove function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        keys = get_keys_to_remove()
        assert isinstance(keys, list)

    def test_keys_have_required_fields(self):
        """Test that keys have required fields."""
        keys = get_keys_to_remove()
        for key in keys:
            assert "region" in key
            assert "key_id" in key
            assert "description" in key

    def test_returns_expected_number(self):
        """Test that function returns expected number of keys."""
        keys = get_keys_to_remove()
        assert len(keys) > 0


class TestScheduleKeyDeletion:
    """Tests for schedule_key_deletion function."""

    def test_schedule_enabled_key(self, capsys):
        """Test scheduling deletion for enabled key."""
        mock_client = MagicMock()
        mock_client.schedule_key_deletion.return_value = {"DeletionDate": "2024-01-15"}

        result = schedule_key_deletion(mock_client, "key-123", "Enabled")

        assert result is True
        mock_client.schedule_key_deletion.assert_called_once_with(KeyId="key-123", PendingWindowInDays=7)
        captured = capsys.readouterr()
        assert "Scheduled for deletion" in captured.out

    def test_schedule_disabled_key(self):
        """Test scheduling deletion for disabled key."""
        mock_client = MagicMock()
        mock_client.schedule_key_deletion.return_value = {"DeletionDate": "2024-01-15"}

        result = schedule_key_deletion(mock_client, "key-123", "Disabled")

        assert result is True

    def test_schedule_pending_deletion_key(self, capsys):
        """Test handling key already pending deletion."""
        mock_client = MagicMock()

        result = schedule_key_deletion(mock_client, "key-123", "PendingDeletion")

        assert result is True
        captured = capsys.readouterr()
        assert "Already pending deletion" in captured.out

    def test_schedule_invalid_state(self, capsys):
        """Test handling invalid key state."""
        mock_client = MagicMock()

        result = schedule_key_deletion(mock_client, "key-123", "Creating")

        assert result is False
        captured = capsys.readouterr()
        assert "cannot delete" in captured.out

    def test_schedule_already_scheduled_error(self, capsys):
        """Test handling already scheduled error."""
        mock_client = MagicMock()
        mock_client.schedule_key_deletion.side_effect = ClientError(
            {"Error": {"Code": "AlreadyScheduled", "Message": "already scheduled"}},
            "schedule_key_deletion",
        )

        result = schedule_key_deletion(mock_client, "key-123", "Enabled")

        assert result is True
        captured = capsys.readouterr()
        assert "Already scheduled" in captured.out

    def test_schedule_other_error(self, capsys):
        """Test handling other errors."""
        mock_client = MagicMock()
        mock_client.schedule_key_deletion.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "schedule_key_deletion")

        result = schedule_key_deletion(mock_client, "key-123", "Enabled")

        assert result is False
        captured = capsys.readouterr()
        assert "Error scheduling deletion" in captured.out


class TestProcessSingleKey:
    """Tests for process_single_key function."""

    def test_process_key_success(self):
        """Test successful key processing."""
        key_info = {
            "region": "us-east-1",
            "key_id": "key-123",
            "description": "Test key",
        }

        with patch("boto3.client") as mock_client:
            mock_kms = MagicMock()
            mock_kms.describe_key.return_value = {"KeyMetadata": {"KeyState": "Enabled"}}
            mock_kms.schedule_key_deletion.return_value = {"DeletionDate": "2024-01-15"}
            mock_client.return_value = mock_kms

            result = process_single_key(key_info)

        assert result is True

    def test_process_key_describe_error(self, capsys):
        """Test handling error when describing key."""
        key_info = {
            "region": "us-east-1",
            "key_id": "key-123",
            "description": "Test key",
        }

        with patch("boto3.client") as mock_client:
            mock_kms = MagicMock()
            mock_kms.describe_key.side_effect = ClientError({"Error": {"Code": "NotFoundException"}}, "describe_key")
            mock_client.return_value = mock_kms

            result = process_single_key(key_info)

        assert result is False
        captured = capsys.readouterr()
        assert "Error accessing key" in captured.out


class TestCleanupKmsKeys:
    """Tests for cleanup_kms_keys function."""

    def test_cleanup_all_successful(self, capsys):
        """Test cleanup when all keys are processed successfully."""
        with patch("cost_toolkit.scripts.cleanup.aws_kms_cleanup.get_keys_to_remove") as mock_get:
            mock_get.return_value = [
                {"region": "us-east-1", "key_id": "key-1", "description": "Key 1"},
                {"region": "us-west-2", "key_id": "key-2", "description": "Key 2"},
            ]

            with patch("cost_toolkit.scripts.cleanup.aws_kms_cleanup.process_single_key", return_value=True):
                cleanup_kms_keys()

        captured = capsys.readouterr()
        assert "AWS KMS Key Cleanup" in captured.out

    def test_cleanup_partial_success(self, capsys):
        """Test cleanup with some failures."""
        with patch("cost_toolkit.scripts.cleanup.aws_kms_cleanup.get_keys_to_remove") as mock_get:
            mock_get.return_value = [
                {"region": "us-east-1", "key_id": "key-1", "description": "Key 1"},
            ]

            with patch(
                "cost_toolkit.scripts.cleanup.aws_kms_cleanup.process_single_key",
                return_value=False,
            ):
                cleanup_kms_keys()

        captured = capsys.readouterr()
        assert "AWS KMS Key Cleanup" in captured.out

    def test_cleanup_no_keys(self, capsys):
        """Test cleanup with no keys to process."""
        with patch("cost_toolkit.scripts.cleanup.aws_kms_cleanup.get_keys_to_remove", return_value=[]):
            cleanup_kms_keys()

        captured = capsys.readouterr()
        assert "AWS KMS Key Cleanup" in captured.out
