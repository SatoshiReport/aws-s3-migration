"""Tests for cost_toolkit/scripts/management/ebs_manager/cli.py - Command handlers."""

# pylint: disable=unused-argument

from __future__ import annotations

from unittest.mock import patch

import pytest

from cost_toolkit.scripts.management.ebs_manager.cli import (
    MIN_ARGS_FOR_COMMAND,
    MIN_ARGS_WITH_VOLUME_ID,
    handle_delete_command,
    handle_info_command,
    print_usage,
)
from tests.assertions import assert_equal


# Test print_usage function
def test_print_usage(capsys):
    """Test print_usage outputs correct usage information."""
    print_usage()

    captured = capsys.readouterr()
    assert "AWS EBS Volume Manager" in captured.out
    assert "Delete volume:" in captured.out
    assert "Get volume info:" in captured.out
    assert "Create snapshot:" in captured.out
    assert "Force delete:" in captured.out
    assert "Examples:" in captured.out


# Test handle_delete_command function
@patch("sys.argv", ["script.py", "delete"])
def test_handle_delete_command_missing_volume_id(capsys):
    """Test handle_delete_command exits when volume ID is missing."""
    with pytest.raises(SystemExit) as exc_info:
        handle_delete_command()

    assert_equal(exc_info.value.code, 1)
    captured = capsys.readouterr()
    assert "Volume ID required for delete command" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.delete_ebs_volume")
@patch("sys.argv", ["script.py", "delete", "vol-123"])
def test_handle_delete_command_success(mock_delete, capsys):
    """Test handle_delete_command with successful deletion."""
    mock_delete.return_value = True

    with pytest.raises(SystemExit) as exc_info:
        handle_delete_command()

    assert_equal(exc_info.value.code, 0)
    mock_delete.assert_called_once_with("vol-123", False)
    captured = capsys.readouterr()
    assert "AWS EBS Volume Deletion" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.delete_ebs_volume")
@patch("sys.argv", ["script.py", "delete", "vol-123", "--force"])
def test_handle_delete_command_with_force(mock_delete, capsys):
    """Test handle_delete_command with force flag."""
    mock_delete.return_value = True

    with pytest.raises(SystemExit) as exc_info:
        handle_delete_command()

    assert_equal(exc_info.value.code, 0)
    mock_delete.assert_called_once_with("vol-123", True)
    captured = capsys.readouterr()
    assert "AWS EBS Volume Deletion" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.delete_ebs_volume")
@patch("sys.argv", ["script.py", "delete", "vol-456"])
def test_handle_delete_command_failure(mock_delete, capsys):
    """Test handle_delete_command with failed deletion."""
    mock_delete.return_value = False

    with pytest.raises(SystemExit) as exc_info:
        handle_delete_command()

    assert_equal(exc_info.value.code, 1)
    mock_delete.assert_called_once_with("vol-456", False)


@patch("cost_toolkit.scripts.management.ebs_manager.cli.delete_ebs_volume")
@patch("sys.argv", ["script.py", "delete", "vol-123", "--force", "--extra-arg"])
def test_handle_delete_command_extra_arguments(mock_delete, capsys):
    """Test handle_delete_command ignores extra arguments."""
    mock_delete.return_value = True

    with pytest.raises(SystemExit) as exc_info:
        handle_delete_command()

    assert_equal(exc_info.value.code, 0)
    mock_delete.assert_called_once_with("vol-123", True)


# Test handle_info_command function
@patch("sys.argv", ["script.py", "info"])
def test_handle_info_command_missing_volume_id(capsys):
    """Test handle_info_command exits when no volume IDs provided."""
    with pytest.raises(SystemExit) as exc_info:
        handle_info_command()

    assert_equal(exc_info.value.code, 1)
    captured = capsys.readouterr()
    assert "At least one volume ID required for info command" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.print_volume_detailed_report")
@patch("cost_toolkit.scripts.management.ebs_manager.cli.get_volume_detailed_info")
@patch("sys.argv", ["script.py", "info", "vol-abc123"])
def test_handle_info_command_single_volume(mock_get_info, mock_print_report, capsys):
    """Test handle_info_command with single volume."""
    volume_info = {
        "volume_id": "vol-abc123",
        "region": "us-east-1",
        "size_gb": 100,
        "volume_type": "gp3",
        "state": "available",
    }
    mock_get_info.return_value = volume_info

    handle_info_command()

    mock_get_info.assert_called_once_with("vol-abc123")
    mock_print_report.assert_called_once_with(volume_info)
    captured = capsys.readouterr()
    assert "AWS EBS Volume Detailed Information" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.print_volume_detailed_report")
@patch("cost_toolkit.scripts.management.ebs_manager.cli.get_volume_detailed_info")
@patch("sys.argv", ["script.py", "info", "vol-111", "vol-222", "vol-333"])
def test_handle_info_command_multiple_volumes(mock_get_info, mock_print_report, capsys):
    """Test handle_info_command with multiple volumes."""
    volume_info_1 = {"volume_id": "vol-111", "region": "us-east-1"}
    volume_info_2 = {"volume_id": "vol-222", "region": "us-west-2"}
    volume_info_3 = {"volume_id": "vol-333", "region": "eu-west-1"}

    mock_get_info.side_effect = [volume_info_1, volume_info_2, volume_info_3]

    handle_info_command()

    assert_equal(mock_get_info.call_count, 3)
    mock_get_info.assert_any_call("vol-111")
    mock_get_info.assert_any_call("vol-222")
    mock_get_info.assert_any_call("vol-333")

    assert_equal(mock_print_report.call_count, 3)
    mock_print_report.assert_any_call(volume_info_1)
    mock_print_report.assert_any_call(volume_info_2)
    mock_print_report.assert_any_call(volume_info_3)


@patch("cost_toolkit.scripts.management.ebs_manager.cli.print_volume_detailed_report")
@patch("cost_toolkit.scripts.management.ebs_manager.cli.get_volume_detailed_info")
@patch("sys.argv", ["script.py", "info", "vol-good", "vol-bad", "vol-ugly"])
def test_handle_info_command_with_errors(mock_get_info, mock_print_report, capsys):
    """Test handle_info_command handles errors gracefully."""
    volume_info = {"volume_id": "vol-good", "region": "us-east-1"}

    mock_get_info.side_effect = [
        volume_info,
        OSError("Volume not found"),
        ValueError("Invalid volume ID"),
    ]

    handle_info_command()

    assert_equal(mock_get_info.call_count, 3)
    mock_print_report.assert_called_once_with(volume_info)

    captured = capsys.readouterr()
    assert "Error getting info for vol-bad: Volume not found" in captured.out
    assert "Error getting info for vol-ugly: Invalid volume ID" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.get_volume_detailed_info")
@patch("sys.argv", ["script.py", "info", "vol-1", "vol-2", "vol-3"])
def test_handle_info_command_all_fail(mock_get_info, capsys):
    """Test handle_info_command when all volumes fail."""
    mock_get_info.side_effect = [
        OSError("Not found"),
        ValueError("Invalid"),
        OSError("Unknown error"),
    ]

    handle_info_command()

    assert_equal(mock_get_info.call_count, 3)

    captured = capsys.readouterr()
    assert "Error getting info for vol-1: Not found" in captured.out
    assert "Error getting info for vol-2: Invalid" in captured.out
    assert "Error getting info for vol-3: Unknown error" in captured.out


@patch("cost_toolkit.scripts.management.ebs_manager.cli.print_volume_detailed_report")
@patch("cost_toolkit.scripts.management.ebs_manager.cli.get_volume_detailed_info")
@patch(
    "sys.argv",
    [
        "script.py",
        "info",
        "vol-1",
        "vol-1",
        "vol-1",
        "vol-1",
        "vol-1",
        "vol-1",
        "vol-1",
        "vol-1",
        "vol-1",
        "vol-1",
    ],
)
def test_handle_info_command_many_volumes(mock_get_info, mock_print_report):
    """Test handle_info_command with many duplicate volume IDs."""
    volume_info = {"volume_id": "vol-1", "region": "us-east-1"}
    mock_get_info.return_value = volume_info

    handle_info_command()

    # Should be called once for each volume ID after the command (10 times)
    assert_equal(mock_get_info.call_count, 10)
    assert_equal(mock_print_report.call_count, 10)


# Test constants
def test_constants():
    """Test that command-line argument count constants have correct values."""
    assert_equal(MIN_ARGS_FOR_COMMAND, 2)
    assert_equal(MIN_ARGS_WITH_VOLUME_ID, 3)
