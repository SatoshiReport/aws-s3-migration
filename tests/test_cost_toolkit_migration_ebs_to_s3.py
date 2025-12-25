"""Comprehensive tests for aws_ebs_to_s3_migration.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.migration.aws_ebs_to_s3_migration import (
    REMAINING_VOLUMES,
    _create_s3_bucket,
    _display_volume_info,
    _generate_migration_script,
    _print_next_steps,
    _print_setup_header,
    _write_migration_script,
    create_s3_bucket_and_migrate,
    main,
)


@patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration._print_next_steps")
@patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration._write_migration_script")
@patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration._generate_migration_script")
@patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration._display_volume_info")
@patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration._create_s3_bucket")
@patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration.aws_utils.setup_aws_credentials")
@patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration.boto3.client")
def test_setup_credentials_calls_utils(
    mock_boto_client,
    mock_setup_creds,
    mock_create_bucket,
    mock_display_volume_info,
    mock_generate_script,
    _mock_write_script,
    _mock_print_next_steps,
):
    """create_s3_bucket_and_migrate should load credentials before running."""
    mock_generate_script.return_value = "#!/bin/bash\n echo test"
    mock_s3 = MagicMock()
    mock_ec2 = MagicMock()
    mock_boto_client.side_effect = [mock_s3, mock_ec2]

    create_s3_bucket_and_migrate()

    mock_setup_creds.assert_called_once()
    mock_create_bucket.assert_called_once_with(mock_s3, "aws-user-files-backup-london")
    mock_display_volume_info.assert_called_once_with(mock_ec2)


def test_print_header_output(capsys):
    """Test setup header is printed."""
    _print_setup_header()

    captured = capsys.readouterr()
    assert "AWS EBS to S3 Migration Setup" in captured.out
    assert "Creating S3 bucket" in captured.out
    assert "S3 Standard" in captured.out


class TestCreateS3Bucket:
    """Tests for _create_s3_bucket function."""

    def test_create_bucket_success(self, capsys):
        """Test successful bucket creation."""
        mock_s3 = MagicMock()

        _create_s3_bucket(mock_s3, "test-bucket")

        mock_s3.create_bucket.assert_called_once_with(Bucket="test-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"})
        captured = capsys.readouterr()
        assert "CREATING S3 BUCKET" in captured.out
        assert "test-bucket" in captured.out
        assert "eu-west-2" in captured.out
        assert "Created S3 bucket: test-bucket" in captured.out

    def test_create_bucket_already_exists(self, capsys):
        """Test when bucket already exists."""
        mock_s3 = MagicMock()
        mock_s3.create_bucket.side_effect = ClientError({"Error": {"Code": "BucketAlreadyExists"}}, "create_bucket")

        _create_s3_bucket(mock_s3, "existing-bucket")

        captured = capsys.readouterr()
        assert "S3 bucket already exists" in captured.out

    def test_create_bucket_other_error(self):
        """Test handling of other errors during bucket creation."""
        mock_s3 = MagicMock()
        mock_s3.create_bucket.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "create_bucket")

        with pytest.raises(ClientError):
            _create_s3_bucket(mock_s3, "test-bucket")


class TestDisplayVolumeInfo:
    """Tests for _display_volume_info function."""

    def test_display_volumes_with_names(self, capsys):
        """Test displaying volumes with name tags."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_volumes.return_value = {
            "Volumes": [
                {
                    "VolumeId": "vol-123",
                    "Size": 384,
                    "Tags": [{"Key": "Name", "Value": "Data Volume"}],
                },
                {
                    "VolumeId": "vol-456",
                    "Size": 64,
                    "Tags": [{"Key": "Name", "Value": "Tars 3"}],
                },
            ]
        }

        _display_volume_info(mock_ec2)

        captured = capsys.readouterr()
        assert "CURRENT EBS VOLUMES" in captured.out
        assert "Data Volume" in captured.out
        assert "vol-123" in captured.out
        assert "384 GB" in captured.out
        assert "Tars 3" in captured.out
        assert "64 GB" in captured.out

    def test_display_volumes_without_names(self, capsys):
        """Test displaying volumes without name tags."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_volumes.return_value = {
            "Volumes": [
                {"VolumeId": "vol-789", "Size": 100, "Tags": []},
            ]
        }

        _display_volume_info(mock_ec2)

        captured = capsys.readouterr()
        assert "No name" in captured.out
        assert "100 GB" in captured.out

    def test_display_volumes_calls_describe(self):
        """Test describe_volumes is called with correct volume IDs."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_volumes.return_value = {"Volumes": []}

        _display_volume_info(mock_ec2)

        mock_ec2.describe_volumes.assert_called_once_with(VolumeIds=REMAINING_VOLUMES)


class TestGenerateMigrationScript:
    """Tests for _generate_migration_script function."""

    def test_generate_script_includes_bucket(self):
        """Test script includes bucket name."""
        bucket = "my-test-bucket"
        script = _generate_migration_script(bucket)

        assert bucket in script
        assert f"s3://{bucket}/" in script

    def test_generate_script_has_shebang(self):
        """Test script has bash shebang."""
        script = _generate_migration_script("test-bucket")
        assert script.startswith("#!/bin/bash")

    def test_generate_script_creates_mount_points(self):
        """Test script creates mount directories."""
        script = _generate_migration_script("test-bucket")
        assert "mkdir -p /mnt/vol384" in script
        assert "mkdir -p /mnt/vol64" in script

    def test_generate_script_mounts_volumes(self):
        """Test script mounts volumes."""
        script = _generate_migration_script("test-bucket")
        assert "mount /dev/nvme1n1 /mnt/vol384" in script
        assert "mount /dev/nvme2n1 /mnt/vol64" in script

    def test_generate_script_syncs_directories(self):
        """Test script syncs expected directories."""
        script = _generate_migration_script("test-bucket")
        assert "sync_to_s3" in script
        assert "/mnt/vol384/home" in script
        assert "/mnt/vol64/opt" in script
        assert "384gb-volume/home" in script
        assert "64gb-volume/opt" in script

    def test_generate_script_excludes_patterns(self):
        """Test script excludes temporary files."""
        script = _generate_migration_script("test-bucket")
        assert '--exclude "*.tmp"' in script
        assert '--exclude "*.log"' in script
        assert '--exclude ".cache/*"' in script

    def test_generate_script_includes_summary(self):
        """Test script includes cost summary."""
        script = _generate_migration_script("test-bucket")
        assert "Migration summary" in script
        assert "Cost comparison" in script
        assert "$35.84/month" in script
        assert "$10.30/month" in script


class TestWriteMigrationScript:
    """Tests for _write_migration_script function."""

    def test_write_script_creates_file(self, capsys):
        """Test script file is created."""
        script_content = "#!/bin/bash\necho test\n"

        with patch("builtins.open", create=True) as mock_open:
            with patch("os.chmod") as mock_chmod:
                _write_migration_script(script_content)

        mock_open.assert_called_once_with("ebs_to_s3_migration.sh", "w", encoding="utf-8")
        mock_chmod.assert_called_once_with("ebs_to_s3_migration.sh", 0o700)
        captured = capsys.readouterr()
        assert "MIGRATION SCRIPT" in captured.out
        assert "ebs_to_s3_migration.sh" in captured.out

    def test_write_script_makes_executable(self):
        """Test script is made executable."""
        with patch("builtins.open", create=True):
            with patch("os.chmod") as mock_chmod:
                _write_migration_script("test script")

        mock_chmod.assert_called_once_with("ebs_to_s3_migration.sh", 0o700)


class TestPrintNextSteps:
    """Tests for _print_next_steps function."""

    def test_print_next_steps_output(self, capsys):
        """Test next steps are printed."""
        bucket = "my-backup-bucket"
        _print_next_steps(bucket)

        captured = capsys.readouterr()
        assert "NEXT STEPS" in captured.out
        assert bucket in captured.out
        assert "ebs_to_s3_migration.sh" in captured.out
        assert "Run the script" in captured.out

    def test_print_next_steps_includes_costs(self, capsys):
        """Test cost information is included."""
        _print_next_steps("test-bucket")

        captured = capsys.readouterr()
        assert "EXPECTED COST SAVINGS" in captured.out
        assert "$35.84/month" in captured.out
        assert "$10.30/month" in captured.out
        assert "$25.54" in captured.out

    def test_print_next_steps_includes_total_optimization(self, capsys):
        """Test total optimization impact is shown."""
        _print_next_steps("test-bucket")

        captured = capsys.readouterr()
        assert "TOTAL OPTIMIZATION IMPACT" in captured.out
        assert "$166.92/month" in captured.out
        assert "$192.46/month" in captured.out


class TestCreateS3BucketAndMigrate:
    """Tests for create_s3_bucket_and_migrate function."""

    def test_create_and_migrate_success(self, capsys):
        """Test successful bucket creation and script generation."""
        with patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration.aws_utils.setup_aws_credentials"):
            with patch("boto3.client") as mock_client:
                with patch("builtins.open", create=True):
                    with patch("os.chmod"):
                        mock_s3 = MagicMock()
                        mock_ec2 = MagicMock()
                        mock_ec2.describe_volumes.return_value = {"Volumes": []}
                        mock_client.side_effect = [mock_s3, mock_ec2]

                        create_s3_bucket_and_migrate()

        captured = capsys.readouterr()
        assert "AWS EBS to S3 Migration Setup" in captured.out

    def test_create_and_migrate_handles_error(self, capsys):
        """Test error handling during setup."""
        with patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration.aws_utils.setup_aws_credentials"):
            with patch("boto3.client") as mock_client:
                mock_s3 = MagicMock()
                mock_s3.create_bucket.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "create_bucket")
                mock_client.return_value = mock_s3

                create_s3_bucket_and_migrate()

        captured = capsys.readouterr()
        assert "Error during setup" in captured.out

    def test_create_and_migrate_uses_correct_region(self):
        """Test correct AWS region is used."""
        with patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration.aws_utils.setup_aws_credentials"):
            with patch("boto3.client") as mock_client:
                with patch("builtins.open", create=True):
                    with patch("os.chmod"):
                        mock_s3 = MagicMock()
                        mock_ec2 = MagicMock()
                        mock_ec2.describe_volumes.return_value = {"Volumes": []}
                        mock_client.side_effect = [mock_s3, mock_ec2]

                        create_s3_bucket_and_migrate()

        assert mock_client.call_count == 2
        calls = mock_client.call_args_list
        assert calls[0][0] == ("s3",)
        assert calls[0][1]["region_name"] == "eu-west-2"
        assert calls[1][0] == ("ec2",)
        assert calls[1][1]["region_name"] == "eu-west-2"

    def test_create_and_migrate_calls_all_functions(self):
        """Test all helper functions are called."""
        with patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration.aws_utils.setup_aws_credentials"):
            with patch("boto3.client") as mock_client:
                with (
                    patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration._print_setup_header") as mock_header,
                    patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration._create_s3_bucket") as mock_bucket,
                    patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration._display_volume_info") as mock_volume,
                    patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration._write_migration_script") as mock_write,
                    patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration._print_next_steps") as mock_steps,
                ):
                    mock_s3 = MagicMock()
                    mock_ec2 = MagicMock()
                    mock_client.side_effect = [mock_s3, mock_ec2]

                    create_s3_bucket_and_migrate()

        mock_header.assert_called_once()
        mock_bucket.assert_called_once()
        mock_volume.assert_called_once()
        mock_write.assert_called_once()
        mock_steps.assert_called_once()


def test_main_calls_create_s3_bucket_and_migrate():
    """Test main function calls create_s3_bucket_and_migrate."""
    with patch("cost_toolkit.scripts.migration.aws_ebs_to_s3_migration.create_s3_bucket_and_migrate") as mock_create:
        main()
    mock_create.assert_called_once()


def test_remaining_volumes_constant():
    """Test REMAINING_VOLUMES constant is defined correctly."""
    assert isinstance(REMAINING_VOLUMES, list)
    assert len(REMAINING_VOLUMES) == 2
    assert all(vol.startswith("vol-") for vol in REMAINING_VOLUMES)
