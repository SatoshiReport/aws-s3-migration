"""Unit tests for GlacierWaiter class - Basic operations"""

from unittest import mock

from migration_scanner import GlacierWaiter
from migration_state_v2 import Phase
from tests.assertions import assert_equal


def test_waiter_initialization(s3_mock, state_mock):
    """Test GlacierWaiter initialization"""
    waiter = GlacierWaiter(s3_mock, state_mock)
    assert waiter.s3 is s3_mock
    assert waiter.state is state_mock
    assert waiter.interrupted is False


class TestGlacierWaiterBasicWaiting:
    """Test GlacierWaiter basic waiting operations"""

    def test_wait_for_restores_no_restoring_files(self, waiter, state_mock, capsys):
        """Test when no files are restoring"""
        state_mock.get_files_restoring.return_value = []

        waiter.wait_for_restores()

        output = capsys.readouterr().out
        assert "PHASE 3/4: WAITING FOR GLACIER RESTORES" in output
        assert "PHASE 3 COMPLETE" in output
        state_mock.set_current_phase.assert_called_once_with(Phase.SYNCING)

    def test_wait_for_restores_with_wait_interval(self, waiter, state_mock):
        """Test that wait_for_restores waits between checks"""
        # Mock _check_restore_status to avoid side_effect issues
        waiter.check_restore_status = mock.Mock(return_value=False)

        state_mock.get_files_restoring.side_effect = [
            [{"bucket": "test-bucket", "key": "file.txt"}],
            [],  # Next check shows no files
        ]

        with mock.patch.object(waiter, "_wait_with_interrupt") as mock_wait:
            waiter.wait_for_restores()

            # Should wait 300 seconds (5 minutes) after first check
            mock_wait.assert_called_with(300)


class TestGlacierWaiterInterruption:
    """Test GlacierWaiter interruption handling"""

    def test_wait_for_restores_respects_interrupt(self, waiter, state_mock):
        """Test that wait_for_restores stops on interrupt"""
        # When interrupted flag is set before entering, loop exits immediately
        waiter.interrupted = True
        waiter.wait_for_restores()

        # Should still transition to SYNCING phase after loop exits
        state_mock.set_current_phase.assert_called_once_with(Phase.SYNCING)

    def test_wait_for_restores_stops_on_interrupt_during_check(self, waiter, state_mock):
        """Test interrupt during restore status check"""
        state_mock.get_files_restoring.return_value = [
            {"bucket": "test-bucket", "key": "file1.txt"},
            {"bucket": "test-bucket", "key": "file2.txt"},
        ]

        def interrupt_on_second_file(*_args, **_kwargs):
            waiter.interrupted = True
            return False

        waiter.check_restore_status = mock.Mock(side_effect=interrupt_on_second_file)

        waiter.wait_for_restores()

        # Should only check first file before interrupt
        assert waiter.check_restore_status.call_count == 1


def test_wait_for_restores_loops_until_complete(waiter, state_mock):
    """Test that wait_for_restores loops multiple times"""
    # Mock _check_restore_status to avoid complications
    waiter.check_restore_status = mock.Mock(return_value=False)

    # Simulate 2 check cycles
    state_mock.get_files_restoring.side_effect = [
        [{"bucket": "test-bucket", "key": "file.txt"}],
        [{"bucket": "test-bucket", "key": "file.txt"}],
        [],  # All done
    ]

    with mock.patch.object(waiter, "_wait_with_interrupt"):
        waiter.wait_for_restores()

    # Should call get_files_restoring 3 times
    assert_equal(state_mock.get_files_restoring.call_count, 3)
