"""Unit tests for GlacierWaiter class - Basic operations"""

from unittest import mock

import pytest

from migration_scanner import GlacierWaiter
from migration_state_v2 import MigrationStateV2, Phase


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
        assert mock_state.get_files_restoring.call_count == 3
