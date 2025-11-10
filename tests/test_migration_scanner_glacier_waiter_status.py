"""Unit tests for GlacierWaiter class - Restore status checking"""

from unittest import mock

import pytest
from botocore.exceptions import ClientError

from migration_scanner import GlacierWaiter
from migration_state_v2 import MigrationStateV2


class TestGlacierWaiterRestoreIncomplete:
    """Test GlacierWaiter incomplete restore status"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def waiter(self, mock_s3, mock_state):
        """Create GlacierWaiter instance"""
        return GlacierWaiter(mock_s3, mock_state)

    def test_check_restore_status_not_complete(self, waiter, mock_s3, mock_state):
        """Test restore status check when restore is still ongoing"""
        mock_s3.head_object.return_value = {
            "Restore": 'ongoing-request="true"',
        }

        file_info = {"bucket": "test-bucket", "key": "file.txt"}
        result = waiter.check_restore_status(file_info)

        assert result is False
        mock_state.mark_glacier_restored.assert_not_called()


class TestGlacierWaiterRestoreComplete:
    """Test GlacierWaiter complete restore status"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def waiter(self, mock_s3, mock_state):
        """Create GlacierWaiter instance"""
        return GlacierWaiter(mock_s3, mock_state)

    def test_check_restore_status_complete(self, waiter, mock_s3, mock_state):
        """Test restore status check when restore is complete"""
        mock_s3.head_object.return_value = {
            "Restore": 'ongoing-request="false"',
        }

        file_info = {"bucket": "test-bucket", "key": "file.txt"}
        result = waiter.check_restore_status(file_info)

        assert result is True
        mock_state.mark_glacier_restored.assert_called_once_with("test-bucket", "file.txt")


class TestGlacierWaiterMissingRestoreHeader:
    """Test GlacierWaiter with missing Restore header"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def waiter(self, mock_s3, mock_state):
        """Create GlacierWaiter instance"""
        return GlacierWaiter(mock_s3, mock_state)

    def test_check_restore_status_no_restore_header(self, waiter, mock_s3, mock_state):
        """Test restore status when Restore header is missing"""
        mock_s3.head_object.return_value = {}

        file_info = {"bucket": "test-bucket", "key": "file.txt"}
        result = waiter.check_restore_status(file_info)

        assert result is False
        mock_state.mark_glacier_restored.assert_not_called()


class TestGlacierWaiterErrorHandling:
    """Test GlacierWaiter error handling"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def waiter(self, mock_s3, mock_state):
        """Create GlacierWaiter instance"""
        return GlacierWaiter(mock_s3, mock_state)

    def test_check_restore_status_handles_error(self, waiter, mock_s3, mock_state):
        """Test restore status check handles errors gracefully"""
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        mock_s3.head_object.side_effect = ClientError(error_response, "HeadObject")

        file_info = {"bucket": "test-bucket", "key": "file.txt"}
        result = waiter.check_restore_status(file_info)

        assert result is False
        mock_state.mark_glacier_restored.assert_not_called()
