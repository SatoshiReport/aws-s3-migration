"""Tests for cost_toolkit/scripts/optimization/snapshot_export_fixed/cli.py - Part 3"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.snapshot_export_fixed.cli import (
    export_snapshots_to_s3_fixed,
    main,
)
from cost_toolkit.scripts.optimization.snapshot_export_fixed.constants import (
    ExportTaskDeletedException,
    ExportTaskFailedException,
    ExportTaskStuckException,
)
from tests.assertions import assert_equal


# Tests for export_snapshots_to_s3_fixed (continued)
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.export_single_snapshot_to_s3")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.calculate_cost_savings")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.get_snapshots_to_export")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.load_aws_credentials")
@patch("builtins.input", return_value="EXPORT TO S3")
@patch("builtins.print")
def test_export_snapshots_to_s3_fixed_handles_export_task_deleted(
    _mock_print,
    _mock_input,
    mock_load_creds,
    mock_get_snapshots,
    mock_calculate_savings,
    mock_export_single,
):
    """Test export_snapshots_to_s3_fixed continues when export task is deleted."""
    mock_load_creds.return_value = ("access_key", "secret_key")
    mock_get_snapshots.return_value = [
        {"snapshot_id": "snap-1", "region": "us-east-1", "size_gb": 50, "description": "Test 1"},
        {"snapshot_id": "snap-2", "region": "us-west-2", "size_gb": 30, "description": "Test 2"},
    ]
    mock_calculate_savings.return_value = {
        "monthly_savings": 5.00,
        "annual_savings": 60.00,
        "ebs_cost": 4.00,
        "s3_cost": 1.84,
        "savings_percentage": 54.0,
    }
    mock_export_single.side_effect = [
        ExportTaskDeletedException("Export deleted"),
        {
            "snapshot_id": "snap-2",
            "success": True,
            "monthly_savings": 0.81,
            "bucket_name": "test-bucket",
            "s3_key": "exports/test.vmdk",
        },
    ]

    export_snapshots_to_s3_fixed()

    assert_equal(mock_export_single.call_count, 2)


@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.export_single_snapshot_to_s3")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.calculate_cost_savings")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.get_snapshots_to_export")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.load_aws_credentials")
@patch("builtins.input", return_value="EXPORT TO S3")
@patch("builtins.print")
def test_export_snapshots_to_s3_fixed_handles_export_task_stuck(
    _mock_print,
    _mock_input,
    mock_load_creds,
    mock_get_snapshots,
    mock_calculate_savings,
    mock_export_single,
):
    """Test export_snapshots_to_s3_fixed continues when export task is stuck."""
    mock_load_creds.return_value = ("access_key", "secret_key")
    mock_get_snapshots.return_value = [
        {"snapshot_id": "snap-1", "region": "us-east-1", "size_gb": 50, "description": "Test 1"},
        {"snapshot_id": "snap-2", "region": "us-west-2", "size_gb": 30, "description": "Test 2"},
    ]
    mock_calculate_savings.return_value = {
        "monthly_savings": 5.00,
        "annual_savings": 60.00,
        "ebs_cost": 4.00,
        "s3_cost": 1.84,
        "savings_percentage": 54.0,
    }
    mock_export_single.side_effect = [
        ExportTaskStuckException("Export stuck"),
        {
            "snapshot_id": "snap-2",
            "success": True,
            "monthly_savings": 0.81,
            "bucket_name": "test-bucket",
            "s3_key": "exports/test.vmdk",
        },
    ]

    export_snapshots_to_s3_fixed()

    assert_equal(mock_export_single.call_count, 2)


@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.export_single_snapshot_to_s3")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.calculate_cost_savings")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.get_snapshots_to_export")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.load_aws_credentials")
@patch("builtins.input", return_value="EXPORT TO S3")
@patch("builtins.print")
def test_export_snapshots_to_s3_fixed_fails_on_client_error(
    _mock_print,
    _mock_input,
    mock_load_creds,
    mock_get_snapshots,
    mock_calculate_savings,
    mock_export_single,
):
    """Test export_snapshots_to_s3_fixed fails on client error."""
    mock_load_creds.return_value = ("access_key", "secret_key")
    mock_get_snapshots.return_value = [
        {"snapshot_id": "snap-1", "region": "us-east-1", "size_gb": 50, "description": "Test 1"}
    ]
    mock_calculate_savings.return_value = {
        "monthly_savings": 5.00,
        "annual_savings": 60.00,
        "ebs_cost": 2.50,
        "s3_cost": 1.15,
        "savings_percentage": 54.0,
    }
    mock_export_single.side_effect = ClientError(
        {"Error": {"Code": "InternalError"}}, "ExportImage"
    )

    with pytest.raises(ExportTaskFailedException):
        export_snapshots_to_s3_fixed()


@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.export_single_snapshot_to_s3")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.calculate_cost_savings")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.get_snapshots_to_export")
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.load_aws_credentials")
@patch("builtins.input", return_value="EXPORT TO S3")
@patch("builtins.print")
def test_export_snapshots_to_s3_fixed_sorts_by_size(
    mock_print,  # pylint: disable=unused-argument
    _mock_input,
    mock_load_creds,
    mock_get_snapshots,
    mock_calculate_savings,
    mock_export_single,
):
    """Test export_snapshots_to_s3_fixed sorts snapshots by size."""
    mock_load_creds.return_value = ("access_key", "secret_key")
    mock_get_snapshots.return_value = [
        {
            "snapshot_id": "snap-large",
            "region": "us-east-1",
            "size_gb": 100,
            "description": "Large",
        },
        {"snapshot_id": "snap-small", "region": "us-west-2", "size_gb": 10, "description": "Small"},
        {
            "snapshot_id": "snap-medium",
            "region": "eu-west-1",
            "size_gb": 50,
            "description": "Medium",
        },
    ]
    mock_calculate_savings.return_value = {
        "monthly_savings": 5.00,
        "annual_savings": 60.00,
        "ebs_cost": 8.00,
        "s3_cost": 3.68,
        "savings_percentage": 54.0,
    }
    mock_export_single.side_effect = [
        {
            "snapshot_id": "snap-small",
            "success": True,
            "monthly_savings": 0.27,
            "bucket_name": "test-bucket",
            "s3_key": "exports/test.vmdk",
        },
        {
            "snapshot_id": "snap-medium",
            "success": True,
            "monthly_savings": 1.35,
            "bucket_name": "test-bucket",
            "s3_key": "exports/test.vmdk",
        },
        {
            "snapshot_id": "snap-large",
            "success": True,
            "monthly_savings": 2.70,
            "bucket_name": "test-bucket",
            "s3_key": "exports/test.vmdk",
        },
    ]

    export_snapshots_to_s3_fixed()

    calls = mock_export_single.call_args_list
    assert_equal(calls[0][0][0]["snapshot_id"], "snap-small")
    assert_equal(calls[1][0][0]["snapshot_id"], "snap-medium")
    assert_equal(calls[2][0][0]["snapshot_id"], "snap-large")


# Tests for main
@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.export_snapshots_to_s3_fixed")
def test_main(mock_export):
    """Test main function parses args and calls export."""
    with patch("sys.argv", ["cli.py"]):
        main()

    mock_export.assert_called_once()


@patch("cost_toolkit.scripts.optimization.snapshot_export_fixed.cli.export_snapshots_to_s3_fixed")
def test_main_with_help_arg(mock_export):
    """Test main function with help argument."""
    with patch("sys.argv", ["cli.py", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert_equal(exc_info.value.code, 0)

    mock_export.assert_not_called()
