"""Unit tests for GlacierRestorer class - Advanced operations"""

from unittest import mock

import pytest
from botocore.exceptions import ClientError

from migration_scanner import GlacierRestorer
from migration_state_v2 import MigrationStateV2


class TestGlacierRestorerStorageClassTiers:
    """Test GlacierRestorer storage class tier selection"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def restorer(self, mock_s3, mock_state):
        """Create GlacierRestorer instance"""
        return GlacierRestorer(mock_s3, mock_state)

    def test_request_restore_for_glacier(self, restorer, mock_s3, mock_state):
        """Test requesting restore for GLACIER storage class"""
        with mock.patch("migration_scanner.config.GLACIER_RESTORE_TIER", "Standard"):
            with mock.patch("migration_scanner.config.GLACIER_RESTORE_DAYS", 1):
                file_info = {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}

                restorer._request_restore(file_info, 1, 1)

                # Should use configured tier for GLACIER
                call_args = mock_s3.restore_object.call_args
                assert call_args[1]["RestoreRequest"]["GlacierJobParameters"]["Tier"] == "Standard"

    def test_request_restore_for_deep_archive(self, restorer, mock_s3, mock_state):
        """Test requesting restore for DEEP_ARCHIVE uses Bulk tier"""
        with mock.patch("migration_scanner.config.GLACIER_RESTORE_DAYS", 1):
            file_info = {
                "bucket": "test-bucket",
                "key": "file.txt",
                "storage_class": "DEEP_ARCHIVE",
            }

            restorer._request_restore(file_info, 1, 1)

            # Should use Bulk tier for DEEP_ARCHIVE
            call_args = mock_s3.restore_object.call_args
            assert call_args[1]["RestoreRequest"]["GlacierJobParameters"]["Tier"] == "Bulk"


class TestGlacierRestorerErrorHandling:
    """Test GlacierRestorer error handling"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def restorer(self, mock_s3, mock_state):
        """Create GlacierRestorer instance"""
        return GlacierRestorer(mock_s3, mock_state)

    def test_request_restore_already_in_progress(self, restorer, mock_s3, mock_state):
        """Test handling RestoreAlreadyInProgress error"""
        error_response = {
            "Error": {"Code": "RestoreAlreadyInProgress", "Message": "Already restoring"}
        }
        mock_s3.restore_object.side_effect = ClientError(error_response, "RestoreObject")

        file_info = {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}

        # Should not raise, should mark as requested
        restorer._request_restore(file_info, 1, 1)

        mock_state.mark_glacier_restore_requested.assert_called_once()

    def test_request_restore_other_error(self, restorer, mock_s3, mock_state):
        """Test that other errors are raised"""
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
        mock_s3.restore_object.side_effect = ClientError(error_response, "RestoreObject")

        file_info = {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}

        # Should raise because it's not RestoreAlreadyInProgress
        with pytest.raises(ClientError):
            restorer._request_restore(file_info, 1, 1)


class TestGlacierRestorerConfiguration:
    """Test GlacierRestorer configuration usage"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def restorer(self, mock_s3, mock_state):
        """Create GlacierRestorer instance"""
        return GlacierRestorer(mock_s3, mock_state)

    def test_request_restore_uses_correct_config_values(self, restorer, mock_s3, mock_state):
        """Test that restore request uses config values"""
        with mock.patch("migration_scanner.config.GLACIER_RESTORE_TIER", "Expedited"):
            with mock.patch("migration_scanner.config.GLACIER_RESTORE_DAYS", 5):
                file_info = {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}

                restorer._request_restore(file_info, 1, 1)

                call_args = mock_s3.restore_object.call_args
                restore_request = call_args[1]["RestoreRequest"]
                assert restore_request["Days"] == 5  # noqa: PLR2004
                assert restore_request["GlacierJobParameters"]["Tier"] == "Expedited"
