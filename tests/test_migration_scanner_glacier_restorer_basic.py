"""Unit tests for GlacierRestorer class - Basic operations"""

from migration_scanner import GlacierRestorer
from migration_state_v2 import Phase
from tests.assertions import assert_equal


def test_restorer_initialization(s3_mock, state_mock):
    """Test GlacierRestorer initialization"""
    restorer = GlacierRestorer(s3_mock, state_mock)
    assert restorer.s3 is s3_mock
    assert restorer.state is state_mock
    assert restorer.interrupted is False


def test_request_all_restores_no_glacier_files(restorer, state_mock, capsys):
    """Test when no Glacier files need restore"""
    state_mock.get_glacier_files_needing_restore.return_value = []

    restorer.request_all_restores()

    output = capsys.readouterr().out
    assert "No Glacier files need restore" in output
    state_mock.set_current_phase.assert_called_once_with(Phase.GLACIER_WAIT)


def test_request_all_restores_with_files(restorer, s3_mock, state_mock):
    """Test requesting restores for Glacier files"""
    state_mock.get_glacier_files_needing_restore.return_value = [
        {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}
    ]

    restorer.request_all_restores()

    s3_mock.restore_object.assert_called_once()
    state_mock.mark_glacier_restore_requested.assert_called_once()
    state_mock.set_current_phase.assert_called_once_with(Phase.GLACIER_WAIT)


def test_request_all_restores_multiple_files(restorer, s3_mock, state_mock):
    """Test requesting restores for multiple files"""
    state_mock.get_glacier_files_needing_restore.return_value = [
        {"bucket": "bucket1", "key": "file1.txt", "storage_class": "GLACIER"},
        {"bucket": "bucket2", "key": "file2.txt", "storage_class": "GLACIER"},
        {"bucket": "bucket1", "key": "file3.txt", "storage_class": "DEEP_ARCHIVE"},
    ]

    restorer.request_all_restores()

    assert_equal(s3_mock.restore_object.call_count, 3)
    assert_equal(state_mock.mark_glacier_restore_requested.call_count, 3)


def test_request_all_restores_respects_interrupt(restorer, s3_mock, state_mock):
    """Test that request_all_restores stops on interrupt"""
    state_mock.get_glacier_files_needing_restore.return_value = [
        {"bucket": "test-bucket", "key": "file1.txt", "storage_class": "GLACIER"},
        {"bucket": "test-bucket", "key": "file2.txt", "storage_class": "GLACIER"},
    ]

    def interrupt_on_first_call(*_args, **_kwargs):
        restorer.interrupted = True

    s3_mock.restore_object.side_effect = interrupt_on_first_call

    restorer.request_all_restores()

    # Should only process first file
    assert s3_mock.restore_object.call_count == 1


def test_request_restore_success(restorer, s3_mock, state_mock, capsys):
    """Test successful restore request"""
    file_info = {
        "bucket": "test-bucket",
        "key": "file.txt",
        "storage_class": "GLACIER",
    }

    restorer.request_restore(file_info, 5, 10)

    s3_mock.restore_object.assert_called_once()
    state_mock.mark_glacier_restore_requested.assert_called_once_with("test-bucket", "file.txt")
    output = capsys.readouterr().out
    assert "[5/10]" in output
