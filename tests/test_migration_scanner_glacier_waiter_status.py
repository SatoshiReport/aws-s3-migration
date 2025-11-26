"""Unit tests for GlacierWaiter class - Restore status checking"""

import pytest
from botocore.exceptions import ClientError


def test_check_restore_status_not_complete(waiter, s3_mock, state_mock):
    """Test restore status check when restore is still ongoing"""
    s3_mock.head_object.return_value = {
        "Restore": 'ongoing-request="true"',
    }

    file_info = {"bucket": "test-bucket", "key": "file.txt"}
    result = waiter.check_restore_status(file_info)

    assert result is False
    state_mock.mark_glacier_restored.assert_not_called()


def test_check_restore_status_complete(waiter, s3_mock, state_mock):
    """Test restore status check when restore is complete"""
    s3_mock.head_object.return_value = {
        "Restore": 'ongoing-request="false"',
    }

    file_info = {"bucket": "test-bucket", "key": "file.txt"}
    result = waiter.check_restore_status(file_info)

    assert result is True
    state_mock.mark_glacier_restored.assert_called_once_with("test-bucket", "file.txt")


def test_check_restore_status_no_restore_header(waiter, s3_mock, state_mock):
    """Test restore status when Restore header is missing"""
    s3_mock.head_object.return_value = {}

    file_info = {"bucket": "test-bucket", "key": "file.txt"}
    result = waiter.check_restore_status(file_info)

    assert result is False
    state_mock.mark_glacier_restored.assert_not_called()


def test_check_restore_status_raises_on_error(waiter, s3_mock, state_mock):
    """Test restore status check raises ClientError on API failure."""
    error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
    s3_mock.head_object.side_effect = ClientError(error_response, "HeadObject")

    file_info = {"bucket": "test-bucket", "key": "file.txt"}
    with pytest.raises(ClientError):
        waiter.check_restore_status(file_info)

    state_mock.mark_glacier_restored.assert_not_called()
