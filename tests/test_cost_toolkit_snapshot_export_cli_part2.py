"""Tests for cost_toolkit/scripts/optimization/snapshot_export_fixed/cli.py - Part 2"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.snapshot_export_fixed.cli import (
    _print_export_intro_fixed,
    _print_final_summary_fixed,
    export_single_snapshot_to_s3,
    export_snapshots_to_s3_fixed,
)
from cost_toolkit.scripts.optimization.snapshot_export_fixed.constants import (
    ExportTaskDeletedException,
)
from tests.assertions import assert_equal


# Additional tests for export_single_snapshot_to_s3
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.cleanup_temporary_ami")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.export_ami_to_s3_with_recovery")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.create_ami_from_snapshot")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli._setup_s3_bucket_for_export")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli._setup_aws_clients")
@patch("builtins.print")
def test_export_single_snapshot_to_s3_cleanup_failure_prints_warning(  # pylint: disable=too-many-positional-arguments
    mock_print,
    mock_setup_clients,
    mock_setup_bucket,
    mock_create_ami,
    mock_export_ami,
    mock_cleanup_ami,
):
    """Test export_single_snapshot_to_s3 prints warning when cleanup fails."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()
    mock_setup_clients.return_value = (mock_ec2, mock_s3)
    mock_setup_bucket.return_value = "test-bucket"
    mock_create_ami.return_value = "ami-123"
    mock_export_ami.side_effect = ExportTaskDeletedException("Export was deleted")
    mock_cleanup_ami.side_effect = ClientError(
        {"Error": {"Code": "InvalidAMIID.NotFound"}}, "DeregisterImage"
    )

    snapshot_info = {
        "snapshot_id": "snap-789",
        "region": "us-east-1",
        "size_gb": 50,
        "description": "Test snapshot",
    }

    with pytest.raises(ExportTaskDeletedException):
        export_single_snapshot_to_s3(snapshot_info, "access_key", "secret_key")

    warning_printed = any(
        "⚠️" in str(call_args) and "ami-123" in str(call_args)
        for call_args in mock_print.call_args_list
    )
    assert warning_printed, "Expected warning message about AMI cleanup failure"


@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.cleanup_temporary_ami")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.export_ami_to_s3_with_recovery")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.create_ami_from_snapshot")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli._setup_s3_bucket_for_export")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli._setup_aws_clients")
@patch("builtins.print")
def test_export_single_snapshot_to_s3_client_error_cleanup_failure(  # pylint: disable=too-many-positional-arguments
    mock_print,
    mock_setup_clients,
    mock_setup_bucket,
    mock_create_ami,
    mock_export_ami,
    mock_cleanup_ami,
):
    """Test export_single_snapshot_to_s3 handles cleanup failure on generic ClientError."""
    mock_ec2 = MagicMock()
    mock_s3 = MagicMock()
    mock_setup_clients.return_value = (mock_ec2, mock_s3)
    mock_setup_bucket.return_value = "test-bucket"
    mock_create_ami.return_value = "ami-cleanup-fail"
    mock_export_ami.side_effect = ClientError(
        {"Error": {"Code": "ServiceUnavailable"}}, "ExportImage"
    )
    mock_cleanup_ami.side_effect = ClientError(
        {"Error": {"Code": "RequestLimitExceeded"}}, "DeregisterImage"
    )

    snapshot_info = {
        "snapshot_id": "snap-cleanup-test",
        "region": "eu-west-1",
        "size_gb": 75,
        "description": "Cleanup failure test",
    }

    with pytest.raises(ClientError):
        export_single_snapshot_to_s3(snapshot_info, "access_key", "secret_key")

    warning_printed = any(
        "⚠️" in str(call_args) and "ami-cleanup-fail" in str(call_args)
        for call_args in mock_print.call_args_list
    )
    assert warning_printed, "Expected warning message about AMI cleanup failure"


# Tests for _print_export_intro_fixed
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.print_export_summary")
@patch("builtins.print")
def test_print_export_intro_fixed(mock_print, mock_print_summary):
    """Test _print_export_intro_fixed prints correct information."""
    snapshots = [
        {"snapshot_id": "snap-1", "size_gb": 10},
        {"snapshot_id": "snap-2", "size_gb": 20},
    ]
    savings = {"monthly_savings": 5.00, "annual_savings": 60.00}

    _print_export_intro_fixed(snapshots, savings)

    mock_print_summary.assert_called_once_with(snapshots, savings)
    assert mock_print.call_count >= 5


# Tests for _print_final_summary_fixed
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.print_export_results")
@patch("builtins.print")
def test_print_final_summary_fixed_with_results(mock_print, mock_print_results):
    """Test _print_final_summary_fixed with successful exports."""
    export_results = [
        {
            "snapshot_id": "snap-1",
            "bucket_name": "bucket-1",
            "s3_key": "exports/snap-1.vmdk",
            "monthly_savings": 2.50,
        },
        {
            "snapshot_id": "snap-2",
            "bucket_name": "bucket-2",
            "s3_key": "exports/snap-2.vmdk",
            "monthly_savings": 3.00,
        },
    ]
    snapshots = [
        {"snapshot_id": "snap-1", "region": "us-east-1", "size_gb": 50},
        {"snapshot_id": "snap-2", "region": "us-west-2", "size_gb": 60},
    ]

    _print_final_summary_fixed(2, export_results, snapshots)

    mock_print_results.assert_called_once_with(export_results)
    delete_commands_printed = any(
        "delete-snapshot" in str(call_args) for call_args in mock_print.call_args_list
    )
    assert delete_commands_printed, "Expected delete-snapshot commands to be printed"


@patch("builtins.print")
def test_print_final_summary_fixed_no_results(_mock_print):
    """Test _print_final_summary_fixed with no results."""
    _print_final_summary_fixed(0, [], [])


# Tests for export_snapshots_to_s3_fixed
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.export_single_snapshot_to_s3")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.calculate_cost_savings")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.get_snapshots_to_export")
@patch("cost_toolkit.common.credential_utils.setup_aws_credentials")
@patch("builtins.input", return_value="EXPORT TO S3")
@patch("builtins.print")
def test_export_snapshots_to_s3_fixed_success(
    _mock_print,
    _mock_input,
    mock_load_creds,
    mock_get_snapshots,
    mock_calculate_savings,
    mock_export_single,
):
    """Test export_snapshots_to_s3_fixed with successful exports."""
    mock_load_creds.return_value = ("access_key", "secret_key")
    mock_get_snapshots.return_value = [
        {"snapshot_id": "snap-1", "region": "us-east-1", "size_gb": 50, "description": "Test 1"},
        {"snapshot_id": "snap-2", "region": "us-west-2", "size_gb": 30, "description": "Test 2"},
    ]
    mock_calculate_savings.side_effect = [
        {
            "monthly_savings": 5.00,
            "annual_savings": 60.00,
            "ebs_cost": 4.00,
            "s3_cost": 1.84,
            "savings_percentage": 54.0,
        },
        {
            "monthly_savings": 1.35,
            "annual_savings": 16.20,
            "ebs_cost": 2.50,
            "s3_cost": 1.15,
            "savings_percentage": 54.0,
        },
        {
            "monthly_savings": 0.81,
            "annual_savings": 9.72,
            "ebs_cost": 1.50,
            "s3_cost": 0.69,
            "savings_percentage": 54.0,
        },
    ]
    mock_export_single.side_effect = [
        {
            "snapshot_id": "snap-2",
            "success": True,
            "monthly_savings": 0.81,
            "s3_key": "key2",
            "bucket_name": "bucket2",
        },
        {
            "snapshot_id": "snap-1",
            "success": True,
            "monthly_savings": 1.35,
            "s3_key": "key1",
            "bucket_name": "bucket1",
        },
    ]

    export_snapshots_to_s3_fixed()

    assert_equal(mock_export_single.call_count, 2)
    first_call = mock_export_single.call_args_list[0][0][0]
    assert_equal(first_call["snapshot_id"], "snap-2")


@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.get_snapshots_to_export")
@patch("cost_toolkit.common.credential_utils.setup_aws_credentials")
@patch("builtins.input", return_value="NO")
@patch("builtins.print")
def test_export_snapshots_to_s3_fixed_cancelled(
    _mock_print, _mock_input, mock_load_creds, mock_get_snapshots
):
    """Test export_snapshots_to_s3_fixed when user cancels."""
    mock_load_creds.return_value = ("access_key", "secret_key")
    mock_get_snapshots.return_value = [
        {"snapshot_id": "snap-1", "region": "us-east-1", "size_gb": 50, "description": "Test 1"}
    ]

    with pytest.raises(ValueError, match="Operation cancelled by user"):
        export_snapshots_to_s3_fixed()
