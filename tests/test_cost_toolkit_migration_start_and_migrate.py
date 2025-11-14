"""Comprehensive tests for aws_start_and_migrate.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.migration.aws_start_and_migrate import (
    OUTPUT_TRUNCATE_CHARS,
    _build_s3_sync_function,
    _build_volume_discovery_script,
    _build_volume_migration_commands,
    _create_migration_command,
    _execute_ssm_command,
    _monitor_migration_progress,
    _print_migration_output,
    _start_ec2_instance,
    main,
    setup_aws_credentials,
    start_instance_and_migrate,
)


def test_setup_credentials_calls_utils():
    """Test credentials setup delegates to aws_utils."""
    with patch("cost_toolkit.scripts.migration.aws_start_and_migrate.aws_utils") as mock_utils:
        setup_aws_credentials()
    mock_utils.setup_aws_credentials.assert_called_once()


class TestStartEc2Instance:
    """Tests for _start_ec2_instance function."""

    def test_start_instance_success(self, capsys):
        """Test successful instance start."""
        mock_ec2 = MagicMock()
        mock_waiter = MagicMock()
        mock_ec2.get_waiter.return_value = mock_waiter

        with patch("time.sleep"):
            _start_ec2_instance(mock_ec2, "i-123456")

        mock_ec2.start_instances.assert_called_once_with(InstanceIds=["i-123456"])
        mock_ec2.get_waiter.assert_called_once_with("instance_running")
        mock_waiter.wait.assert_called_once_with(
            InstanceIds=["i-123456"], WaiterConfig={"Delay": 15, "MaxAttempts": 40}
        )
        captured = capsys.readouterr()
        assert "STARTING EC2 INSTANCE" in captured.out
        assert "Starting instance: i-123456" in captured.out
        assert "Instance is now running" in captured.out

    def test_start_instance_prints_progress(self, capsys):
        """Test start instance prints progress messages."""
        mock_ec2 = MagicMock()
        mock_waiter = MagicMock()
        mock_ec2.get_waiter.return_value = mock_waiter

        with patch("time.sleep"):
            _start_ec2_instance(mock_ec2, "i-test")

        captured = capsys.readouterr()
        assert "Start command sent" in captured.out
        assert "Waiting for instance to be running" in captured.out
        assert "Waiting additional 60 seconds for SSM agent" in captured.out


class TestBuildVolumeDiscoveryScript:
    """Tests for _build_volume_discovery_script function."""

    def test_build_discovery_script_contains_keywords(self):
        """Test discovery script contains expected commands."""
        script = _build_volume_discovery_script()
        assert "lsblk" in script
        assert "VOL384_DEVICE" in script
        assert "VOL64_DEVICE" in script
        assert "/mnt/vol384" in script
        assert "/mnt/vol64" in script

    def test_discovery_script_mounts_volumes(self):
        """Test script includes mount commands."""
        script = _build_volume_discovery_script()
        assert "mount $VOL384_DEVICE /mnt/vol384" in script
        assert "mount $VOL64_DEVICE /mnt/vol64" in script

    def test_discovery_script_checks_contents(self):
        """Test script checks directory contents."""
        script = _build_volume_discovery_script()
        assert "ls -la" in script
        assert "du -sh" in script
        assert "df -h" in script


class TestBuildS3SyncFunction:
    """Tests for _build_s3_sync_function function."""

    def test_sync_function_uses_bucket_name(self):
        """Test sync function includes bucket name."""
        bucket = "test-bucket"
        script = _build_s3_sync_function(bucket)
        assert f"s3://{bucket}/" in script

    def test_sync_function_excludes_patterns(self):
        """Test sync function excludes temporary files."""
        script = _build_s3_sync_function("test-bucket")
        assert '--exclude "*.tmp"' in script
        assert '--exclude "*.log"' in script
        assert '--exclude ".cache/*"' in script
        assert '--exclude "lost+found/*"' in script

    def test_sync_function_has_region(self):
        """Test sync function specifies region."""
        script = _build_s3_sync_function("test-bucket")
        assert "--region eu-west-2" in script
        assert "--storage-class STANDARD" in script


class TestBuildVolumeMigrationCommands:
    """Tests for _build_volume_migration_commands function."""

    def test_migration_commands_sync_directories(self):
        """Test migration syncs expected directories."""
        script = _build_volume_migration_commands()
        assert 'sync_to_s3 "/mnt/vol384/home" "384gb-volume/home"' in script
        assert 'sync_to_s3 "/mnt/vol384/opt" "384gb-volume/opt"' in script
        assert 'sync_to_s3 "/mnt/vol64/home" "64gb-volume/home"' in script
        assert 'sync_to_s3 "/mnt/vol64/var" "64gb-volume/var"' in script

    def test_migration_checks_directories_exist(self):
        """Test migration checks for directory existence."""
        script = _build_volume_migration_commands()
        assert '[ -d "/mnt/vol384" ]' in script
        assert '[ -d "/mnt/vol64" ]' in script


class TestCreateMigrationCommand:
    """Tests for _create_migration_command function."""

    def test_create_command_includes_bucket(self):
        """Test command includes target bucket."""
        bucket = "my-backup-bucket"
        command = _create_migration_command(bucket)
        assert bucket in command

    def test_create_command_has_shebang(self):
        """Test command has bash shebang."""
        command = _create_migration_command("test-bucket")
        assert command.startswith("#!/bin/bash")

    def test_create_command_sets_region(self):
        """Test command sets AWS region."""
        command = _create_migration_command("test-bucket")
        assert "AWS_DEFAULT_REGION=eu-west-2" in command

    def test_create_command_creates_mount_points(self):
        """Test command creates mount directories."""
        command = _create_migration_command("test-bucket")
        assert "mkdir -p /mnt/vol384" in command
        assert "mkdir -p /mnt/vol64" in command

    def test_create_command_combines_all_parts(self):
        """Test command includes all script sections."""
        command = _create_migration_command("test-bucket")
        assert "lsblk" in command
        assert "sync_to_s3" in command
        assert "Migration complete" in command


class TestExecuteSsmCommand:
    """Tests for _execute_ssm_command function."""

    def test_execute_ssm_sends_command(self, capsys):
        """Test SSM command is sent successfully."""
        mock_ssm = MagicMock()
        mock_ssm.send_command.return_value = {"Command": {"CommandId": "cmd-123"}}

        command_id = _execute_ssm_command(mock_ssm, "i-123", "echo test")

        assert command_id == "cmd-123"
        mock_ssm.send_command.assert_called_once()
        call_args = mock_ssm.send_command.call_args
        assert call_args[1]["InstanceIds"] == ["i-123"]
        assert call_args[1]["DocumentName"] == "AWS-RunShellScript"
        assert call_args[1]["Parameters"]["commands"] == ["echo test"]
        captured = capsys.readouterr()
        assert "EXECUTING MIGRATION VIA SSM" in captured.out
        assert "Command ID: cmd-123" in captured.out

    def test_execute_ssm_includes_timeout(self):
        """Test SSM command includes execution timeout."""
        mock_ssm = MagicMock()
        mock_ssm.send_command.return_value = {"Command": {"CommandId": "cmd-123"}}

        _execute_ssm_command(mock_ssm, "i-123", "test")

        call_args = mock_ssm.send_command.call_args
        assert call_args[1]["Parameters"]["executionTimeout"] == ["7200"]


class TestMonitorMigrationProgress:
    """Tests for _monitor_migration_progress function."""

    def test_monitor_success(self, capsys):
        """Test monitoring successful migration."""
        mock_ssm = MagicMock()
        mock_ssm.get_command_invocation.return_value = {
            "Status": "Success",
            "StandardOutputContent": "Migration completed",
            "StandardErrorContent": "",
        }

        with patch("time.sleep"):
            with patch(
                "cost_toolkit.scripts.migration.aws_start_and_migrate._print_migration_output"
            ) as mock_print:
                _monitor_migration_progress(mock_ssm, "i-123", "cmd-123")

        mock_ssm.get_command_invocation.assert_called_with(CommandId="cmd-123", InstanceId="i-123")
        mock_print.assert_called_once()
        captured = capsys.readouterr()
        assert "MONITORING MIGRATION PROGRESS" in captured.out

    def test_monitor_failed_status(self):
        """Test monitoring failed migration."""
        mock_ssm = MagicMock()
        mock_ssm.get_command_invocation.return_value = {
            "Status": "Failed",
            "StandardOutputContent": "",
            "StandardErrorContent": "Error occurred",
        }

        with patch("time.sleep"):
            with patch(
                "cost_toolkit.scripts.migration.aws_start_and_migrate._print_migration_output"
            ) as mock_print:
                _monitor_migration_progress(mock_ssm, "i-123", "cmd-123")

        mock_print.assert_called_once()

    def test_monitor_in_progress_then_success(self):
        """Test monitoring transitions from in progress to success."""
        mock_ssm = MagicMock()
        mock_ssm.get_command_invocation.side_effect = [
            {"Status": "InProgress"},
            {"Status": "Success", "StandardOutputContent": "Done", "StandardErrorContent": ""},
        ]

        with patch("time.sleep"):
            with patch(
                "cost_toolkit.scripts.migration.aws_start_and_migrate._print_migration_output"
            ):
                _monitor_migration_progress(mock_ssm, "i-123", "cmd-123")

        assert mock_ssm.get_command_invocation.call_count == 2

    def test_monitor_timeout(self, capsys):
        """Test monitoring times out."""
        mock_ssm = MagicMock()
        mock_ssm.get_command_invocation.return_value = {"Status": "InProgress"}

        with patch("time.sleep"):
            with patch(
                "cost_toolkit.scripts.migration.aws_start_and_migrate.MAX_SSM_MONITOR_SECONDS", 60
            ):
                _monitor_migration_progress(mock_ssm, "i-123", "cmd-123")

        captured = capsys.readouterr()
        assert "Migration timeout reached" in captured.out

    def test_monitor_handles_client_error(self, capsys):
        """Test monitoring handles client errors."""
        mock_ssm = MagicMock()
        mock_ssm.get_command_invocation.side_effect = [
            ClientError({"Error": {"Code": "ServiceError"}}, "get_command_invocation"),
            {"Status": "Success", "StandardOutputContent": "", "StandardErrorContent": ""},
        ]

        with patch("time.sleep"):
            with patch(
                "cost_toolkit.scripts.migration.aws_start_and_migrate._print_migration_output"
            ):
                _monitor_migration_progress(mock_ssm, "i-123", "cmd-123")

        captured = capsys.readouterr()
        assert "Error checking status" in captured.out


class TestPrintMigrationOutput:
    """Tests for _print_migration_output function."""

    def test_print_output_success(self, capsys):
        """Test printing successful migration output."""
        command_status = {
            "StandardOutputContent": "Files synced successfully",
            "StandardErrorContent": "",
        }

        _print_migration_output(command_status, "Success")

        captured = capsys.readouterr()
        assert "MIGRATION OUTPUT" in captured.out
        assert "Files synced successfully" in captured.out
        assert "Migration completed successfully" in captured.out
        assert "Potential savings" in captured.out

    def test_print_output_failed(self, capsys):
        """Test printing failed migration output."""
        command_status = {
            "StandardOutputContent": "",
            "StandardErrorContent": "Mount failed",
        }

        _print_migration_output(command_status, "Failed")

        captured = capsys.readouterr()
        assert "ERRORS" in captured.out
        assert "Mount failed" in captured.out
        assert "Migration failed with status: Failed" in captured.out

    def test_print_output_truncates_long_output(self, capsys):
        """Test output truncation for long content."""
        long_output = "x" * (OUTPUT_TRUNCATE_CHARS + 1000)
        command_status = {
            "StandardOutputContent": long_output,
            "StandardErrorContent": "",
        }

        _print_migration_output(command_status, "Success")

        captured = capsys.readouterr()
        assert "(output truncated)" in captured.out
        assert len(captured.out) < len(long_output)

    def test_print_output_no_error_content(self, capsys):
        """Test when no error content exists."""
        command_status = {"StandardOutputContent": "OK"}

        _print_migration_output(command_status, "Success")

        captured = capsys.readouterr()
        assert "ERRORS" not in captured.out


class TestStartInstanceAndMigrate:
    """Tests for start_instance_and_migrate function."""

    def test_start_and_migrate_success(self, capsys):
        """Test successful instance start and migration."""
        with patch("cost_toolkit.scripts.migration.aws_start_and_migrate.setup_aws_credentials"):
            with patch("boto3.client") as mock_client:
                mock_ec2 = MagicMock()
                mock_ssm = MagicMock()
                mock_ssm.send_command.return_value = {"Command": {"CommandId": "cmd-123"}}
                mock_ssm.get_command_invocation.return_value = {
                    "Status": "Success",
                    "StandardOutputContent": "",
                    "StandardErrorContent": "",
                }
                mock_client.side_effect = [mock_ec2, mock_ssm]

                with patch("time.sleep"):
                    start_instance_and_migrate()

        captured = capsys.readouterr()
        assert "AWS Instance Startup and Migration" in captured.out

    def test_start_and_migrate_handles_error(self, capsys):
        """Test error handling during start and migrate."""
        with patch("cost_toolkit.scripts.migration.aws_start_and_migrate.setup_aws_credentials"):
            with patch("boto3.client") as mock_client:
                mock_ec2 = MagicMock()
                mock_ec2.start_instances.side_effect = ClientError(
                    {"Error": {"Code": "ServiceError"}}, "start_instances"
                )
                mock_client.return_value = mock_ec2

                start_instance_and_migrate()

        captured = capsys.readouterr()
        assert "Error during execution" in captured.out


def test_main_calls_start_and_migrate():
    """Test main function calls start_instance_and_migrate."""
    with patch(
        "cost_toolkit.scripts.migration.aws_start_and_migrate.start_instance_and_migrate"
    ) as mock_start:
        main()
    mock_start.assert_called_once()
