"""Helper functions for fixed export operations"""

import time

from botocore.exceptions import ClientError

from . import constants
from .constants import (
    EXPORT_STATUS_CHECK_INTERVAL_SECONDS,
    ExportTaskDeletedException,
    ExportTaskStuckException,
)


def _start_export_task_fixed(ec2_client, ami_id, bucket_name):
    """Start AMI export task and return task ID and S3 key."""
    print(f"   🔄 Exporting AMI {ami_id} to S3 bucket {bucket_name}...")

    response = ec2_client.export_image(
        ImageId=ami_id,
        DiskImageFormat="VMDK",
        S3ExportLocation={"S3Bucket": bucket_name, "S3Prefix": f"ebs-snapshots/{ami_id}/"},
        Description=f"Export of AMI {ami_id} for cost optimization",
    )

    export_task_id = response["ExportImageTaskId"]
    s3_key = f"ebs-snapshots/{ami_id}/{export_task_id}.vmdk"
    print(f"   ✅ Started export task: {export_task_id}")
    print("   ⏳ Monitoring export progress with intelligent completion detection...")

    return export_task_id, s3_key


def _handle_task_deletion_recovery(s3_client, bucket_name, s3_key, snapshot_size_gb, elapsed_hours):
    """Handle export task deletion by checking S3 file."""
    from .monitoring import check_s3_file_completion

    print(f"   ⚠️  Export task was deleted after {elapsed_hours:.1f} hours")
    print("   🔍 Checking if S3 file was completed before task deletion...")

    try:
        s3_result = check_s3_file_completion(
            s3_client, bucket_name, s3_key, snapshot_size_gb, fast_check=True
        )
        print(
            "   ✅ S3 file found and validated! "
            "Export completed successfully despite task deletion"
        )
        print(f"   📏 Final file size: {s3_result['size_gb']:.2f} GB")
    except Exception as s3_error:
        print("   ❌ Cannot retrieve export results - task no longer exists")
        raise ExportTaskDeletedException(  # noqa: TRY003
            f"Export task deleted and no valid S3 file found: {s3_error}"
        ) from s3_error
    else:
        return True, s3_key


def _fetch_export_task_status(ec2_client, export_task_id):
    """Fetch export task status with error handling."""
    from .export_ops import validate_export_task_exists

    task = validate_export_task_exists(ec2_client, export_task_id)
    return task, 0


def _check_terminal_state_fixed(task, status, elapsed_hours):
    """Check if export is in terminal state."""
    if status == "completed":
        print(f"   ✅ AWS reports export completed after {elapsed_hours:.1f} hours!")
        return True, "completed"

    if status == "failed":
        error_msg = task.get("StatusMessage", "Unknown error")
        raise Exception(  # noqa: TRY002, TRY003
            f"AWS export failed after {elapsed_hours:.1f} hours: {error_msg}"
        )

    if status == "deleted":
        return True, "deleted"

    return False, None


def _print_export_status(status, progress, status_msg, elapsed_hours):
    """Print formatted export status."""
    if status_msg:
        print(
            f"   📊 AWS Status: {status} | Progress: {progress}% | "
            f"Message: {status_msg} | Elapsed: {elapsed_hours:.1f}h"
        )
    else:
        print(f"   📊 AWS Status: {status} | Progress: {progress}% | Elapsed: {elapsed_hours:.1f}h")


def _track_progress_change(current_progress, last_progress_value, current_time, last_change_time):
    """Track and log progress changes."""
    if current_progress != last_progress_value:
        print(f"   📈 Progress updated to {current_progress}%")
        return current_progress, current_time
    return last_progress_value, last_change_time


def _handle_api_errors(consecutive_api_errors, exception):
    """Handle API errors with retry logic."""
    consecutive_api_errors += 1
    print(
        f"   ❌ API error {consecutive_api_errors}/"
        f"{constants.MAX_CONSECUTIVE_API_ERRORS}: {exception}"
    )

    if consecutive_api_errors >= constants.MAX_CONSECUTIVE_API_ERRORS:
        raise Exception(  # noqa: TRY002, TRY003
            f"Too many consecutive API errors ({consecutive_api_errors}) - failing fast"
        )

    return consecutive_api_errors


def monitor_export_with_recovery(
    ec2_client, s3_client, export_task_id, s3_key, bucket_name, snapshot_size_gb
):
    """Monitor export progress with recovery mechanisms."""
    start_time = time.time()
    last_progress_change_time = start_time
    last_progress_value = 0
    consecutive_api_errors = 0

    while True:
        current_time = time.time()
        elapsed_time = current_time - start_time
        elapsed_hours = elapsed_time / 3600

        if elapsed_hours >= constants.EXPORT_MAX_DURATION_HOURS:
            raise ExportTaskStuckException(  # noqa: TRY003
                f"Export exceeded maximum duration of "
                f"{constants.EXPORT_MAX_DURATION_HOURS} hours - aborting"
            )

        try:
            task, _ = _fetch_export_task_status(ec2_client, export_task_id)
            consecutive_api_errors = 0
        except ExportTaskDeletedException:
            return _handle_task_deletion_recovery(
                s3_client, bucket_name, s3_key, snapshot_size_gb, elapsed_hours
            )
        except ClientError as e:
            consecutive_api_errors = _handle_api_errors(consecutive_api_errors, e)
            time.sleep(constants.EXPORT_STATUS_CHECK_INTERVAL_SECONDS)
            continue

        status = task["Status"]
        progress = task.get("Progress", "N/A")
        status_msg = task.get("StatusMessage", "")

        _print_export_status(status, progress, status_msg, elapsed_hours)

        current_progress = int(progress) if progress != "N/A" else 0
        last_progress_value, last_progress_change_time = _track_progress_change(
            current_progress, last_progress_value, current_time, last_progress_change_time
        )

        is_terminal, terminal_type = _check_terminal_state_fixed(task, status, elapsed_hours)
        if is_terminal:
            if terminal_type == "completed":
                return True, s3_key
            if terminal_type == "deleted":
                result = _handle_task_deletion_recovery(
                    s3_client, bucket_name, s3_key, snapshot_size_gb, elapsed_hours
                )
                return result

        time.sleep(EXPORT_STATUS_CHECK_INTERVAL_SECONDS)


def export_ami_to_s3_with_recovery(
    ec2_client, s3_client, ami_id, bucket_name, region, snapshot_size_gb
):
    """
    Export AMI to S3 with proper error handling and recovery - fail fast on unrecoverable errors
    """
    export_task_id, s3_key = _start_export_task_fixed(ec2_client, ami_id, bucket_name)

    success, result_key = monitor_export_with_recovery(
        ec2_client, s3_client, export_task_id, s3_key, bucket_name, snapshot_size_gb
    )

    if success:
        return export_task_id, result_key

    return None, None
