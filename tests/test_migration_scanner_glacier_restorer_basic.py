"""Unit tests for GlacierRestorer class - Basic operations"""

from unittest import mock

import pytest
from botocore.exceptions import ClientError

from migration_scanner import GlacierRestorer
from migration_state_v2 import MigrationStateV2, Phase


class TestGlacierRestorerInitialization:
    """Test GlacierRestorer initialization"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    def test_restorer_initialization(self, mock_s3, mock_state):
        """Test GlacierRestorer initialization"""
        restorer = GlacierRestorer(mock_s3, mock_state)
        assert restorer.s3 is mock_s3
        assert restorer.state is mock_state
        assert restorer.interrupted is False


class TestGlacierRestorerNoFiles:
    """Test GlacierRestorer with no Glacier files"""

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

    def test_request_all_restores_no_glacier_files(self, restorer, mock_state, capsys):
        """Test when no Glacier files need restore"""
        mock_state.get_glacier_files_needing_restore.return_value = []

        restorer.request_all_restores()

        output = capsys.readouterr().out
        assert "No Glacier files need restore" in output
        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_WAIT)


class TestGlacierRestorerSingleFile:
    """Test GlacierRestorer with single file"""

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

    def test_request_all_restores_with_files(self, restorer, mock_s3, mock_state, capsys):
        """Test requesting restores for Glacier files"""
        mock_state.get_glacier_files_needing_restore.return_value = [
            {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}
        ]

        restorer.request_all_restores()

        mock_s3.restore_object.assert_called_once()
        mock_state.mark_glacier_restore_requested.assert_called_once()
        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_WAIT)


class TestGlacierRestorerMultipleFiles:
    """Test GlacierRestorer with multiple files"""

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

    def test_request_all_restores_multiple_files(self, restorer, mock_s3, mock_state):
        """Test requesting restores for multiple files"""
        mock_state.get_glacier_files_needing_restore.return_value = [
            {"bucket": "bucket1", "key": "file1.txt", "storage_class": "GLACIER"},
            {"bucket": "bucket2", "key": "file2.txt", "storage_class": "GLACIER"},
            {"bucket": "bucket1", "key": "file3.txt", "storage_class": "DEEP_ARCHIVE"},
        ]

        restorer.request_all_restores()

        assert mock_s3.restore_object.call_count == 3  # noqa: PLR2004
        assert mock_state.mark_glacier_restore_requested.call_count == 3  # noqa: PLR2004


class TestGlacierRestorerInterruption:
    """Test GlacierRestorer interruption handling"""

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

    def test_request_all_restores_respects_interrupt(self, restorer, mock_s3, mock_state):
        """Test that request_all_restores stops on interrupt"""
        mock_state.get_glacier_files_needing_restore.return_value = [
            {"bucket": "test-bucket", "key": "file1.txt", "storage_class": "GLACIER"},
            {"bucket": "test-bucket", "key": "file2.txt", "storage_class": "GLACIER"},
        ]

        def interrupt_on_first_call(*args, **kwargs):
            restorer.interrupted = True

        mock_s3.restore_object.side_effect = interrupt_on_first_call

        restorer.request_all_restores()

        # Should only process first file
        assert mock_s3.restore_object.call_count == 1


class TestGlacierRestorerSuccessOutput:
    """Test GlacierRestorer success output"""

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

    def test_request_restore_success(self, restorer, mock_s3, mock_state, capsys):
        """Test successful restore request"""
        file_info = {
            "bucket": "test-bucket",
            "key": "file.txt",
            "storage_class": "GLACIER",
        }

        restorer._request_restore(file_info, 5, 10)

        mock_s3.restore_object.assert_called_once()
        mock_state.mark_glacier_restore_requested.assert_called_once_with("test-bucket", "file.txt")
        output = capsys.readouterr().out
        assert "[5/10]" in output
