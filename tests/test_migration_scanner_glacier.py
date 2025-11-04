"""Unit tests for GlacierRestorer and GlacierWaiter classes from migration_scanner.py"""

from unittest import mock

import pytest
from botocore.exceptions import ClientError

from migration_scanner import GlacierRestorer, GlacierWaiter
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
        file_info = {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}

        restorer._request_restore(file_info, 5, 10)

        mock_s3.restore_object.assert_called_once()
        mock_state.mark_glacier_restore_requested.assert_called_once_with("test-bucket", "file.txt")
        output = capsys.readouterr().out
        assert "[5/10]" in output


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


class TestGlacierWaiterInitialization:
    """Test GlacierWaiter initialization"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    def test_waiter_initialization(self, mock_s3, mock_state):
        """Test GlacierWaiter initialization"""
        waiter = GlacierWaiter(mock_s3, mock_state)
        assert waiter.s3 is mock_s3
        assert waiter.state is mock_state
        assert waiter.interrupted is False


class TestGlacierWaiterBasicWaiting:
    """Test GlacierWaiter basic waiting operations"""

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

    def test_wait_for_restores_no_restoring_files(self, waiter, mock_state, capsys):
        """Test when no files are restoring"""
        mock_state.get_files_restoring.return_value = []

        waiter.wait_for_restores()

        output = capsys.readouterr().out
        assert "PHASE 3/4: WAITING FOR GLACIER RESTORES" in output
        assert "PHASE 3 COMPLETE" in output
        mock_state.set_current_phase.assert_called_once_with(Phase.SYNCING)

    def test_wait_for_restores_with_sleep(self, waiter, mock_s3, mock_state):
        """Test that wait_for_restores sleeps between checks"""
        # Mock _check_restore_status to avoid side_effect issues
        waiter._check_restore_status = mock.Mock(return_value=False)

        mock_state.get_files_restoring.side_effect = [
            [{"bucket": "test-bucket", "key": "file.txt"}],
            [],  # Next check shows no files
        ]

        with mock.patch("migration_scanner.time.sleep") as mock_sleep:
            waiter.wait_for_restores()

            # Should sleep 300 seconds (5 minutes) after first check
            mock_sleep.assert_called_with(300)


class TestGlacierWaiterInterruption:
    """Test GlacierWaiter interruption handling"""

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

    def test_wait_for_restores_respects_interrupt(self, waiter, mock_state):
        """Test that wait_for_restores stops on interrupt"""
        # When interrupted flag is set before entering, loop exits immediately
        waiter.interrupted = True
        with mock.patch("migration_scanner.time.sleep"):
            waiter.wait_for_restores()

        # Should still transition to SYNCING phase after loop exits
        mock_state.set_current_phase.assert_called_once_with(Phase.SYNCING)

    def test_wait_for_restores_stops_on_interrupt_during_check(self, waiter, mock_s3, mock_state):
        """Test interrupt during restore status check"""
        mock_state.get_files_restoring.return_value = [
            {"bucket": "test-bucket", "key": "file1.txt"},
            {"bucket": "test-bucket", "key": "file2.txt"},
        ]

        def interrupt_on_second_file(*args, **kwargs):
            waiter.interrupted = True
            return False

        waiter._check_restore_status = mock.Mock(side_effect=interrupt_on_second_file)

        waiter.wait_for_restores()

        # Should only check first file before interrupt
        assert waiter._check_restore_status.call_count == 1


class TestGlacierWaiterLooping:
    """Test GlacierWaiter loop behavior"""

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

    def test_wait_for_restores_loops_until_complete(self, waiter, mock_s3, mock_state):
        """Test that wait_for_restores loops multiple times"""
        # Mock _check_restore_status to avoid complications
        waiter._check_restore_status = mock.Mock(return_value=False)

        # Simulate 2 check cycles
        mock_state.get_files_restoring.side_effect = [
            [{"bucket": "test-bucket", "key": "file.txt"}],
            [{"bucket": "test-bucket", "key": "file.txt"}],
            [],  # All done
        ]

        with mock.patch("migration_scanner.time.sleep"):
            waiter.wait_for_restores()

        # Should call get_files_restoring 3 times
        assert mock_state.get_files_restoring.call_count == 3  # noqa: PLR2004


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
        result = waiter._check_restore_status(file_info)

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
        result = waiter._check_restore_status(file_info)

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
        result = waiter._check_restore_status(file_info)

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
        result = waiter._check_restore_status(file_info)

        assert result is False
        mock_state.mark_glacier_restored.assert_not_called()
