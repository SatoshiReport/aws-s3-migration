"""Comprehensive tests for aws_efs_cleanup.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_efs_cleanup import (
    _delete_mount_targets,
    _delete_single_filesystem,
    _process_region,
    _wait_for_mount_targets_deletion,
    delete_efs_resources,
    setup_aws_credentials,
)


class TestSetupAwsCredentials:
    """Tests for setup_aws_credentials function."""

    def test_calls_shared_setup(self):
        """Test that setup calls the shared utility."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_efs_cleanup.aws_utils.setup_aws_credentials"
        ) as mock_setup:
            setup_aws_credentials()
            mock_setup.assert_called_once()


class TestDeleteMountTargets:
    """Tests for _delete_mount_targets function."""

    def test_delete_multiple_mount_targets(self, capsys):
        """Test deleting multiple mount targets."""
        mock_client = MagicMock()
        mock_client.describe_mount_targets.return_value = {
            "MountTargets": [
                {"MountTargetId": "mt-1"},
                {"MountTargetId": "mt-2"},
                {"MountTargetId": "mt-3"},
            ]
        }

        count = _delete_mount_targets(mock_client, "fs-123")

        assert count == 3
        assert mock_client.delete_mount_target.call_count == 3
        captured = capsys.readouterr()
        assert "Deleting mount target" in captured.out

    def test_delete_no_mount_targets(self):
        """Test when no mount targets exist."""
        mock_client = MagicMock()
        mock_client.describe_mount_targets.return_value = {"MountTargets": []}

        count = _delete_mount_targets(mock_client, "fs-123")

        assert count == 0
        mock_client.delete_mount_target.assert_not_called()

    def test_delete_single_mount_target(self, capsys):
        """Test deleting single mount target."""
        mock_client = MagicMock()
        mock_client.describe_mount_targets.return_value = {
            "MountTargets": [{"MountTargetId": "mt-single"}]
        }

        count = _delete_mount_targets(mock_client, "fs-123")

        assert count == 1
        mock_client.delete_mount_target.assert_called_once_with(MountTargetId="mt-single")


class TestWaitForMountTargetsDeletion:
    """Tests for _wait_for_mount_targets_deletion function."""

    def test_wait_until_deleted(self, capsys):
        """Test waiting until mount targets are deleted."""
        mock_client = MagicMock()
        mock_client.describe_mount_targets.side_effect = [
            {"MountTargets": [{"MountTargetId": "mt-1"}]},
            {"MountTargets": []},
        ]

        with patch("time.sleep"):
            _wait_for_mount_targets_deletion(mock_client, "fs-123")

        captured = capsys.readouterr()
        assert "All mount targets deleted" in captured.out

    def test_wait_with_timeout(self, capsys):
        """Test waiting with multiple retries."""
        mock_client = MagicMock()
        mock_client.describe_mount_targets.side_effect = [
            {"MountTargets": [{"MountTargetId": "mt-1"}, {"MountTargetId": "mt-2"}]},
            {"MountTargets": [{"MountTargetId": "mt-1"}]},
            {"MountTargets": []},
        ]

        with patch("time.sleep"):
            _wait_for_mount_targets_deletion(mock_client, "fs-123")

        captured = capsys.readouterr()
        assert "Still waiting" in captured.out

    def test_wait_handles_error(self):
        """Test that errors during wait are handled."""
        mock_client = MagicMock()
        mock_client.describe_mount_targets.side_effect = ClientError(
            {"Error": {"Code": "FileSystemNotFound"}}, "describe_mount_targets"
        )

        with patch("time.sleep"):
            # Should not raise exception
            _wait_for_mount_targets_deletion(mock_client, "fs-123")


class TestDeleteSingleFilesystem:
    """Tests for _delete_single_filesystem function."""

    def test_delete_filesystem_with_mount_targets(self, capsys):
        """Test deleting filesystem with mount targets."""
        mock_client = MagicMock()

        with patch(
            "cost_toolkit.scripts.cleanup.aws_efs_cleanup._delete_mount_targets", return_value=2
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_efs_cleanup._wait_for_mount_targets_deletion"
            ):
                fs = {"FileSystemId": "fs-123"}

                success, mt_count = _delete_single_filesystem(mock_client, fs)

        assert success is True
        assert mt_count == 2
        mock_client.delete_file_system.assert_called_once_with(FileSystemId="fs-123")
        captured = capsys.readouterr()
        assert "Successfully deleted" in captured.out

    def test_delete_filesystem_no_mount_targets(self, capsys):
        """Test deleting filesystem without mount targets."""
        mock_client = MagicMock()

        with patch(
            "cost_toolkit.scripts.cleanup.aws_efs_cleanup._delete_mount_targets", return_value=0
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_efs_cleanup._wait_for_mount_targets_deletion"
            ) as mock_wait:
                fs = {"FileSystemId": "fs-123"}

                success, mt_count = _delete_single_filesystem(mock_client, fs)

        assert success is True
        mock_wait.assert_not_called()
        mock_client.delete_file_system.assert_called_once()

    def test_delete_filesystem_error(self, capsys):
        """Test error when deleting filesystem."""
        mock_client = MagicMock()
        mock_client.delete_file_system.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "delete_file_system"
        )

        with patch(
            "cost_toolkit.scripts.cleanup.aws_efs_cleanup._delete_mount_targets", return_value=0
        ):
            fs = {"FileSystemId": "fs-123"}

            success, mt_count = _delete_single_filesystem(mock_client, fs)

        assert success is False
        assert mt_count == 0
        captured = capsys.readouterr()
        assert "Failed to delete" in captured.out


class TestProcessRegion:
    """Tests for _process_region function."""

    def test_process_region_with_filesystems(self, capsys):
        """Test processing region with EFS filesystems."""
        with patch("boto3.client") as mock_client:
            mock_efs = MagicMock()
            mock_efs.describe_file_systems.return_value = {
                "FileSystems": [
                    {"FileSystemId": "fs-1"},
                    {"FileSystemId": "fs-2"},
                ]
            }
            mock_client.return_value = mock_efs

            with patch(
                "cost_toolkit.scripts.cleanup.aws_efs_cleanup._delete_single_filesystem",
                return_value=(True, 2),
            ):
                fs_count, mt_count = _process_region("us-east-1")

        assert fs_count == 2
        assert mt_count == 4  # 2 filesystems * 2 mount targets each
        captured = capsys.readouterr()
        assert "Found 2 EFS file systems" in captured.out

    def test_process_region_no_filesystems(self, capsys):
        """Test processing region with no filesystems."""
        with patch("boto3.client") as mock_client:
            mock_efs = MagicMock()
            mock_efs.describe_file_systems.return_value = {"FileSystems": []}
            mock_client.return_value = mock_efs

            fs_count, mt_count = _process_region("us-east-1")

        assert fs_count == 0
        assert mt_count == 0
        captured = capsys.readouterr()
        assert "No EFS file systems found" in captured.out

    def test_process_region_partial_failures(self, capsys):
        """Test processing region with some failures."""
        with patch("boto3.client") as mock_client:
            mock_efs = MagicMock()
            mock_efs.describe_file_systems.return_value = {
                "FileSystems": [
                    {"FileSystemId": "fs-1"},
                    {"FileSystemId": "fs-2"},
                    {"FileSystemId": "fs-3"},
                ]
            }
            mock_client.return_value = mock_efs

            with patch(
                "cost_toolkit.scripts.cleanup.aws_efs_cleanup._delete_single_filesystem",
                side_effect=[(True, 1), (False, 0), (True, 2)],
            ):
                fs_count, mt_count = _process_region("us-east-1")

        assert fs_count == 2
        assert mt_count == 3


class TestDeleteEfsResources:
    """Tests for delete_efs_resources function."""

    def test_delete_resources_multiple_regions(self, capsys):
        """Test deleting resources across multiple regions."""
        with patch("cost_toolkit.scripts.cleanup.aws_efs_cleanup.setup_aws_credentials"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_efs_cleanup._process_region", return_value=(2, 4)
            ):
                delete_efs_resources()

        captured = capsys.readouterr()
        assert "EFS Cleanup Summary" in captured.out
        assert "Total EFS file systems deleted: 4" in captured.out
        assert "Total mount targets deleted: 8" in captured.out
        assert "cleanup completed successfully" in captured.out

    def test_delete_resources_no_resources(self, capsys):
        """Test when no resources found."""
        with patch("cost_toolkit.scripts.cleanup.aws_efs_cleanup.setup_aws_credentials"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_efs_cleanup._process_region", return_value=(0, 0)
            ):
                delete_efs_resources()

        captured = capsys.readouterr()
        assert "No EFS resources were deleted" in captured.out

    def test_delete_resources_handles_errors(self, capsys):
        """Test error handling during resource deletion."""
        with patch("cost_toolkit.scripts.cleanup.aws_efs_cleanup.setup_aws_credentials"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_efs_cleanup._process_region"
            ) as mock_process:
                mock_process.side_effect = [
                    (1, 2),
                    ClientError({"Error": {"Code": "AccessDenied"}}, "describe_file_systems"),
                ]

                delete_efs_resources()

        captured = capsys.readouterr()
        assert "Error accessing EFS" in captured.out
        assert "Total EFS file systems deleted: 1" in captured.out
