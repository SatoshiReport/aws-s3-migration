"""Comprehensive tests for aws_snapshot_to_s3_semi_manual.py."""

from __future__ import annotations

from unittest.mock import MagicMock, mock_open, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.aws_snapshot_to_s3_semi_manual import (
    _build_cleanup_command,
    _build_export_command,
    _build_monitor_command,
    _build_s3_check_command,
    _get_target_snapshots,
    _prepare_all_snapshots,
    _print_cost_summary,
    _print_monitoring_commands,
    _print_workflow_and_troubleshooting,
    _save_commands_to_file,
    generate_manual_commands,
    prepare_snapshot_for_export,
)
from cost_toolkit.scripts.optimization.snapshot_export_common import (
    create_ami_from_snapshot,
    create_s3_bucket_if_not_exists,
)


class TestCreateS3BucketIfNotExists:
    """Test S3 bucket creation."""

    def test_bucket_already_exists(self, capsys):
        """Test when bucket already exists."""
        mock_s3 = MagicMock()
        mock_s3.head_bucket.return_value = {}

        result = create_s3_bucket_if_not_exists(mock_s3, "existing-bucket", "us-east-1")

        assert result is True
        mock_s3.head_bucket.assert_called_once_with(Bucket="existing-bucket")
        captured = capsys.readouterr()
        assert "S3 bucket existing-bucket already exists" in captured.out

    @patch("cost_toolkit.scripts.optimization.snapshot_export_common.create_s3_bucket_with_region")
    def test_bucket_creation_success(self, mock_create, capsys):
        """Test successful bucket creation."""
        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadBucket")

        result = create_s3_bucket_if_not_exists(mock_s3, "new-bucket", "us-west-2")

        assert result is True
        mock_create.assert_called_once_with(mock_s3, "new-bucket", "us-west-2")
        mock_s3.put_bucket_versioning.assert_called_once()
        captured = capsys.readouterr()
        assert "Enabled versioning for new-bucket" in captured.out


class TestCreateAmiFromSnapshot:
    """Test AMI creation from snapshot."""

    def test_create_ami_success(self, capsys):
        """Test successful AMI creation."""
        mock_ec2 = MagicMock()
        mock_ec2.register_image.return_value = {"ImageId": "ami-12345"}
        mock_waiter = MagicMock()
        mock_ec2.get_waiter.return_value = mock_waiter

        ami_id = create_ami_from_snapshot(mock_ec2, "snap-12345", "Test snapshot")

        assert ami_id == "ami-12345"
        mock_ec2.register_image.assert_called_once()
        mock_waiter.wait.assert_called_once()
        captured = capsys.readouterr()
        assert "Created AMI: ami-12345" in captured.out
        assert "AMI ami-12345 is now available" in captured.out

    def test_create_ami_with_settings(self):
        """Test AMI creation with specific settings."""
        mock_ec2 = MagicMock()
        mock_ec2.register_image.return_value = {"ImageId": "ami-67890"}
        mock_waiter = MagicMock()
        mock_ec2.get_waiter.return_value = mock_waiter

        create_ami_from_snapshot(mock_ec2, "snap-67890", "Production snapshot")

        call_kwargs = mock_ec2.register_image.call_args[1]
        assert call_kwargs["Architecture"] == "x86_64"
        assert call_kwargs["EnaSupport"] is True  # Default is True
        assert call_kwargs["RootDeviceName"] == "/dev/sda1"
        # BootMode is not set by default (boot_mode=None)

    def test_create_ami_block_device_mappings(self):
        """Test AMI block device mappings."""
        mock_ec2 = MagicMock()
        mock_ec2.register_image.return_value = {"ImageId": "ami-99999"}
        mock_waiter = MagicMock()
        mock_ec2.get_waiter.return_value = mock_waiter

        create_ami_from_snapshot(mock_ec2, "snap-99999", "Test")

        call_kwargs = mock_ec2.register_image.call_args[1]
        mappings = call_kwargs["BlockDeviceMappings"]
        assert len(mappings) == 1
        assert mappings[0]["DeviceName"] == "/dev/sda1"
        assert mappings[0]["Ebs"]["SnapshotId"] == "snap-99999"
        assert mappings[0]["Ebs"]["VolumeType"] == "gp3"  # Default is gp3
        assert mappings[0]["Ebs"]["DeleteOnTermination"] is True


class TestPrepareSnapshotForExport:
    """Test snapshot preparation for export."""

    @patch("cost_toolkit.scripts.optimization.aws_snapshot_to_s3_semi_manual." "create_ec2_and_s3_clients")
    @patch("cost_toolkit.scripts.optimization.aws_snapshot_to_s3_semi_manual." "create_s3_bucket_if_not_exists")
    @patch("cost_toolkit.scripts.optimization.aws_snapshot_to_s3_semi_manual." "create_ami_from_snapshot")
    def test_prepare_snapshot_success(self, mock_create_ami, mock_create_bucket, mock_clients):
        """Test successful snapshot preparation."""
        mock_ec2 = MagicMock()
        mock_s3 = MagicMock()
        mock_clients.return_value = (mock_ec2, mock_s3)
        mock_create_bucket.return_value = True
        mock_create_ami.return_value = "ami-prepared"

        snapshot_info = {
            "snapshot_id": "snap-111",
            "region": "us-east-2",
            "size_gb": 100,
            "description": "Test snapshot",
        }

        result = prepare_snapshot_for_export(snapshot_info, "access_key", "secret_key")

        assert result["snapshot_id"] == "snap-111"
        assert result["ami_id"] == "ami-prepared"
        assert result["region"] == "us-east-2"
        assert result["size_gb"] == 100
        assert "bucket_name" in result
        assert "monthly_savings" in result

    @patch("cost_toolkit.scripts.optimization.aws_snapshot_to_s3_semi_manual." "create_ec2_and_s3_clients")
    @patch("cost_toolkit.scripts.optimization.aws_snapshot_to_s3_semi_manual." "create_s3_bucket_if_not_exists")
    @patch("cost_toolkit.scripts.optimization.aws_snapshot_to_s3_semi_manual." "create_ami_from_snapshot")
    def test_prepare_snapshot_calculates_savings(self, mock_create_ami, mock_create_bucket, mock_clients):
        """Test that savings are calculated correctly."""
        mock_ec2 = MagicMock()
        mock_s3 = MagicMock()
        mock_clients.return_value = (mock_ec2, mock_s3)
        mock_create_bucket.return_value = True
        mock_create_ami.return_value = "ami-savings"

        snapshot_info = {
            "snapshot_id": "snap-222",
            "region": "eu-west-2",
            "size_gb": 200,
            "description": "Large snapshot",
        }

        result = prepare_snapshot_for_export(snapshot_info, "key", "secret")

        ebs_cost = 200 * 0.05
        s3_cost = 200 * 0.023
        expected_savings = ebs_cost - s3_cost
        assert result["monthly_savings"] == expected_savings


class TestBuildCommands:
    """Test command building functions."""

    def test_build_export_command(self):
        """Test export command generation."""
        cmd = _build_export_command("ami-123", "bucket-name", "us-east-1", "snap-123")

        assert "aws ec2 export-image" in cmd
        assert "{ami_id}" in cmd
        assert "{bucket_name}" in cmd
        assert "{region}" in cmd
        assert "{snapshot_id}" in cmd
        assert "VMDK" in cmd

    def test_build_monitor_command(self):
        """Test monitor command generation."""
        cmd = _build_monitor_command("us-west-2", "ami-456")

        assert "aws ec2 describe-export-image-tasks" in cmd
        assert "{region}" in cmd
        assert "{ami_id}" in cmd

    def test_build_s3_check_command(self):
        """Test S3 check command generation."""
        cmd = _build_s3_check_command("test-bucket", "ami-789")

        assert "aws s3 ls" in cmd
        assert "{bucket_name}" in cmd
        assert "{ami_id}" in cmd
        assert "aws s3api head-object" in cmd

    def test_build_cleanup_command(self):
        """Test cleanup command generation."""
        cmd = _build_cleanup_command("ami-cleanup", "eu-west-1")

        assert "aws ec2 deregister-image" in cmd
        assert "{ami_id}" in cmd
        assert "{region}" in cmd


class TestPrintFunctions:
    """Test print helper functions."""

    def test_print_workflow_and_troubleshooting(self, capsys):
        """Test workflow printing."""
        _print_workflow_and_troubleshooting()

        captured = capsys.readouterr()
        assert "EXPORT WORKFLOW" in captured.out
        assert "TROUBLESHOOTING" in captured.out
        assert "stuck at 80%" in captured.out

    def test_print_monitoring_commands(self, capsys):
        """Test monitoring commands printing."""
        prepared = [
            {"bucket_name": "bucket1", "ami_id": "ami-111"},
            {"bucket_name": "bucket2", "ami_id": "ami-222"},
        ]

        _print_monitoring_commands(prepared)

        captured = capsys.readouterr()
        assert "S3 FILE SIZE MONITORING COMMANDS" in captured.out
        assert "bucket1" in captured.out
        assert "ami-111" in captured.out
        assert "bucket2" in captured.out
        assert "ami-222" in captured.out

    def test_print_cost_summary(self, capsys):
        """Test cost summary printing."""
        prepared = [
            {"monthly_savings": 5.0},
            {"monthly_savings": 10.0},
        ]

        _print_cost_summary(prepared)

        captured = capsys.readouterr()
        assert "POTENTIAL SAVINGS" in captured.out
        assert "Monthly: $15.00" in captured.out
        assert "Annual: $180.00" in captured.out


def test_generate_commands(capsys):
    """Test generating manual commands."""
    prepared = [
        {
            "ami_id": "ami-111",
            "bucket_name": "bucket-1",
            "region": "us-east-1",
            "snapshot_id": "snap-111",
            "size_gb": 50,
            "monthly_savings": 1.35,
        }
    ]

    export_cmds, monitor_cmds, cleanup_cmds = generate_manual_commands(prepared)

    assert len(export_cmds) == 1
    assert len(monitor_cmds) == 1
    assert len(cleanup_cmds) == 1
    assert "{ami_id}" in export_cmds[0]
    assert "{bucket_name}" in export_cmds[0]
    captured = capsys.readouterr()
    assert "MANUAL EXPORT COMMANDS" in captured.out


def test_get_target_snapshots():
    """Test retrieving target snapshots."""
    snapshots = _get_target_snapshots()

    assert len(snapshots) > 0
    assert all("snapshot_id" in s for s in snapshots)
    assert all("region" in s for s in snapshots)
    assert all("size_gb" in s for s in snapshots)


class TestPrepareAllSnapshots:
    """Test preparing all snapshots."""

    @patch("cost_toolkit.scripts.optimization.aws_snapshot_to_s3_semi_manual." "prepare_snapshot_for_export")
    def test_prepare_all_success(self, mock_prepare):
        """Test preparing all snapshots successfully."""
        mock_prepare.side_effect = [
            {"snapshot_id": "snap-1", "ami_id": "ami-1"},
            {"snapshot_id": "snap-2", "ami_id": "ami-2"},
        ]

        snapshots = [
            {"snapshot_id": "snap-1", "region": "us-east-1", "size_gb": 10, "description": "Test1"},
            {"snapshot_id": "snap-2", "region": "us-east-2", "size_gb": 20, "description": "Test2"},
        ]

        result = _prepare_all_snapshots(snapshots, "key", "secret")

        assert len(result) == 2
        assert result[0]["snapshot_id"] == "snap-1"
        assert result[1]["snapshot_id"] == "snap-2"

    @patch("cost_toolkit.scripts.optimization.aws_snapshot_to_s3_semi_manual." "prepare_snapshot_for_export")
    def test_prepare_all_with_failure(self, mock_prepare, capsys):
        """Test preparing snapshots with failure."""
        mock_prepare.side_effect = RuntimeError("Preparation failed")

        snapshots = [
            {
                "snapshot_id": "snap-fail",
                "region": "us-east-1",
                "size_gb": 10,
                "description": "Fail",
            }
        ]

        try:
            _prepare_all_snapshots(snapshots, "key", "secret")
        except RuntimeError:
            captured = capsys.readouterr()
            assert "Failed to prepare snap-fail" in captured.out


@patch("builtins.open", new_callable=mock_open)
def test_save_commands(mock_file, capsys):
    """Test saving commands to file."""
    prepared = [
        {
            "snapshot_id": "snap-111",
            "ami_id": "ami-111",
            "size_gb": 100,
        }
    ]
    export_cmds = ["export command 1"]
    monitor_cmds = ["monitor command 1"]
    cleanup_cmds = ["cleanup command 1"]

    _save_commands_to_file(prepared, export_cmds, monitor_cmds, cleanup_cmds)

    mock_file.assert_called_once()
    handle = mock_file()
    assert handle.write.called
    captured = capsys.readouterr()
    assert "Commands saved to:" in captured.out
