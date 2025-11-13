"""Export operations with fail-fast error handling"""

from cost_toolkit.common.s3_utils import create_s3_bucket_with_region

from ..snapshot_export_common import _register_ami, wait_for_ami_available
from . import constants
from .constants import ExportTaskDeletedException


def create_s3_bucket_if_not_exists(s3_client, bucket_name, _region):
    """Create S3 bucket if it doesn't exist - fail fast on errors"""
    s3_client.head_bucket(Bucket=bucket_name)
    print(f"   ✅ S3 bucket {bucket_name} already exists")
    return True


def create_s3_bucket_new(s3_client, bucket_name, region):
    """Create new S3 bucket - fail fast on errors"""
    create_s3_bucket_with_region(s3_client, bucket_name, region)
    return True


def create_ami_from_snapshot(ec2_client, snapshot_id, snapshot_description):
    """Create an AMI from an EBS snapshot - fail fast on errors"""
    ami_id = _register_ami(
        ec2_client,
        snapshot_id,
        snapshot_description,
        volume_type="gp3",
        boot_mode=None,
        ena_support=True,
        attempt_suffix="",
    )

    return wait_for_ami_available(
        ec2_client,
        ami_id,
        waiter_delay=constants.AMI_CREATION_CHECK_INTERVAL_SECONDS,
        waiter_max_attempts=(constants.AMI_CREATION_MAX_WAIT_MINUTES * 60)
        // constants.AMI_CREATION_CHECK_INTERVAL_SECONDS,
    )


def validate_export_task_exists(ec2_client, export_task_id):
    """Validate that export task still exists - raise exception if deleted"""
    response = ec2_client.describe_export_image_tasks(ExportImageTaskIds=[export_task_id])

    if not response["ExportImageTasks"]:
        raise ExportTaskDeletedException(  # noqa: TRY003
            f"Export task {export_task_id} no longer exists - was deleted"
        )

    return response["ExportImageTasks"][0]


if __name__ == "__main__":  # pragma: no cover - script entry point
    pass
