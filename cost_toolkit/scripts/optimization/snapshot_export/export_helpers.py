"""Helper functions for export operations"""

import time
from dataclasses import dataclass

from botocore.exceptions import ClientError


@dataclass
class MonitoringState:
    """Tracking state for export monitoring."""

    start_time: float
    last_progress_change_time: float
    last_progress_value: int
    last_s3_check_time: float = 0
    error_count: int = 0


@dataclass
class ExportContext:
    """Context for export operations."""

    ec2_client: object
    s3_client: object
    ami_id: str
    bucket_name: str
    export_task_id: str
    snapshot_size_gb: float


@dataclass
class ExportConfig:
    """Configuration for export monitoring."""

    max_export_hours: float
    max_errors: int


def _extract_s3_key_from_task(task, export_task_id, ami_id):
    """Extract S3 key from export task, handling different response structures"""
    s3_key = None
    if "S3ExportLocation" in task:
        s3_export_location = task["S3ExportLocation"]
        if "S3Key" in s3_export_location:
            s3_key = s3_export_location["S3Key"]
        elif "S3Prefix" in s3_export_location:
            s3_prefix = s3_export_location["S3Prefix"]
            s3_key = f"{s3_prefix}{export_task_id}.vmdk"

    if not s3_key:
        s3_key = f"ebs-snapshots/{ami_id}/{export_task_id}.vmdk"

    return export_task_id, s3_key


def _start_ami_export(ec2_client, ami_id, bucket_name):
    """Start AMI export to S3 and return export task ID."""
    print(f"   🔄 Exporting AMI {ami_id} to S3 bucket {bucket_name}...")

    response = ec2_client.export_image(
        ImageId=ami_id,
        DiskImageFormat="VMDK",
        S3ExportLocation={"S3Bucket": bucket_name, "S3Prefix": f"ebs-snapshots/{ami_id}/"},
        Description=f"Export of AMI {ami_id} for cost optimization",
    )

    export_task_id = response["ExportImageTaskId"]
    print(f"   ✅ Started export task: {export_task_id}")
    print("   ⏳ Monitoring export progress with intelligent completion detection...")
    return export_task_id


def _check_export_timeout(elapsed_hours, max_export_hours):
    """Check if export has exceeded maximum duration."""
    if elapsed_hours >= max_export_hours:
        print(
            f"   ⏰ Export has been running for {elapsed_hours:.1f} hours (max: {max_export_hours})"
        )
        print("   ❌ Aborting stuck export - this is likely a permanently failed AWS export")
        return True
    return False


def _fetch_and_validate_task(ec2_client, export_task_id):
    """Fetch and validate export task."""
    status_response = ec2_client.describe_export_image_tasks(ExportImageTaskIds=[export_task_id])

    if not status_response["ExportImageTasks"]:
        print("   ❌ Export task not found")
        return None

    return status_response["ExportImageTasks"][0]


def _print_status_update(status, progress, status_msg, elapsed_hours):
    """Print formatted status update."""
    if status_msg:
        print(
            f"   📊 AWS Status: {status} | Progress: {progress}% | "
            f"Message: {status_msg} | Elapsed: {elapsed_hours:.1f}h"
        )
    else:
        print(f"   📊 AWS Status: {status} | Progress: {progress}% | Elapsed: {elapsed_hours:.1f}h")


def _update_progress_tracking(current_progress, last_progress_value, current_time):
    """Update progress tracking and return new values."""
    if current_progress != last_progress_value:
        print(f"   📈 Progress updated to {current_progress}%")
        return current_progress, current_time
    return last_progress_value, None


def _handle_terminal_status(status, task, elapsed_hours, export_task_id, ami_id):
    """Handle terminal export statuses (completed, failed, deleted)."""
    if status == "completed":
        print(f"   ✅ AWS reports export completed after {elapsed_hours:.1f} hours!")
        return True, _extract_s3_key_from_task(task, export_task_id, ami_id)

    if status == "failed":
        error_msg = task.get("StatusMessage", "Unknown error")
        print(f"   ❌ AWS reports export failed after {elapsed_hours:.1f} hours: {error_msg}")
        return True, (None, None)

    if status == "deleted":
        print(f"   ⚠️  Export task was deleted after {elapsed_hours:.1f} hours")
        print("   ❌ Cannot retrieve export results - task no longer exists")
        return True, (None, None)

    return False, None


def _check_stuck_export(
    context: ExportContext,
    time_since_progress_change: float,
    current_progress: int,
    status: str,
):
    """Check if export is stuck and try S3 recovery."""
    from .monitoring import check_s3_file_stability

    stuck_detection_hours = 6

    if time_since_progress_change >= stuck_detection_hours and status == "active":
        print(
            f"   ⚠️  Export stuck at {current_progress}% for {time_since_progress_change:.1f} hours"
        )
        print("   🔍 Checking if S3 file completed despite stuck AWS status...")

        s3_key = f"ebs-snapshots/{context.ami_id}/{context.export_task_id}.vmdk"
        s3_stability = check_s3_file_stability(
            context.s3_client,
            context.bucket_name,
            s3_key,
            context.snapshot_size_gb,
            fast_check=True,
        )

        if s3_stability.get("exists") and s3_stability.get("stable"):
            if s3_stability.get("size_reasonable", True):
                print("   ✅ S3 file completed despite stuck AWS status! Export successful")
                print(f"   📏 Final file size: {s3_stability['size_gb']:.2f} GB")
                return True, (context.export_task_id, s3_key)

            print("   ❌ S3 file exists but size unreasonable - export likely failed")
            return True, (None, None)

        print("   ❌ No valid S3 file found - export appears to have failed")
        return True, (None, None)

    return False, None


def _process_export_status_check(
    context: ExportContext,
    state: MonitoringState,
    max_export_hours: float,
):
    """Process a single export status check iteration."""
    current_time = time.time()
    elapsed_time = current_time - state.start_time
    elapsed_hours = elapsed_time / 3600

    if _check_export_timeout(elapsed_hours, max_export_hours):
        return None, None

    task = _fetch_and_validate_task(context.ec2_client, context.export_task_id)
    if not task:
        return None, None

    status = task["Status"]
    progress = task.get("Progress", "N/A")
    status_msg = task.get("StatusMessage", "")

    _print_status_update(status, progress, status_msg, elapsed_hours)

    current_progress = int(progress) if progress != "N/A" else 0
    new_progress, new_time = _update_progress_tracking(
        current_progress, state.last_progress_value, current_time
    )
    if new_time:
        state.last_progress_change_time = new_time
    state.last_progress_value = new_progress

    is_terminal, result = _handle_terminal_status(
        status, task, elapsed_hours, context.export_task_id, context.ami_id
    )
    if is_terminal:
        return result[0], result[1]

    time_since_progress_change = (current_time - state.last_progress_change_time) / 3600

    is_stuck, stuck_result = _check_stuck_export(
        context,
        time_since_progress_change,
        current_progress,
        status,
    )
    if is_stuck:
        return stuck_result[0], stuck_result[1]

    return "continue", None


def monitor_export_status(
    context: ExportContext,
    *,
    max_export_hours,
    max_errors,
):
    """Monitor export progress with intelligent completion detection.

    Args:
        context: Export context containing client, AMI, and bucket details
        max_export_hours: Maximum hours to wait for export
        max_errors: Maximum consecutive errors before aborting
    """
    config = ExportConfig(max_export_hours=max_export_hours, max_errors=max_errors)
    return _monitor_with_context(context, config)


def _monitor_with_context(context: ExportContext, config: ExportConfig):
    """Internal monitoring implementation using context objects."""
    state = MonitoringState(
        start_time=time.time(),
        last_progress_change_time=time.time(),
        last_progress_value=0,
    )

    while True:
        try:
            result_type, result_value = _process_export_status_check(
                context,
                state,
                config.max_export_hours,
            )

            if result_type != "continue":
                return result_type, result_value

            time.sleep(60)

        except ClientError as e:
            print(f"   ❌ Error checking export status: {e}")
            state.error_count += 1

            if state.error_count >= config.max_errors:
                print(f"   ❌ Too many consecutive errors ({state.error_count}), aborting export")
                return None, None

            time.sleep(60)
