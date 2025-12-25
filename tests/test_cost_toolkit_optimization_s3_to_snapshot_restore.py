"""Comprehensive tests for aws_s3_to_snapshot_restore.py."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore import (
    AMIImportError,
    S3ExportError,
    SnapshotCreationError,
    _create_aws_clients,
    _validate_user_inputs,
    create_snapshot_from_ami,
    import_ami_from_s3,
    list_s3_exports,
)


@patch("cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore.setup_aws_credentials")
class TestListS3Exports:
    """Test S3 export listing functionality."""

    def test_list_exports_with_vmdk_files(self, _mock_setup):
        """Test listing exports with VMDK files."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {
                    "Key": "ebs-snapshots/snap-123.vmdk",
                    "Size": 1024 * 1024 * 100,
                    "LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc),
                },
                {
                    "Key": "ebs-snapshots/snap-456.raw",
                    "Size": 1024 * 1024 * 200,
                    "LastModified": datetime(2024, 1, 2, tzinfo=timezone.utc),
                },
                {"Key": "ebs-snapshots/readme.txt", "Size": 1024, "LastModified": datetime.now()},
            ]
        }

        exports = list_s3_exports(mock_s3, "test-bucket")

        assert len(exports) == 2
        assert exports[0]["key"] == "ebs-snapshots/snap-123.vmdk"
        assert exports[0]["size"] == 1024 * 1024 * 100
        assert exports[1]["key"] == "ebs-snapshots/snap-456.raw"
        mock_s3.list_objects_v2.assert_called_once_with(Bucket="test-bucket", Prefix="ebs-snapshots/")

    def test_list_exports_no_contents(self, _mock_setup):
        """Test listing when bucket has no files."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {}

        exports = list_s3_exports(mock_s3, "empty-bucket")

        assert not exports

    def test_list_exports_client_error(self, _mock_setup, capsys):
        """Test handling S3 client errors."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.side_effect = ClientError({"Error": {"Code": "NoSuchBucket"}}, "list_objects_v2")

        with pytest.raises(S3ExportError) as exc_info:
            list_s3_exports(mock_s3, "nonexistent-bucket")

        captured = capsys.readouterr()
        assert "Error listing S3 exports" in captured.out
        assert "Failed to list S3 exports" in str(exc_info.value)


class TestImportAmiFromS3:
    """Test AMI import from S3 functionality."""

    def test_import_ami_success(self, capsys):
        """Test successful AMI import."""
        mock_ec2 = MagicMock()
        mock_ec2.import_image.return_value = {"ImportTaskId": "import-123"}
        mock_ec2.describe_import_image_tasks.return_value = {
            "ImportImageTasks": [
                {
                    "ImportTaskId": "import-123",
                    "Status": "completed",
                    "Progress": "100",
                    "ImageId": "ami-12345",
                }
            ]
        }

        ami_id = import_ami_from_s3(mock_ec2, "test-bucket", "exports/snap.vmdk", "Test snapshot")

        assert ami_id == "ami-12345"
        mock_ec2.import_image.assert_called_once()
        captured = capsys.readouterr()
        assert "Started import task: import-123" in captured.out
        assert "Import completed! AMI ID: ami-12345" in captured.out

    def test_import_ami_failure(self, capsys):
        """Test AMI import failure."""
        mock_ec2 = MagicMock()
        mock_ec2.import_image.return_value = {"ImportTaskId": "import-456"}
        mock_ec2.describe_import_image_tasks.return_value = {
            "ImportImageTasks": [
                {
                    "ImportTaskId": "import-456",
                    "Status": "failed",
                    "StatusMessage": "Invalid image format",
                }
            ]
        }

        with pytest.raises(AMIImportError) as exc_info:
            import_ami_from_s3(mock_ec2, "test-bucket", "exports/bad.vmdk", "Bad snapshot")

        captured = capsys.readouterr()
        assert "Import status: failed" in captured.out
        assert "Invalid image format" in str(exc_info.value)

    def test_import_ami_deleted(self, capsys):
        """Test AMI import deleted status."""
        mock_ec2 = MagicMock()
        mock_ec2.import_image.return_value = {"ImportTaskId": "import-789"}
        mock_ec2.describe_import_image_tasks.return_value = {"ImportImageTasks": [{"ImportTaskId": "import-789", "Status": "deleted"}]}

        with pytest.raises(AMIImportError) as exc_info:
            import_ami_from_s3(mock_ec2, "test-bucket", "exports/test.vmdk", "Test")

        captured = capsys.readouterr()
        assert "Import status: deleted" in captured.out
        assert "Import task import-789 failed" in str(exc_info.value)

    def test_import_ami_task_not_found(self):
        """Test when import task is not found."""
        mock_ec2 = MagicMock()
        mock_ec2.import_image.return_value = {"ImportTaskId": "import-999"}
        mock_ec2.describe_import_image_tasks.return_value = {"ImportImageTasks": []}

        with pytest.raises(AMIImportError) as exc_info:
            import_ami_from_s3(mock_ec2, "test-bucket", "exports/test.vmdk", "Test")

        assert "import-999 not found" in str(exc_info.value)

    def test_import_ami_client_error(self):
        """Test handling client errors during import."""
        mock_ec2 = MagicMock()
        mock_ec2.import_image.side_effect = ClientError({"Error": {"Code": "InvalidParameter"}}, "import_image")

        with pytest.raises(AMIImportError) as exc_info:
            import_ami_from_s3(mock_ec2, "test-bucket", "exports/test.vmdk", "Test")

        assert "Failed to start AMI import" in str(exc_info.value)


class TestCreateSnapshotFromAmi:
    """Test snapshot creation from AMI."""

    def test_create_snapshot_success(self, capsys):
        """Test successful snapshot creation."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_images.return_value = {
            "Images": [
                {
                    "RootDeviceName": "/dev/sda1",
                    "BlockDeviceMappings": [{"DeviceName": "/dev/sda1", "Ebs": {"SnapshotId": "snap-12345"}}],
                }
            ]
        }

        snapshot_id = create_snapshot_from_ami(mock_ec2, "ami-12345", "Test AMI")

        assert snapshot_id == "snap-12345"
        mock_ec2.create_tags.assert_called_once()
        captured = capsys.readouterr()
        assert "Found root snapshot: snap-12345" in captured.out
        assert "Tagged snapshot snap-12345" in captured.out

    def test_create_snapshot_ami_not_found(self):
        """Test when AMI is not found."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_images.return_value = {"Images": []}

        with pytest.raises(SnapshotCreationError) as exc_info:
            create_snapshot_from_ami(mock_ec2, "ami-notfound", "Test")

        assert "AMI ami-notfound not found" in str(exc_info.value)

    def test_create_snapshot_no_root_device(self):
        """Test when AMI has no root device mapping."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_images.return_value = {"Images": [{"RootDeviceName": "/dev/sda1", "BlockDeviceMappings": []}]}

        with pytest.raises(SnapshotCreationError) as exc_info:
            create_snapshot_from_ami(mock_ec2, "ami-12345", "Test")

        assert "No root snapshot found in AMI" in str(exc_info.value)

    def test_create_snapshot_tagging_failure(self, capsys):
        """Test when tagging fails but snapshot is found."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_images.return_value = {
            "Images": [
                {
                    "RootDeviceName": "/dev/sda1",
                    "BlockDeviceMappings": [{"DeviceName": "/dev/sda1", "Ebs": {"SnapshotId": "snap-99999"}}],
                }
            ]
        }
        mock_ec2.create_tags.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "create_tags")

        snapshot_id = create_snapshot_from_ami(mock_ec2, "ami-12345", "Test")

        assert snapshot_id == "snap-99999"
        captured = capsys.readouterr()
        assert "Warning: Could not tag snapshot" in captured.out


class TestValidateUserInputs:
    """Test user input validation."""

    def test_validate_inputs_valid(self):
        """Test validation with valid inputs."""
        assert _validate_user_inputs("us-east-1", "my-bucket") is True

    def test_validate_inputs_missing_region(self, capsys):
        """Test validation with missing region."""
        assert _validate_user_inputs("", "my-bucket") is False
        captured = capsys.readouterr()
        assert "Region is required" in captured.out

    def test_validate_inputs_missing_bucket(self, capsys):
        """Test validation with missing bucket."""
        assert _validate_user_inputs("us-east-1", "") is False
        captured = capsys.readouterr()
        assert "Bucket name is required" in captured.out


@patch("cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore.boto3.client")
def test_create_clients(mock_boto_client):
    """Test creating EC2 and S3 clients."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()
    mock_boto_client.side_effect = [mock_ec2, mock_s3]

    ec2, s3 = _create_aws_clients("access_key", "secret_key", "us-west-2")

    assert ec2 == mock_ec2
    assert s3 == mock_s3
    assert mock_boto_client.call_count == 2
