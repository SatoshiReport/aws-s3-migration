"""Integration and edge case tests for migration_scanner.py

Tests phase transitions, interruption handling, error handling, and edge cases.
"""

from datetime import datetime
from unittest import mock

import pytest
from botocore.exceptions import ClientError

from migration_scanner import BucketScanner, GlacierRestorer, GlacierWaiter
from migration_state_v2 import MigrationStateV2, Phase


class TestPhaseTransitions:
    """Test phase transitions across classes"""

    def test_bucket_scanner_transitions_to_glacier_restore(self):
        """Test BucketScanner transitions to GLACIER_RESTORE phase"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_s3.list_buckets.return_value = {"Buckets": []}

        scanner = BucketScanner(mock_s3, mock_state)
        scanner.scan_all_buckets()

        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_RESTORE)

    def test_glacier_restorer_transitions_to_glacier_wait(self):
        """Test GlacierRestorer transitions to GLACIER_WAIT phase"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_state.get_glacier_files_needing_restore.return_value = []

        restorer = GlacierRestorer(mock_s3, mock_state)
        restorer.request_all_restores()

        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_WAIT)

    def test_glacier_waiter_transitions_to_syncing(self):
        """Test GlacierWaiter transitions to SYNCING phase"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_state.get_files_restoring.return_value = []

        waiter = GlacierWaiter(mock_s3, mock_state)
        waiter.wait_for_restores()

        mock_state.set_current_phase.assert_called_once_with(Phase.SYNCING)


class TestInterruptFlagBehavior:
    """Test interrupt flag behavior across classes"""

    def test_bucket_scanner_interrupt_flag(self):
        """Test BucketScanner interrupt flag behavior"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        scanner = BucketScanner(mock_s3, mock_state)

        assert scanner.interrupted is False
        scanner.interrupted = True
        assert scanner.interrupted is True

    def test_glacier_restorer_interrupt_flag(self):
        """Test GlacierRestorer interrupt flag behavior"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        restorer = GlacierRestorer(mock_s3, mock_state)

        assert restorer.interrupted is False
        restorer.interrupted = True
        assert restorer.interrupted is True

    def test_glacier_waiter_interrupt_flag(self):
        """Test GlacierWaiter interrupt flag behavior"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        waiter = GlacierWaiter(mock_s3, mock_state)

        assert waiter.interrupted is False
        waiter.interrupted = True
        assert waiter.interrupted is True


class TestBucketScannerInterruptExit:
    """Test BucketScanner early exit on interrupt"""

    def test_bucket_scanner_early_exit_on_interrupt(self):
        """Test early exit on interrupt in bucket loop"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_s3.list_buckets.return_value = {
            "Buckets": [
                {"Name": "bucket1"},
                {"Name": "bucket2"},
                {"Name": "bucket3"},
            ]
        }
        mock_s3.get_paginator.return_value.paginate.return_value = []

        scanner = BucketScanner(mock_s3, mock_state)

        call_count = 0

        def count_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                scanner.interrupted = True

        mock_state.save_bucket_status.side_effect = count_calls

        scanner.scan_all_buckets()

        # Should only be called once before interrupt
        assert call_count == 1


class TestGlacierRestorerInterruptExit:
    """Test GlacierRestorer early exit on interrupt"""

    def test_glacier_restorer_early_exit_on_interrupt(self):
        """Test early exit on interrupt in restore loop"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_state.get_glacier_files_needing_restore.return_value = [
            {"bucket": "bucket1", "key": "file1.txt", "storage_class": "GLACIER"},
            {"bucket": "bucket2", "key": "file2.txt", "storage_class": "GLACIER"},
            {"bucket": "bucket3", "key": "file3.txt", "storage_class": "GLACIER"},
        ]

        restorer = GlacierRestorer(mock_s3, mock_state)

        call_count = 0

        def count_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                restorer.interrupted = True

        mock_s3.restore_object.side_effect = count_calls

        restorer.request_all_restores()

        # Should only be called once before interrupt
        assert call_count == 1


class TestGlacierWaiterInterruptExit:
    """Test GlacierWaiter early exit on interrupt"""

    def test_glacier_waiter_early_exit_on_interrupt_during_loop(self):
        """Test early exit on interrupt in waiter loop"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)

        waiter = GlacierWaiter(mock_s3, mock_state)
        waiter.interrupted = True

        waiter.wait_for_restores()

        # When interrupted before loop, still transitions to SYNCING at end
        mock_state.set_current_phase.assert_called_once_with(Phase.SYNCING)


class TestBucketScannerErrorPropagation:
    """Test BucketScanner error propagation"""

    def test_bucket_scanner_handles_pagination_error(self):
        """Test that pagination errors propagate"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "test-bucket"}]}
        mock_s3.get_paginator.return_value.paginate.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "ListObjectsV2"
        )

        scanner = BucketScanner(mock_s3, mock_state)

        with pytest.raises(ClientError):
            scanner.scan_all_buckets()


class TestGlacierRestorerErrorPropagation:
    """Test GlacierRestorer error propagation"""

    def test_glacier_restorer_handles_non_restore_error(self):
        """Test that non-RestoreAlreadyInProgress errors propagate"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_state.get_glacier_files_needing_restore.return_value = [
            {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}
        ]
        error = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}}, "RestoreObject"
        )
        mock_s3.restore_object.side_effect = error

        restorer = GlacierRestorer(mock_s3, mock_state)

        with pytest.raises(ClientError):
            restorer.request_all_restores()


class TestGlacierWaiterErrorHandling:
    """Test GlacierWaiter error handling"""

    def test_glacier_waiter_handles_head_object_error(self):
        """Test that head_object errors are handled gracefully"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        # Use side_effect to return files on first call, then empty on second
        mock_state.get_files_restoring.side_effect = [
            [{"bucket": "test-bucket", "key": "file.txt"}],
            [],  # Empty on retry
        ]
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "HeadObject"
        )

        waiter = GlacierWaiter(mock_s3, mock_state)

        with mock.patch("migration_scanner.time.sleep"):
            waiter.wait_for_restores()

        # Should handle error gracefully and exit
        mock_state.set_current_phase.assert_called_once_with(Phase.SYNCING)
