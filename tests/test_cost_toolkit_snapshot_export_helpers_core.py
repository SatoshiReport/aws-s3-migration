"""Tests for core helper functions in snapshot_export_fixed/export_helpers.py"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.snapshot_export_fixed.constants import (
    MAX_CONSECUTIVE_API_ERRORS,
    ExportAPIException,
    ExportTaskDeletedException,
    ExportTaskFailedException,
)
from cost_toolkit.scripts.optimization.snapshot_export_fixed.export_helpers import (
    MonitoringState,
    _check_terminal_state_fixed,
    _fetch_export_task_status,
    _handle_api_errors,
    _handle_task_deletion_recovery,
    _print_export_status,
    _start_export_task_fixed,
    _track_progress_change,
)
from tests.assertions import assert_equal


def test_monitoring_state_initialization():
    """Test MonitoringState dataclass initialization."""
    start_time = time.time()
    state = MonitoringState(start_time=start_time, last_progress_change_time=start_time)

    assert_equal(state.start_time, start_time)
    assert_equal(state.last_progress_change_time, start_time)
    assert_equal(state.last_progress_value, 0)
    assert_equal(state.consecutive_api_errors, 0)


def test_start_export_task_fixed():
    """Test _start_export_task_fixed starts export and returns task ID and key."""
    mock_ec2 = MagicMock()

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.export_helpers."
        "start_ami_export_task",
        return_value=("export-123", "ebs-snapshots/ami-123/export-123.vmdk"),
    ) as mock_start:
        task_id, s3_key = _start_export_task_fixed(mock_ec2, "ami-123", "test-bucket")

        assert_equal(task_id, "export-123")
        assert_equal(s3_key, "ebs-snapshots/ami-123/export-123.vmdk")
        mock_start.assert_called_once_with(mock_ec2, "ami-123", "test-bucket")


def test_handle_task_deletion_recovery_success():
    """Test _handle_task_deletion_recovery when S3 file is complete."""
    mock_s3 = MagicMock()

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.export_helpers."
        "check_s3_file_completion",
        return_value={"size_gb": 50.0, "size_bytes": 53687091200},
    ) as mock_check:
        success, key = _handle_task_deletion_recovery(
            mock_s3, "test-bucket", "test-key.vmdk", 50, 2.5
        )

        assert_equal(success, True)
        assert_equal(key, "test-key.vmdk")
        mock_check.assert_called_once_with(
            mock_s3, "test-bucket", "test-key.vmdk", 50, fast_check=True
        )


def test_handle_task_deletion_recovery_failure():
    """Test _handle_task_deletion_recovery raises exception when S3 file invalid."""
    mock_s3 = MagicMock()

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.export_helpers."
        "check_s3_file_completion",
        side_effect=Exception("S3 file not found"),
    ):
        try:
            _handle_task_deletion_recovery(mock_s3, "test-bucket", "test-key.vmdk", 50, 2.5)
            assert False, "Expected ExportTaskDeletedException to be raised"
        except ExportTaskDeletedException as exc:
            assert "Export task deleted" in str(exc)
            assert "no valid S3 file found" in str(exc)


def test_fetch_export_task_status():
    """Test _fetch_export_task_status fetches task successfully."""
    mock_ec2 = MagicMock()
    mock_task = {"ExportImageTaskId": "export-123", "Status": "active"}

    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.export_helpers."
        "validate_export_task_exists",
        return_value=mock_task,
    ) as mock_validate:
        task, errors = _fetch_export_task_status(mock_ec2, "export-123")

        assert_equal(task, mock_task)
        assert_equal(errors, 0)
        mock_validate.assert_called_once_with(mock_ec2, "export-123")


def test_check_terminal_state_fixed_completed():
    """Test _check_terminal_state_fixed detects completed status."""
    mock_task = {"Status": "completed", "Progress": "100"}

    is_terminal, terminal_type = _check_terminal_state_fixed(mock_task, "completed", 2.5)

    assert_equal(is_terminal, True)
    assert_equal(terminal_type, "completed")


def test_check_terminal_state_fixed_failed():
    """Test _check_terminal_state_fixed raises exception on failed status."""
    mock_task = {"Status": "failed", "StatusMessage": "Export failed due to error"}

    try:
        _check_terminal_state_fixed(mock_task, "failed", 2.5)
        assert False, "Expected ExportTaskFailedException to be raised"
    except ExportTaskFailedException as exc:
        assert "AWS export failed" in str(exc)
        assert "2.5 hours" in str(exc)
        assert "Export failed due to error" in str(exc)


def test_check_terminal_state_fixed_deleted():
    """Test _check_terminal_state_fixed detects deleted status."""
    mock_task = {"Status": "deleted"}

    is_terminal, terminal_type = _check_terminal_state_fixed(mock_task, "deleted", 1.0)

    assert_equal(is_terminal, True)
    assert_equal(terminal_type, "deleted")


def test_check_terminal_state_fixed_not_terminal():
    """Test _check_terminal_state_fixed returns False for non-terminal status."""
    mock_task = {"Status": "active", "Progress": "50"}

    is_terminal, terminal_type = _check_terminal_state_fixed(mock_task, "active", 1.0)

    assert_equal(is_terminal, False)
    assert_equal(terminal_type, None)


def test_check_terminal_state_fixed_failed_no_message():
    """Test _check_terminal_state_fixed handles failed status without message."""
    mock_task = {"Status": "failed"}

    try:
        _check_terminal_state_fixed(mock_task, "failed", 3.0)
        assert False, "Expected ExportTaskFailedException to be raised"
    except ExportTaskFailedException as exc:
        assert "AWS export failed" in str(exc)
        assert "Unknown error" in str(exc)


def test_print_export_status():
    """Test _print_export_status calls print_export_status."""
    with patch(
        "cost_toolkit.scripts.optimization.snapshot_export_fixed.export_helpers.print_export_status"
    ) as mock_print:
        _print_export_status("active", 50, "Exporting...", 1.5)

        mock_print.assert_called_once_with("active", 50, "Exporting...", 1.5)


def test_track_progress_change_with_progress():
    """Test _track_progress_change updates state when progress changes."""
    current_time = time.time()
    state = MonitoringState(start_time=current_time, last_progress_change_time=current_time)

    _track_progress_change(state, 25, current_time + 60)

    assert_equal(state.last_progress_value, 25)
    assert_equal(state.last_progress_change_time, current_time + 60)


def test_track_progress_change_no_change():
    """Test _track_progress_change does not update when progress unchanged."""
    current_time = time.time()
    state = MonitoringState(
        start_time=current_time,
        last_progress_change_time=current_time,
        last_progress_value=50,
    )

    original_time = state.last_progress_change_time
    _track_progress_change(state, 50, current_time + 60)

    assert_equal(state.last_progress_value, 50)
    assert_equal(state.last_progress_change_time, original_time)


def test_handle_api_errors_increments_counter():
    """Test _handle_api_errors increments error counter."""
    state = MonitoringState(start_time=time.time(), last_progress_change_time=time.time())
    error = ClientError({"Error": {"Code": "Throttling"}}, "describe_export_image_tasks")

    _handle_api_errors(state, error)

    assert_equal(state.consecutive_api_errors, 1)


def test_handle_api_errors_raises_on_max_errors():
    """Test _handle_api_errors raises exception after max consecutive errors."""
    state = MonitoringState(
        start_time=time.time(),
        last_progress_change_time=time.time(),
        consecutive_api_errors=MAX_CONSECUTIVE_API_ERRORS - 1,
    )
    error = ClientError({"Error": {"Code": "Throttling"}}, "describe_export_image_tasks")

    try:
        _handle_api_errors(state, error)
        assert False, "Expected ExportAPIException to be raised"
    except ExportAPIException as exc:
        assert "Too many consecutive API errors" in str(exc)
        assert str(MAX_CONSECUTIVE_API_ERRORS) in str(exc)
