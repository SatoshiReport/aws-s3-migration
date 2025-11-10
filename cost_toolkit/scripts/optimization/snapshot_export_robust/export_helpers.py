"""Helper functions for robust export operations"""

import time

from botocore.exceptions import ClientError

STUCK_EXPORT_PROGRESS_PERCENT = 80


def _check_deleted_task_s3_file(s3_client, bucket_name, s3_key):
    """Check if S3 file exists when task is deleted."""
    try:
        s3_response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
        file_size_gb = s3_response["ContentLength"] / (1024**3)
        print(f"   ✅ S3 file found! Size: {file_size_gb:.2f} GB")
    except Exception:  # noqa: BLE001
        return False, None
    return True, s3_key


def _check_stuck_export_s3_file(s3_client, bucket_name, s3_key):
    """Check if S3 file is stable for stuck export."""
    try:
        s3_response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
        file_size_gb = s3_response["ContentLength"] / (1024**3)

        time.sleep(300)
        s3_response2 = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
        file_size_gb2 = s3_response2["ContentLength"] / (1024**3)

        if file_size_gb == file_size_gb2:
            print(f"   ✅ S3 file is stable at {file_size_gb:.2f} GB - considering export complete")
            return True, s3_key
    except:
        pass

    return False, None


def _handle_export_task_status(task, s3_key):
    """Handle terminal export task states."""
    status = task["Status"]

    if status == "completed":
        print("   ✅ Export completed successfully!")
        return True, s3_key

    if status == "failed":
        error_msg = task.get("StatusMessage", "Unknown error")
        print(f"   ❌ Export failed: {error_msg}")
        return False, None

    return None, None


def wait_for_export_completion_robust(
    ec2_client, s3_client, export_task_id, bucket_name, ami_id, size_gb, constants
):
    """Monitor export with robust completion detection"""
    print(
        f"   ⏳ Waiting {constants.INITIAL_WAIT_MINUTES} minutes before checking export status..."
    )
    time.sleep(constants.INITIAL_WAIT_MINUTES * 60)

    start_time = time.time()
    s3_key = f"ebs-snapshots/{ami_id}/{export_task_id}.vmdk"
    last_progress = 0

    while True:
        elapsed_time = time.time() - start_time
        elapsed_hours = elapsed_time / 3600

        if elapsed_hours >= constants.EXPORT_MAX_DURATION_HOURS:
            raise Exception(  # noqa: TRY003, TRY002
                f"Export exceeded maximum duration of {constants.EXPORT_MAX_DURATION_HOURS} hours"
            )

        try:
            response = ec2_client.describe_export_image_tasks(ExportImageTaskIds=[export_task_id])

            if not response["ExportImageTasks"]:
                print("   ⚠️  Export task no longer exists - checking S3...")
                return _check_deleted_task_s3_file(s3_client, bucket_name, s3_key)

            task = response["ExportImageTasks"][0]
            progress = task.get("Progress", "N/A")
            current_progress = int(progress) if progress != "N/A" else 0

            print(
                f"   📊 Status: {task['Status']} | Progress: {progress}% | "
                f"Elapsed: {elapsed_hours:.1f}h"
            )

            result = _handle_export_task_status(task, s3_key)
            if result[0] is not None:
                return result

            is_stuck = (
                current_progress == STUCK_EXPORT_PROGRESS_PERCENT
                and current_progress == last_progress
                and elapsed_time > (30 * 60)
            )

            if is_stuck:
                print(
                    f"   🔍 Export stuck at {STUCK_EXPORT_PROGRESS_PERCENT}% - "
                    "checking S3 directly..."
                )
                return _check_stuck_export_s3_file(s3_client, bucket_name, s3_key)

            last_progress = current_progress

        except ClientError as e:
            print(f"   ⚠️  Error checking export status: {e}")

        time.sleep(constants.EXPORT_STATUS_CHECK_INTERVAL_SECONDS)
