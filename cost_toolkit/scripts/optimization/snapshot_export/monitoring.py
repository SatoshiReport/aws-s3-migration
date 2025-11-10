"""Monitoring and validation utilities for export operations"""

import time

from botocore.exceptions import ClientError

FAST_STABILITY_MINUTES = 2
FAST_STABILITY_INTERVAL_MINUTES = 1
NORMAL_STABILITY_MINUTES = 10
NORMAL_STABILITY_INTERVAL_MINUTES = 5
SIZE_VARIANCE_PERCENT = 10


def cleanup_temporary_ami(ec2_client, ami_id, region):
    """Clean up temporary AMI after successful export"""
    try:
        print(f"   🧹 Cleaning up temporary AMI: {ami_id}")
        ec2_client.deregister_image(ImageId=ami_id)
        print(f"   ✅ Successfully cleaned up AMI {ami_id}")
    except ClientError as e:
        print(f"   ⚠️  Warning: Could not clean up AMI {ami_id}: {e}")
        return False

    return True


def check_existing_exports(ec2_client, region):
    """Check for existing completed export tasks"""
    try:
        print(f"   🔍 Checking for existing completed exports in {region}...")
        response = ec2_client.describe_export_image_tasks()
        completed_exports = []

        for task in response["ExportImageTasks"]:
            if task["Status"] == "completed":
                completed_exports.append(
                    {
                        "export_task_id": task["ExportImageTaskId"],
                        "ami_id": task.get("ImageId", "unknown"),
                        "s3_location": task.get("S3ExportLocation", {}),
                        "description": task.get("Description", ""),
                    }
                )

        if completed_exports:
            print(f"   ✅ Found {len(completed_exports)} completed exports:")
            for export in completed_exports:
                s3_bucket = export["s3_location"].get("S3Bucket", "unknown")
                s3_prefix = export["s3_location"].get("S3Prefix", "unknown")
                print(f"      - {export['export_task_id']}: s3://{s3_bucket}/{s3_prefix}")

    except ClientError as e:
        print(f"   ⚠️  Could not check existing exports: {e}")
        return []

    return completed_exports


def _perform_stability_check(s3_client, bucket_name, s3_key, check_num):
    """Perform a single stability check on S3 file."""
    response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
    file_size_bytes = response["ContentLength"]
    file_size_gb = file_size_bytes / (1024**3)

    return {
        "check_num": check_num + 1,
        "size_bytes": file_size_bytes,
        "size_gb": file_size_gb,
        "last_modified": response["LastModified"],
        "timestamp": time.time(),
    }


def _compare_stability_checks(prev_check, current_check, stability_checks):
    """Compare consecutive stability checks and return updated list."""
    if prev_check["size_bytes"] != current_check["size_bytes"]:
        print(
            f"   📈 File size changed: {prev_check['size_gb']:.2f} GB → "
            f"{current_check['size_gb']:.2f} GB"
        )
        print("   ⏳ File still growing, continuing to monitor...")
        return [current_check]

    print(f"   ✅ File size stable: {current_check['size_gb']:.2f} GB")
    return stability_checks


def _validate_final_file_size(final_check, expected_size_gb):
    """Validate that final file size is reasonable."""
    min_expected_gb = expected_size_gb * 0.1 if expected_size_gb else 0.1
    max_expected_gb = expected_size_gb * 1.2 if expected_size_gb else float("in")

    size_reasonable = min_expected_gb <= final_check["size_gb"] <= max_expected_gb

    if not size_reasonable:
        print(
            f"   ⚠️  File size suspicious: {final_check['size_gb']:.2f} GB "
            f"(expected {min_expected_gb:.1f}-{max_expected_gb:.1f} GB)"
        )

    return size_reasonable


def check_s3_file_stability(
    s3_client, bucket_name, s3_key, expected_size_gb=None, fast_check=False
):
    """Check if S3 file exists and monitor its stability (size unchanged for multiple checks)"""
    stability_required_minutes = FAST_STABILITY_MINUTES if fast_check else NORMAL_STABILITY_MINUTES
    check_interval_minutes = (
        FAST_STABILITY_INTERVAL_MINUTES if fast_check else NORMAL_STABILITY_INTERVAL_MINUTES
    )
    required_stable_checks = stability_required_minutes // check_interval_minutes

    print(f"   🔍 Checking S3 file stability: s3://{bucket_name}/{s3_key}")

    stability_checks = []
    for check_num in range(required_stable_checks):
        try:
            check_data = _perform_stability_check(s3_client, bucket_name, s3_key, check_num)
            stability_checks.append(check_data)

            print(
                f"   📊 Stability check {check_num + 1}/{required_stable_checks}: "
                f"{check_data['size_gb']:.2f} GB"
            )

            if len(stability_checks) > 1:
                stability_checks = _compare_stability_checks(
                    stability_checks[-2], stability_checks[-1], stability_checks
                )

            if check_num < required_stable_checks - 1:
                print(f"   ⏳ Waiting {check_interval_minutes} minutes for next stability check...")
                time.sleep(check_interval_minutes * 60)

        except s3_client.exceptions.NoSuchKey:
            print(f"   ❌ File not found in S3: s3://{bucket_name}/{s3_key}")
            return {"exists": False, "stable": False}
        except ClientError as e:
            print(f"   ❌ Error checking S3 file: {e}")
            return {"exists": False, "stable": False, "error": str(e)}

    if len(stability_checks) >= required_stable_checks:
        final_check = stability_checks[-1]
        size_reasonable = _validate_final_file_size(final_check, expected_size_gb)

        print(
            f"   ✅ File stable for {stability_required_minutes} minutes "
            f"at {final_check['size_gb']:.2f} GB"
        )

        return {
            "exists": True,
            "stable": True,
            "size_bytes": final_check["size_bytes"],
            "size_gb": final_check["size_gb"],
            "last_modified": final_check["last_modified"],
            "size_reasonable": size_reasonable,
            "stability_checks": len(stability_checks),
        }

    return {"exists": True, "stable": False}


def verify_s3_export(s3_client, bucket_name, s3_key, expected_size_gb=None):
    """Verify that the exported file exists in S3 and get its details"""
    try:
        print(f"   🔍 Verifying S3 export: s3://{bucket_name}/{s3_key}")

        response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)

        file_size_bytes = response["ContentLength"]
        file_size_gb = file_size_bytes / (1024**3)
        last_modified = response["LastModified"]

        print("   ✅ File exists in S3!")
        print(f"   📏 File size: {file_size_gb:.2f} GB ({file_size_bytes:,} bytes)")
        print(f"   📅 Last modified: {last_modified}")

        if expected_size_gb:
            size_diff_percent = abs(file_size_gb - expected_size_gb) / expected_size_gb * 100
            if size_diff_percent > SIZE_VARIANCE_PERCENT:
                print(
                    f"   ⚠️  Size variance: Expected ~{expected_size_gb} GB, got "
                    f"{file_size_gb:.2f} GB ({size_diff_percent:.1f}% difference, "
                    f"limit {SIZE_VARIANCE_PERCENT}%)"
                )
            else:
                print(
                    f"   ✅ Size verification passed (within {SIZE_VARIANCE_PERCENT}% of expected "
                    f"{expected_size_gb} GB)"
                )

        return {  # noqa: TRY300
            "exists": True,
            "size_bytes": file_size_bytes,
            "size_gb": file_size_gb,
            "last_modified": last_modified,
        }

    except s3_client.exceptions.NoSuchKey:
        print(f"   ❌ File not found in S3: s3://{bucket_name}/{s3_key}")
        return {"exists": False}
    except ClientError as e:
        print(f"   ❌ Error verifying S3 file: {e}")
        return {"exists": False, "error": str(e)}
