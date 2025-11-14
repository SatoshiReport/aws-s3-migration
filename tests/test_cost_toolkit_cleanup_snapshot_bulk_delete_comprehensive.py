"""Comprehensive tests for aws_snapshot_bulk_delete.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete import (
    confirm_bulk_deletion,
    delete_snapshot_safely,
    find_snapshot_region,
    get_bulk_deletion_snapshots,
    get_snapshot_details,
    main,
    print_bulk_deletion_summary,
    print_bulk_deletion_warning,
    process_bulk_deletions,
)


class TestFindSnapshotRegion:
    """Tests for find_snapshot_region function."""

    def test_find_snapshot_in_first_region(self):
        """Test finding snapshot in first region checked."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_snapshots.return_value = {"Snapshots": [{"SnapshotId": "snap-123"}]}
            mock_client.return_value = mock_ec2

            region = find_snapshot_region("snap-123")

            assert region == "eu-west-2"

    def test_find_snapshot_in_later_region(self):
        """Test finding snapshot after checking multiple regions."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()

            # Simulate not found in first region, found in second
            def describe_side_effect(**_):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    error = ClientError(
                        {"Error": {"Code": "InvalidSnapshot.NotFound"}}, "describe_snapshots"
                    )
                    error.response = {"Error": {"Code": "InvalidSnapshot.NotFound"}}
                    raise error
                return {"Snapshots": [{"SnapshotId": "snap-123"}]}

            call_count = 0
            mock_ec2.describe_snapshots.side_effect = describe_side_effect
            mock_ec2.exceptions.ClientError = ClientError
            mock_client.return_value = mock_ec2

            region = find_snapshot_region("snap-123")

            assert region == "us-east-1"

    def test_snapshot_not_found_any_region(self):
        """Test when snapshot not found in any region."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            error = ClientError(
                {"Error": {"Code": "InvalidSnapshot.NotFound"}}, "describe_snapshots"
            )
            error.response = {"Error": {"Code": "InvalidSnapshot.NotFound"}}
            mock_ec2.describe_snapshots.side_effect = error
            mock_ec2.exceptions.ClientError = ClientError
            mock_client.return_value = mock_ec2

            region = find_snapshot_region("snap-notfound")

            assert region is None

    def test_other_error_continues_search(self, capsys):
        """Test that other errors don't stop the search."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()

            def describe_side_effect(**_):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ClientError({"Error": {"Code": "ServiceError"}}, "describe_snapshots")
                return {"Snapshots": [{"SnapshotId": "snap-123"}]}

            call_count = 0
            mock_ec2.describe_snapshots.side_effect = describe_side_effect
            mock_ec2.exceptions.ClientError = ClientError
            mock_client.return_value = mock_ec2

            region = find_snapshot_region("snap-123")

            assert region == "us-east-1"
            captured = capsys.readouterr()
            assert "Error checking" in captured.out


class TestGetSnapshotDetails:
    """Tests for get_snapshot_details function."""

    def test_get_snapshot_details_success(self):
        """Test successful retrieval of snapshot details."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_snapshots.return_value = {
                "Snapshots": [
                    {
                        "SnapshotId": "snap-123",
                        "VolumeSize": 100,
                        "State": "completed",
                        "StartTime": "2024-01-01",
                        "Description": "Test snapshot",
                        "Encrypted": True,
                    }
                ]
            }
            mock_client.return_value = mock_ec2

            result = get_snapshot_details("snap-123", "us-east-1")

            assert result is not None
            assert result["snapshot_id"] == "snap-123"
            assert result["size_gb"] == 100
            assert result["state"] == "completed"
            assert result["encrypted"] is True

    def test_get_snapshot_details_no_description(self):
        """Test snapshot without description."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_snapshots.return_value = {
                "Snapshots": [
                    {
                        "SnapshotId": "snap-123",
                        "VolumeSize": 50,
                        "State": "completed",
                        "StartTime": "2024-01-01",
                        "Encrypted": False,
                    }
                ]
            }
            mock_client.return_value = mock_ec2

            result = get_snapshot_details("snap-123", "us-east-1")

            assert result["description"] == "No description"

    def test_get_snapshot_details_error(self, capsys):
        """Test error when retrieving snapshot details."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_snapshots.side_effect = ClientError(
                {"Error": {"Code": "InvalidSnapshot.NotFound"}}, "describe_snapshots"
            )
            mock_client.return_value = mock_ec2

            result = get_snapshot_details("snap-notfound", "us-east-1")

            assert result is None
            captured = capsys.readouterr()
            assert "Error getting details" in captured.out

    def test_get_snapshot_details_no_snapshots(self):
        """Test when no snapshots returned."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.describe_snapshots.return_value = {"Snapshots": []}
            mock_client.return_value = mock_ec2

            result = get_snapshot_details("snap-123", "us-east-1")

            assert result is None


class TestDeleteSnapshotSafely:
    """Tests for delete_snapshot_safely function."""

    def test_delete_snapshot_success(self, capsys):
        """Test successful snapshot deletion."""
        with patch("boto3.client") as mock_client:
            with patch(
                "cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.get_snapshot_details"
            ) as mock_get:
                mock_ec2 = MagicMock()
                mock_client.return_value = mock_ec2

                mock_get.return_value = {
                    "snapshot_id": "snap-123",
                    "size_gb": 100,
                    "state": "completed",
                    "start_time": "2024-01-01",
                    "description": "Test snapshot",
                }

                result = delete_snapshot_safely("snap-123", "us-east-1")

                assert result is True
                mock_ec2.delete_snapshot.assert_called_once_with(SnapshotId="snap-123")
                captured = capsys.readouterr()
                assert "Successfully deleted" in captured.out
                assert "Monthly savings: $5.00" in captured.out

    def test_delete_snapshot_no_details(self):
        """Test deletion when snapshot details not available."""
        with patch("boto3.client"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.get_snapshot_details",
                return_value=None,
            ):
                result = delete_snapshot_safely("snap-123", "us-east-1")

                assert result is False

    def test_delete_snapshot_error(self, capsys):
        """Test error during snapshot deletion."""
        with patch("boto3.client") as mock_client:
            with patch(
                "cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.get_snapshot_details"
            ) as mock_get:
                mock_ec2 = MagicMock()
                mock_ec2.delete_snapshot.side_effect = ClientError(
                    {"Error": {"Code": "ServiceError"}}, "delete_snapshot"
                )
                mock_client.return_value = mock_ec2

                mock_get.return_value = {
                    "snapshot_id": "snap-123",
                    "size_gb": 100,
                    "state": "completed",
                    "start_time": "2024-01-01",
                    "description": "Test",
                }

                result = delete_snapshot_safely("snap-123", "us-east-1")

                assert result is False
                captured = capsys.readouterr()
                assert "Error deleting snapshot" in captured.out


def test_get_bulk_deletion_snapshots_returns_list_of_snapshots():
    """Test that function returns expected list."""
    snapshots = get_bulk_deletion_snapshots()

    assert isinstance(snapshots, list)
    assert len(snapshots) > 0
    assert all(snap.startswith("snap-") for snap in snapshots)


def test_print_bulk_deletion_warning_print_warning(capsys):
    """Test printing bulk deletion warning."""
    snapshots = ["snap-1", "snap-2", "snap-3"]

    print_bulk_deletion_warning(snapshots)

    captured = capsys.readouterr()
    assert "Bulk Deletion" in captured.out
    assert "3 snapshots" in captured.out
    assert "WARNING" in captured.out


class TestConfirmBulkDeletion:
    """Tests for confirm_bulk_deletion function."""

    def test_confirm_with_correct_input(self):
        """Test confirmation with correct input."""
        with patch("builtins.input", return_value="DELETE ALL SNAPSHOTS"):
            result = confirm_bulk_deletion()

            assert result is True

    def test_confirm_with_wrong_input(self):
        """Test confirmation with wrong input."""
        with patch("builtins.input", return_value="delete"):
            result = confirm_bulk_deletion()

            assert result is False


class TestProcessBulkDeletions:
    """Tests for process_bulk_deletions function."""

    def test_process_all_successful(self):
        """Test processing with all deletions successful."""
        snapshots = ["snap-1", "snap-2"]

        with patch(
            "cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.find_snapshot_region",
            return_value="us-east-1",
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.get_snapshot_details"
            ) as mock_get:
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.delete_snapshot_safely",
                    return_value=True,
                ):
                    mock_get.return_value = {"size_gb": 100}

                    successful, failed, savings = process_bulk_deletions(snapshots)

        assert successful == 2
        assert failed == 0
        assert savings == 10.0  # 2 * 100 * 0.05

    def test_process_snapshot_not_found(self, capsys):
        """Test processing when snapshot not found."""
        snapshots = ["snap-notfound"]

        with patch(
            "cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.find_snapshot_region",
            return_value=None,
        ):
            successful, failed, savings = process_bulk_deletions(snapshots)

        assert successful == 0
        assert failed == 1
        assert savings == 0
        captured = capsys.readouterr()
        assert "not found in any region" in captured.out

    def test_process_partial_failures(self):
        """Test processing with some failures."""
        snapshots = ["snap-1", "snap-2", "snap-3"]

        with patch(
            "cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.find_snapshot_region",
            return_value="us-east-1",
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.get_snapshot_details"
            ) as mock_get:
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.delete_snapshot_safely",
                    side_effect=[True, False, True],
                ):
                    mock_get.return_value = {"size_gb": 50}

                    successful, failed, _ = process_bulk_deletions(snapshots)

        assert successful == 2
        assert failed == 1


class TestPrintBulkDeletionSummary:
    """Tests for print_bulk_deletion_summary function."""

    def test_print_summary_with_deletions(self, capsys):
        """Test summary with successful deletions."""
        print_bulk_deletion_summary(10, 2, 150.0)

        captured = capsys.readouterr()
        assert "BULK DELETION SUMMARY" in captured.out
        assert "Successfully deleted: 10" in captured.out
        assert "Failed to delete: 2" in captured.out
        assert "$150.00" in captured.out
        assert "cleanup completed successfully" in captured.out

    def test_print_summary_no_failures(self, capsys):
        """Test summary with no failures."""
        print_bulk_deletion_summary(5, 0, 75.0)

        captured = capsys.readouterr()
        assert "Successfully deleted: 5" in captured.out
        assert "Failed to delete" not in captured.out

    def test_print_summary_no_deletions(self, capsys):
        """Test summary with no successful deletions."""
        print_bulk_deletion_summary(0, 5, 0.0)

        captured = capsys.readouterr()
        assert "Successfully deleted: 0" in captured.out
        assert "cleanup completed successfully" not in captured.out


class TestMain:
    """Tests for main function."""

    def test_main_cancelled(self, capsys):
        """Test main when user cancels."""
        with patch("cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.setup_aws_credentials"):
            with patch("builtins.input", return_value="NO"):
                main()

        captured = capsys.readouterr()
        assert "Deletion cancelled" in captured.out

    def test_main_success(self, capsys):
        """Test main with successful deletions."""
        with patch("cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.setup_aws_credentials"):
            with patch("builtins.input", return_value="DELETE ALL SNAPSHOTS"):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_snapshot_bulk_delete.process_bulk_deletions",
                    return_value=(5, 0, 50.0),
                ):
                    main()

        captured = capsys.readouterr()
        assert "Proceeding with bulk snapshot deletion" in captured.out
        assert "BULK DELETION SUMMARY" in captured.out
