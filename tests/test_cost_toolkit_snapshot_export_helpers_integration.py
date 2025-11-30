"""Tests for monitoring and integration functions in snapshot_export_fixed/export_helpers.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.snapshot_export_fixed.constants import (
    EXPORT_MAX_DURATION_HOURS,
    ExportTaskDeletedException,
    ExportTaskStuckException,
)
from cost_toolkit.scripts.optimization.snapshot_export_fixed.export_helpers import (
    export_ami_to_s3_with_recovery,
    monitor_export_with_recovery,
)
from tests.assertions import assert_equal

EXPORT_HELPERS_PATH = "cost_toolkit.scripts.optimization.snapshot_export_fixed.export_helpers."


def _helpers_path(attr: str) -> str:
    return f"{EXPORT_HELPERS_PATH}{attr}"


def test_monitor_export_with_recovery_success():
    """Test monitor_export_with_recovery completes successfully."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()

    mock_task_active = {"Status": "active", "Progress": "50", "StatusMessage": "Exporting"}
    mock_task_complete = {"Status": "completed", "Progress": "100", "StatusMessage": "Done"}

    with patch(
        (_helpers_path("_fetch_export_task_status")),
        side_effect=[
            (mock_task_active, 0),
            (mock_task_complete, 0),
        ],
    ):
        with patch((_helpers_path("_print_export_status"))):
            with patch((_helpers_path("_track_progress_change"))):
                with patch((_helpers_path("_WAIT_EVENT"))):
                    with patch("time.sleep"):
                        success, key = monitor_export_with_recovery(
                            mock_ec2,
                            mock_s3,
                            "export-123",
                            "test-key.vmdk",
                            bucket_name="test-bucket",
                            snapshot_size_gb=50,
                        )

                        assert_equal(success, True)
                        assert_equal(key, "test-key.vmdk")


def test_monitor_export_with_recovery_max_duration():
    """Test monitor_export_with_recovery raises exception on max duration."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()

    with patch(_helpers_path("_WAIT_EVENT")):
        with patch("time.time", side_effect=[0, (EXPORT_MAX_DURATION_HOURS + 1) * 3600]):
            try:
                monitor_export_with_recovery(
                    mock_ec2,
                    mock_s3,
                    "export-123",
                    "test-key.vmdk",
                    bucket_name="test-bucket",
                    snapshot_size_gb=50,
                )
                assert False, "Expected ExportTaskStuckException to be raised"
            except ExportTaskStuckException as exc:
                assert "exceeded maximum duration" in str(exc)
                assert str(EXPORT_MAX_DURATION_HOURS) in str(exc)


def test_monitor_export_with_recovery_task_deleted():
    """Test monitor_export_with_recovery handles task deletion."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()

    deleted_exc = ExportTaskDeletedException("Task deleted")
    with patch(
        _helpers_path("_fetch_export_task_status"),
        side_effect=deleted_exc,
    ):
        with patch(
            _helpers_path("_handle_task_deletion_recovery"),
            return_value=(True, "test-key.vmdk"),
        ) as mock_handle:
            success, key = monitor_export_with_recovery(
                mock_ec2,
                mock_s3,
                "export-123",
                "test-key.vmdk",
                bucket_name="test-bucket",
                snapshot_size_gb=50,
            )

            assert_equal(success, True)
            assert_equal(key, "test-key.vmdk")
            mock_handle.assert_called_once()


def test_monitor_export_with_recovery_api_errors():
    """Test monitor_export_with_recovery handles API errors and retries."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()

    mock_task_complete = {"Status": "completed", "Progress": "100"}
    throttling_error = ClientError({"Error": {"Code": "Throttling"}}, "describe_export_image_tasks")

    with patch(
        _helpers_path("_fetch_export_task_status"),
        side_effect=[throttling_error, (mock_task_complete, 0)],
    ):
        with patch(_helpers_path("_handle_api_errors")) as mock_handle_errors:
            with patch(_helpers_path("_print_export_status")):
                with patch(_helpers_path("_track_progress_change")):
                    with patch(_helpers_path("_WAIT_EVENT")):
                        with patch("time.sleep"):
                            success, _ = monitor_export_with_recovery(
                                mock_ec2,
                                mock_s3,
                                "export-123",
                                "test-key.vmdk",
                                bucket_name="test-bucket",
                                snapshot_size_gb=50,
                            )

                            assert_equal(success, True)
                            assert mock_handle_errors.call_count == 1


def test_monitor_export_with_recovery_terminal_deleted():
    """Test monitor_export_with_recovery handles terminal deleted state."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()

    mock_task_deleted = {"Status": "deleted", "Progress": "N/A"}

    with patch(
        _helpers_path("_fetch_export_task_status"),
        return_value=(mock_task_deleted, 0),
    ):
        with patch(_helpers_path("_print_export_status")):
            with patch(_helpers_path("_track_progress_change")):
                with patch(
                    _helpers_path("_handle_task_deletion_recovery"),
                    return_value=(True, "recovered-key.vmdk"),
                ) as mock_handle:
                    with patch(_helpers_path("_WAIT_EVENT")):
                        with patch("time.sleep"):
                            success, key = monitor_export_with_recovery(
                                mock_ec2,
                                mock_s3,
                                "export-123",
                                "test-key.vmdk",
                                bucket_name="test-bucket",
                                snapshot_size_gb=50,
                            )

                            assert_equal(success, True)
                            assert_equal(key, "recovered-key.vmdk")
                            mock_handle.assert_called_once()


def test_monitor_export_with_recovery_resets_api_errors():
    """Test monitor_export_with_recovery resets consecutive API errors on success."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()

    mock_task_complete = {"Status": "completed", "Progress": "100"}

    with patch(
        _helpers_path("_fetch_export_task_status"),
        return_value=(mock_task_complete, 0),
    ):
        with patch(_helpers_path("_print_export_status")):
            with patch(_helpers_path("_track_progress_change")):
                with patch(_helpers_path("_WAIT_EVENT")):
                    with patch("time.sleep"):
                        success, _ = monitor_export_with_recovery(
                            mock_ec2,
                            mock_s3,
                            "export-123",
                            "test-key.vmdk",
                            bucket_name="test-bucket",
                            snapshot_size_gb=50,
                        )

                        assert_equal(success, True)


def test_monitor_export_with_recovery_progress_tracking():
    """Test monitor_export_with_recovery tracks progress changes correctly."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()

    mock_task_25 = {"Status": "active", "Progress": "25", "StatusMessage": ""}
    mock_task_50 = {"Status": "active", "Progress": "50", "StatusMessage": ""}
    mock_task_complete = {"Status": "completed", "Progress": "100", "StatusMessage": ""}

    with patch(
        _helpers_path("_fetch_export_task_status"),
        side_effect=[
            (mock_task_25, 0),
            (mock_task_50, 0),
            (mock_task_complete, 0),
        ],
    ):
        with patch(_helpers_path("_print_export_status")):
            with patch(_helpers_path("_track_progress_change")) as mock_track:
                with patch(_helpers_path("_WAIT_EVENT")):
                    with patch("time.sleep"):
                        success, _ = monitor_export_with_recovery(
                            mock_ec2,
                            mock_s3,
                            "export-123",
                            "test-key.vmdk",
                            bucket_name="test-bucket",
                            snapshot_size_gb=50,
                        )

                        assert_equal(success, True)
                        assert mock_track.call_count >= 3


def test_monitor_export_with_recovery_progress_na():
    """Test monitor_export_with_recovery handles N/A progress value."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()

    mock_task_na = {"Status": "active", "Progress": "N/A", "StatusMessage": "Starting"}
    mock_task_complete = {"Status": "completed", "Progress": "100"}

    with patch(
        _helpers_path("_fetch_export_task_status"),
        side_effect=[
            (mock_task_na, 0),
            (mock_task_complete, 0),
        ],
    ):
        with patch(_helpers_path("_print_export_status")):
            with patch(_helpers_path("_track_progress_change")) as mock_track:
                with patch(_helpers_path("_WAIT_EVENT")):
                    with patch("time.sleep"):
                        success, _ = monitor_export_with_recovery(
                            mock_ec2,
                            mock_s3,
                            "export-123",
                            "test-key.vmdk",
                            bucket_name="test-bucket",
                            snapshot_size_gb=50,
                        )

                        assert_equal(success, True)
                        # Verify _track_progress_change called with 0 for N/A progress
                        assert any(call_args[0][1] == 0 for call_args in mock_track.call_args_list)


def test_export_ami_to_s3_with_recovery_success():
    """Test export_ami_to_s3_with_recovery completes successfully."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()

    with patch(
        _helpers_path("_start_export_task_fixed"),
        return_value=("export-123", "test-key.vmdk"),
    ):
        with patch(
            f"{EXPORT_HELPERS_PATH}monitor_export_with_recovery",
            return_value=(True, "test-key.vmdk"),
        ):
            task_id, key = export_ami_to_s3_with_recovery(
                mock_ec2, mock_s3, "ami-123", "test-bucket", "us-east-1", 50
            )

            assert_equal(task_id, "export-123")
            assert_equal(key, "test-key.vmdk")


def test_export_ami_to_s3_with_recovery_failure():
    """Test export_ami_to_s3_with_recovery returns None on failure."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()

    with patch(
        _helpers_path("_start_export_task_fixed"),
        return_value=("export-123", "test-key.vmdk"),
    ):
        with patch(
            f"{EXPORT_HELPERS_PATH}monitor_export_with_recovery",
            return_value=(False, None),
        ):
            task_id, key = export_ami_to_s3_with_recovery(
                mock_ec2, mock_s3, "ami-123", "test-bucket", "us-east-1", 50
            )

            assert_equal(task_id, None)
            assert_equal(key, None)
