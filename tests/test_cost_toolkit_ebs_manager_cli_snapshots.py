"""Tests for cost_toolkit/scripts/management/ebs_manager/cli.py - Snapshot operations and main."""

# pylint: disable=unused-argument

from __future__ import annotations

from unittest.mock import patch

import pytest

from cost_toolkit.scripts.management.ebs_manager.cli import (
    create_multiple_snapshots,
    handle_snapshot_command,
    main,
)
from tests.assertions import assert_equal


# Test create_multiple_snapshots function
@patch("cost_toolkit.scripts.management.ebs_manager.cli.create_volume_snapshot")
def test_create_multiple_snapshots_single_volume(mock_create_snapshot, capsys):
    """Test create_multiple_snapshots with single volume."""
    snapshot_info = {
        "snapshot_id": "snap-abc123",
        "volume_id": "vol-123",
        "volume_name": "test-volume",
        "volume_size": 100,
        "region": "us-east-1",
    }
    mock_create_snapshot.return_value = snapshot_info

    result = create_multiple_snapshots(["vol-123"])

    assert_equal(len(result), 1)
    assert_equal(result[0], snapshot_info)
    mock_create_snapshot.assert_called_once_with("vol-123")

    captured = capsys.readouterr()
    assert "Creating snapshot for volume vol-123..." in captured.out
    assert "Snapshot snap-abc123 created successfully" in captured.out
    assert "Volume: test-volume (100 GB)" in captured.out
    assert "Region: us-east-1" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.create_volume_snapshot")
def test_create_multiple_snapshots_multiple_volumes(mock_create_snapshot, capsys):
    """Test create_multiple_snapshots with multiple volumes."""
    snapshot_info_1 = {
        "snapshot_id": "snap-111",
        "volume_id": "vol-111",
        "volume_name": "volume-1",
        "volume_size": 50,
        "region": "us-east-1",
    }
    snapshot_info_2 = {
        "snapshot_id": "snap-222",
        "volume_id": "vol-222",
        "volume_name": "volume-2",
        "volume_size": 100,
        "region": "us-west-2",
    }

    mock_create_snapshot.side_effect = [snapshot_info_1, snapshot_info_2]

    result = create_multiple_snapshots(["vol-111", "vol-222"])

    assert_equal(len(result), 2)
    assert_equal(result[0], snapshot_info_1)
    assert_equal(result[1], snapshot_info_2)
    assert_equal(mock_create_snapshot.call_count, 2)


@patch("cost_toolkit.scripts.management.ebs_manager.cli.create_volume_snapshot")
def test_create_multiple_snapshots_with_errors(mock_create_snapshot, capsys):
    """Test create_multiple_snapshots handles errors gracefully."""
    snapshot_info = {
        "snapshot_id": "snap-good",
        "volume_id": "vol-good",
        "volume_name": "good-volume",
        "volume_size": 75,
        "region": "us-east-1",
    }

    mock_create_snapshot.side_effect = [
        snapshot_info,
        OSError("Volume not found"),
        ValueError("Rate limit exceeded"),
    ]

    result = create_multiple_snapshots(["vol-good", "vol-bad", "vol-ugly"])

    assert_equal(len(result), 1)
    assert_equal(result[0], snapshot_info)

    captured = capsys.readouterr()
    assert "Snapshot snap-good created successfully" in captured.out
    assert "Error creating snapshot for vol-bad: Volume not found" in captured.out
    assert "Error creating snapshot for vol-ugly: Rate limit exceeded" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.create_volume_snapshot")
def test_create_multiple_snapshots_empty_list(mock_create_snapshot, capsys):
    """Test create_multiple_snapshots with empty volume list."""
    result = create_multiple_snapshots([])

    assert_equal(len(result), 0)
    mock_create_snapshot.assert_not_called()


@patch("cost_toolkit.scripts.management.ebs_manager.cli.create_volume_snapshot")
def test_create_multiple_snapshots_all_fail(mock_create_snapshot, capsys):
    """Test create_multiple_snapshots when all volumes fail."""
    mock_create_snapshot.side_effect = [
        OSError("Error 1"),
        ValueError("Error 2"),
        OSError("Error 3"),
    ]

    result = create_multiple_snapshots(["vol-1", "vol-2", "vol-3"])

    assert_equal(len(result), 0)
    assert_equal(mock_create_snapshot.call_count, 3)

    captured = capsys.readouterr()
    assert "Error creating snapshot for vol-1: Error 1" in captured.out
    assert "Error creating snapshot for vol-2: Error 2" in captured.out
    assert "Error creating snapshot for vol-3: Error 3" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.create_volume_snapshot")
def test_create_multiple_snapshots_partial_success(mock_create_snapshot, capsys):
    """Test create_multiple_snapshots with mix of success and failure."""
    success_1 = {
        "snapshot_id": "snap-1",
        "volume_id": "vol-1",
        "volume_name": "vol1",
        "volume_size": 50,
        "region": "us-east-1",
    }
    success_2 = {
        "snapshot_id": "snap-3",
        "volume_id": "vol-3",
        "volume_name": "vol3",
        "volume_size": 150,
        "region": "eu-west-1",
    }

    mock_create_snapshot.side_effect = [success_1, OSError("Failed"), success_2]

    result = create_multiple_snapshots(["vol-1", "vol-2", "vol-3"])

    assert_equal(len(result), 2)
    assert_equal(result[0], success_1)
    assert_equal(result[1], success_2)

    captured = capsys.readouterr()
    assert "Snapshot snap-1 created successfully" in captured.out
    assert "Error creating snapshot for vol-2: Failed" in captured.out
    assert "Snapshot snap-3 created successfully" in captured.out


# Test handle_snapshot_command function
@patch("sys.argv", ["script.py", "snapshot"])
def test_handle_snapshot_command_missing_volume_id(capsys):
    """Test handle_snapshot_command exits when no volume IDs provided."""
    with pytest.raises(SystemExit) as exc_info:
        handle_snapshot_command()

    assert_equal(exc_info.value.code, 1)
    captured = capsys.readouterr()
    assert "At least one volume ID required for snapshot command" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.print_snapshot_summary")
@patch("cost_toolkit.scripts.management.ebs_manager.cli.create_multiple_snapshots")
@patch("sys.argv", ["script.py", "snapshot", "vol-123"])
def test_handle_snapshot_command_single_volume(mock_create_snapshots, mock_print_summary, capsys):
    """Test handle_snapshot_command with single volume."""
    snapshot_info = {
        "snapshot_id": "snap-123",
        "volume_id": "vol-123",
        "volume_name": "test-vol",
        "volume_size": 100,
        "region": "us-east-1",
    }
    mock_create_snapshots.return_value = [snapshot_info]

    handle_snapshot_command()

    mock_create_snapshots.assert_called_once_with(["vol-123"])
    mock_print_summary.assert_called_once_with([snapshot_info])

    captured = capsys.readouterr()
    assert "AWS EBS Volume Snapshot Creation" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.print_snapshot_summary")
@patch("cost_toolkit.scripts.management.ebs_manager.cli.create_multiple_snapshots")
@patch("sys.argv", ["script.py", "snapshot", "vol-111", "vol-222", "vol-333"])
def test_handle_snapshot_command_multiple_volumes(mock_create_snapshots, mock_print_summary, capsys):
    """Test handle_snapshot_command with multiple volumes."""
    snapshots = [
        {"snapshot_id": "snap-111", "volume_size": 50},
        {"snapshot_id": "snap-222", "volume_size": 100},
        {"snapshot_id": "snap-333", "volume_size": 200},
    ]
    mock_create_snapshots.return_value = snapshots

    handle_snapshot_command()

    mock_create_snapshots.assert_called_once_with(["vol-111", "vol-222", "vol-333"])
    mock_print_summary.assert_called_once_with(snapshots)


@patch("cost_toolkit.scripts.management.ebs_manager.cli.print_snapshot_summary")
@patch("cost_toolkit.scripts.management.ebs_manager.cli.create_multiple_snapshots")
@patch("sys.argv", ["script.py", "snapshot", "vol-fail"])
def test_handle_snapshot_command_no_snapshots_created(mock_create_snapshots, mock_print_summary, capsys):
    """Test handle_snapshot_command when no snapshots are created."""
    mock_create_snapshots.return_value = []

    handle_snapshot_command()

    mock_create_snapshots.assert_called_once_with(["vol-fail"])
    mock_print_summary.assert_not_called()

    captured = capsys.readouterr()
    assert "AWS EBS Volume Snapshot Creation" in captured.out


# Test main function
@patch("sys.argv", ["script.py"])
def test_main_no_arguments(capsys):
    """Test main function exits when no arguments provided."""
    with pytest.raises(SystemExit) as exc_info:
        main()

    assert_equal(exc_info.value.code, 1)
    captured = capsys.readouterr()
    assert "AWS EBS Volume Manager" in captured.out
    assert "Usage:" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.handle_delete_command")
@patch("cost_toolkit.scripts.management.ebs_manager.cli.setup_aws_credentials")
@patch("sys.argv", ["script.py", "delete", "vol-123"])
def test_main_delete_command(mock_setup_creds, mock_handle_delete):
    """Test main function routes to delete command handler."""
    mock_handle_delete.side_effect = SystemExit(0)

    with pytest.raises(SystemExit):
        main()

    mock_setup_creds.assert_called_once()
    mock_handle_delete.assert_called_once()


@patch("cost_toolkit.scripts.management.ebs_manager.cli.handle_info_command")
@patch("cost_toolkit.scripts.management.ebs_manager.cli.setup_aws_credentials")
@patch("sys.argv", ["script.py", "info", "vol-123"])
def test_main_info_command(mock_setup_creds, mock_handle_info):
    """Test main function routes to info command handler."""
    main()

    mock_setup_creds.assert_called_once()
    mock_handle_info.assert_called_once()


@patch("cost_toolkit.scripts.management.ebs_manager.cli.handle_snapshot_command")
@patch("cost_toolkit.scripts.management.ebs_manager.cli.setup_aws_credentials")
@patch("sys.argv", ["script.py", "snapshot", "vol-123"])
def test_main_snapshot_command(mock_setup_creds, mock_handle_snapshot):
    """Test main function routes to snapshot command handler."""
    main()

    mock_setup_creds.assert_called_once()
    mock_handle_snapshot.assert_called_once()


@patch("cost_toolkit.scripts.management.ebs_manager.cli.setup_aws_credentials")
@patch("sys.argv", ["script.py", "DELETE", "vol-123"])
def test_main_delete_command_uppercase(mock_setup_creds):
    """Test main function handles DELETE command (case-insensitive)."""
    with patch("cost_toolkit.scripts.management.ebs_manager.cli.handle_delete_command") as mock_handle:
        mock_handle.side_effect = SystemExit(0)

        with pytest.raises(SystemExit):
            main()

        mock_setup_creds.assert_called_once()
        mock_handle.assert_called_once()


@patch("cost_toolkit.scripts.management.ebs_manager.cli.setup_aws_credentials")
@patch("sys.argv", ["script.py", "INFO", "vol-123"])
def test_main_info_command_uppercase(mock_setup_creds):
    """Test main function handles INFO command (case-insensitive)."""
    with patch("cost_toolkit.scripts.management.ebs_manager.cli.handle_info_command") as mock_handle:
        main()

        mock_setup_creds.assert_called_once()
        mock_handle.assert_called_once()


@patch("cost_toolkit.scripts.management.ebs_manager.cli.setup_aws_credentials")
@patch("sys.argv", ["script.py", "SnApShOt", "vol-123"])
def test_main_snapshot_command_mixed_case(mock_setup_creds):
    """Test main function handles SNAPSHOT command (case-insensitive)."""
    with patch("cost_toolkit.scripts.management.ebs_manager.cli.handle_snapshot_command") as mock_handle:
        main()

        mock_setup_creds.assert_called_once()
        mock_handle.assert_called_once()


@patch("cost_toolkit.scripts.management.ebs_manager.cli.setup_aws_credentials")
@patch("sys.argv", ["script.py", "invalid-command"])
def test_main_unknown_command(mock_setup_creds, capsys):
    """Test main function handles unknown commands."""
    with pytest.raises(SystemExit) as exc_info:
        main()

    assert_equal(exc_info.value.code, 1)
    mock_setup_creds.assert_called_once()

    captured = capsys.readouterr()
    assert "Unknown command: invalid-command" in captured.out
    assert "Valid commands: delete, info, snapshot" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.setup_aws_credentials")
@patch("sys.argv", ["script.py", "status"])
def test_main_invalid_command(mock_setup_creds, capsys):
    """Test main function with invalid command."""
    with pytest.raises(SystemExit) as exc_info:
        main()

    assert_equal(exc_info.value.code, 1)
    captured = capsys.readouterr()
    assert "Unknown command: status" in captured.out
