"""Tests for cost_toolkit/scripts/optimization/snapshot_export_common.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.common.waiter_utils import wait_ami_available
from cost_toolkit.scripts.optimization.snapshot_export_common import (
    _register_ami,
    create_ami_from_snapshot,
    create_s3_bucket_if_not_exists,
    print_export_status,
    setup_s3_bucket_versioning,
    start_ami_export_task,
)


# Tests for load_aws_credentials
def test_create_s3_bucket_if_not_exists_already_exists(mock_print):
    """Test bucket already exists."""
    mock_s3 = MagicMock()
    mock_s3.head_bucket.return_value = {}

    result = create_s3_bucket_if_not_exists(mock_s3, "test-bucket", "us-east-1")

    assert result is True
    mock_s3.head_bucket.assert_called_once_with(Bucket="test-bucket")
    mock_print.assert_called()


@patch("cost_toolkit.scripts.optimization.snapshot_export_common.create_s3_bucket_with_region")
@patch("builtins.print")
def test_create_s3_bucket_if_not_exists_creates_bucket(_mock_print, mock_create):
    """Test bucket creation when it doesn't exist."""
    mock_s3 = MagicMock()
    mock_s3.head_bucket.side_effect = ClientError({"Error": {"Code": "NotFound"}}, "HeadBucket")

    result = create_s3_bucket_if_not_exists(mock_s3, "test-bucket", "us-west-2")

    assert result is True
    mock_create.assert_called_once_with(mock_s3, "test-bucket", "us-west-2")
    mock_s3.put_bucket_versioning.assert_called_once_with(
        Bucket="test-bucket", VersioningConfiguration={"Status": "Enabled"}
    )


@patch("cost_toolkit.scripts.optimization.snapshot_export_common.create_s3_bucket_with_region")
@patch("builtins.print")
def test_create_s3_bucket_if_not_exists_no_versioning(_mock_print, mock_create):
    """Test bucket creation without versioning."""
    mock_s3 = MagicMock()
    mock_s3.head_bucket.side_effect = ClientError({"Error": {"Code": "NotFound"}}, "HeadBucket")

    result = create_s3_bucket_if_not_exists(
        mock_s3, "test-bucket", "us-west-2", enable_versioning=False
    )

    assert result is True
    mock_create.assert_called_once()
    mock_s3.put_bucket_versioning.assert_not_called()


@patch("cost_toolkit.scripts.optimization.snapshot_export_common.create_s3_bucket_with_region")
@patch("builtins.print")
def test_create_s3_bucket_if_not_exists_creation_fails(_mock_print, mock_create):
    """Test bucket creation failure."""
    mock_s3 = MagicMock()
    mock_s3.head_bucket.side_effect = ClientError({"Error": {"Code": "NotFound"}}, "HeadBucket")
    mock_create.side_effect = ClientError(
        {"Error": {"Code": "BucketAlreadyExists"}}, "CreateBucket"
    )

    result = create_s3_bucket_if_not_exists(mock_s3, "test-bucket", "us-west-2")

    assert result is False


# Tests for setup_s3_bucket_versioning
@patch("builtins.print")
def test_setup_s3_bucket_versioning_success(_mock_print):
    """Test successful versioning setup."""
    mock_s3 = MagicMock()

    result = setup_s3_bucket_versioning(mock_s3, "test-bucket")

    assert result is True
    mock_s3.put_bucket_versioning.assert_called_once_with(
        Bucket="test-bucket", VersioningConfiguration={"Status": "Enabled"}
    )


@patch("builtins.print")
def test_setup_s3_bucket_versioning_failure(_mock_print):
    """Test versioning setup failure."""
    mock_s3 = MagicMock()
    mock_s3.put_bucket_versioning.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied"}}, "PutBucketVersioning"
    )

    result = setup_s3_bucket_versioning(mock_s3, "test-bucket")

    assert result is False


# Tests for create_ami_from_snapshot
@patch("cost_toolkit.scripts.optimization.snapshot_export_common.wait_ami_available")
@patch("cost_toolkit.scripts.optimization.snapshot_export_common._register_ami")
@patch("builtins.print")
def test_create_ami_from_snapshot_success(_mock_print, mock_register, mock_wait):
    """Test successful AMI creation."""
    mock_ec2 = MagicMock()
    mock_register.return_value = "ami-12345678"

    result = create_ami_from_snapshot(mock_ec2, "snap-12345678", "Test snapshot")

    assert result == "ami-12345678"
    mock_register.assert_called_once()
    mock_wait.assert_called_once_with(mock_ec2, "ami-12345678", delay=30, max_attempts=40)


@patch("cost_toolkit.scripts.optimization.snapshot_export_common._register_ami")
@patch("builtins.print")
def test_create_ami_from_snapshot_failure(_mock_print, mock_register):
    """Test AMI creation failure."""
    mock_ec2 = MagicMock()
    mock_register.side_effect = ClientError({"Error": {"Code": "InvalidSnapshot"}}, "RegisterImage")

    result = create_ami_from_snapshot(mock_ec2, "snap-12345678", "Test snapshot")

    assert result is None


@patch("cost_toolkit.scripts.optimization.snapshot_export_common.wait_ami_available")
@patch("cost_toolkit.scripts.optimization.snapshot_export_common._register_ami")
@patch("builtins.print")
def test_create_ami_from_snapshot_with_boot_mode(_mock_print, mock_register, _mock_wait):
    """Test AMI creation with boot mode specified."""
    mock_ec2 = MagicMock()
    mock_register.return_value = "ami-12345678"

    result = create_ami_from_snapshot(
        mock_ec2,
        "snap-12345678",
        "Test snapshot",
        volume_type="gp2",
        boot_mode="uefi",
        ena_support=False,
        attempt_suffix="-retry",
    )

    assert result == "ami-12345678"
    call_kwargs = mock_register.call_args[1]
    assert call_kwargs["boot_mode"] == "uefi"
    assert call_kwargs["volume_type"] == "gp2"
    assert call_kwargs["ena_support"] is False
    assert call_kwargs["attempt_suffix"] == "-retry"


# Tests for _register_ami
@patch("cost_toolkit.scripts.optimization.snapshot_export_common.datetime")
@patch("builtins.print")
def test_register_ami_success(_mock_print, mock_datetime):
    """Test _register_ami creates AMI with correct parameters."""
    mock_datetime.now.return_value.strftime.return_value = "20250114-120000"
    mock_ec2 = MagicMock()
    mock_ec2.register_image.return_value = {"ImageId": "ami-12345678"}

    result = _register_ami(
        mock_ec2,
        "snap-12345678",
        "Test description",
        volume_type="gp3",
        boot_mode=None,
        ena_support=True,
        attempt_suffix="",
    )

    assert result == "ami-12345678"
    mock_ec2.register_image.assert_called_once()
    call_kwargs = mock_ec2.register_image.call_args[1]
    assert call_kwargs["Name"] == "export-snap-12345678-20250114-120000"
    assert call_kwargs["Architecture"] == "x86_64"
    assert call_kwargs["EnaSupport"] is True
    assert "BootMode" not in call_kwargs


@patch("cost_toolkit.scripts.optimization.snapshot_export_common.datetime")
@patch("builtins.print")
def test_register_ami_with_boot_mode(_mock_print, mock_datetime):
    """Test _register_ami with boot mode specified."""
    mock_datetime.now.return_value.strftime.return_value = "20250114-120000"
    mock_ec2 = MagicMock()
    mock_ec2.register_image.return_value = {"ImageId": "ami-12345678"}

    result = _register_ami(
        mock_ec2,
        "snap-12345678",
        "Test description",
        volume_type="gp3",
        boot_mode="uefi",
        ena_support=True,
        attempt_suffix="-v2",
    )

    assert result == "ami-12345678"
    call_kwargs = mock_ec2.register_image.call_args[1]
    assert call_kwargs["BootMode"] == "uefi"
    assert call_kwargs["Name"] == "export-snap-12345678-20250114-120000-v2"


# Tests for wait_ami_available
@patch("builtins.print")
def test_wait_ami_available_success(_mock_print):
    """Test waiting for AMI to become available."""
    mock_ec2 = MagicMock()
    mock_waiter = MagicMock()
    mock_ec2.get_waiter.return_value = mock_waiter

    wait_ami_available(mock_ec2, "ami-12345678")

    mock_ec2.get_waiter.assert_called_once_with("image_available")
    mock_waiter.wait.assert_called_once_with(
        ImageIds=["ami-12345678"],
        WaiterConfig={"Delay": 15, "MaxAttempts": 40},
    )


@patch("builtins.print")
def test_wait_ami_available_custom_config(_mock_print):
    """Test waiting for AMI with custom waiter config."""
    mock_ec2 = MagicMock()
    mock_waiter = MagicMock()
    mock_ec2.get_waiter.return_value = mock_waiter

    wait_ami_available(mock_ec2, "ami-12345678", delay=60, max_attempts=20)

    mock_waiter.wait.assert_called_once_with(
        ImageIds=["ami-12345678"],
        WaiterConfig={"Delay": 60, "MaxAttempts": 20},
    )


# Tests for start_ami_export_task
@patch("builtins.print")
def test_start_ami_export_task_success(_mock_print):
    """Test starting AMI export task."""
    mock_ec2 = MagicMock()
    mock_ec2.export_image.return_value = {"ExportImageTaskId": "export-12345"}

    task_id, s3_key = start_ami_export_task(mock_ec2, "ami-12345678", "test-bucket")

    assert task_id == "export-12345"
    assert s3_key == "ebs-snapshots/ami-12345678/export-12345.vmdk"
    mock_ec2.export_image.assert_called_once_with(
        ImageId="ami-12345678",
        DiskImageFormat="VMDK",
        S3ExportLocation={
            "S3Bucket": "test-bucket",
            "S3Prefix": "ebs-snapshots/ami-12345678/",
        },
        Description="Export of AMI ami-12345678 for cost optimization",
    )


@patch("builtins.print")
def test_start_ami_export_task_with_snapshot_id(_mock_print):
    """Test starting AMI export task with snapshot ID."""
    mock_ec2 = MagicMock()
    mock_ec2.export_image.return_value = {"ExportImageTaskId": "export-12345"}

    task_id, _ = start_ami_export_task(
        mock_ec2, "ami-12345678", "test-bucket", snapshot_id="snap-12345678"
    )

    assert task_id == "export-12345"
    call_kwargs = mock_ec2.export_image.call_args[1]
    assert "snap-12345678" in call_kwargs["Description"]


# Tests for print_export_status
@patch("builtins.print")
def test_print_export_status_with_message(mock_print):
    """Test printing export status with message."""
    print_export_status("active", 50, "Processing snapshot", 2.5)

    mock_print.assert_called_once()
    call_args = str(mock_print.call_args)
    assert "active" in call_args
    assert "50%" in call_args
    assert "Processing snapshot" in call_args
    assert "2.5h" in call_args


@patch("builtins.print")
def test_print_export_status_without_message(mock_print):
    """Test printing export status without message."""
    print_export_status("completed", 100, None, 3.2)

    mock_print.assert_called_once()
    call_args = str(mock_print.call_args)
    assert "completed" in call_args
    assert "100%" in call_args
    assert "3.2h" in call_args


@patch("builtins.print")
def test_print_export_status_with_string_progress(mock_print):
    """Test printing export status with string progress."""
    print_export_status("pending", "N/A", "Waiting", 0.1)

    mock_print.assert_called_once()
    call_args = str(mock_print.call_args)
    assert "N/A" in call_args
