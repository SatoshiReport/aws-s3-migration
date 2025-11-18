"""Tests for the waiter helper wrappers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cost_toolkit.common import waiter_utils


@pytest.mark.parametrize(
    "function,args,waiter_name,expected_kwargs",
    [
        (
            waiter_utils.wait_instance_stopped,
            ("i-123",),
            "instance_stopped",
            {"InstanceIds": ["i-123"], "WaiterConfig": {"Delay": 15, "MaxAttempts": 40}},
        ),
        (
            waiter_utils.wait_instance_running,
            ("i-123",),
            "instance_running",
            {"InstanceIds": ["i-123"], "WaiterConfig": {"Delay": 15, "MaxAttempts": 40}},
        ),
        (
            waiter_utils.wait_instance_terminated,
            ("i-123",),
            "instance_terminated",
            {"InstanceIds": ["i-123"], "WaiterConfig": {"Delay": 15, "MaxAttempts": 40}},
        ),
        (
            waiter_utils.wait_volume_available,
            ("vol-123",),
            "volume_available",
            {"VolumeIds": ["vol-123"], "WaiterConfig": {"Delay": 15, "MaxAttempts": 40}},
        ),
        (
            waiter_utils.wait_ami_available,
            ("ami-123",),
            "image_available",
            {"ImageIds": ["ami-123"], "WaiterConfig": {"Delay": 15, "MaxAttempts": 40}},
        ),
        (
            waiter_utils.wait_rds_instance_available,
            ("db-123",),
            "db_instance_available",
            {
                "DBInstanceIdentifier": "db-123",
                "WaiterConfig": {"Delay": 30, "MaxAttempts": 60},
            },
        ),
        (
            waiter_utils.wait_rds_instance_deleted,
            ("db-123",),
            "db_instance_deleted",
            {
                "DBInstanceIdentifier": "db-123",
                "WaiterConfig": {"Delay": 30, "MaxAttempts": 60},
            },
        ),
        (
            waiter_utils.wait_rds_snapshot_completed,
            ("snap-123",),
            "db_snapshot_completed",
            {
                "DBSnapshotIdentifier": "snap-123",
                "WaiterConfig": {"Delay": 30, "MaxAttempts": 60},
            },
        ),
        (
            waiter_utils.wait_rds_cluster_available,
            ("cluster-123",),
            "db_cluster_available",
            {
                "DBClusterIdentifier": "cluster-123",
                "WaiterConfig": {"Delay": 30, "MaxAttempts": 60},
            },
        ),
        (
            waiter_utils.wait_route53_changes,
            ("change-123",),
            "resource_record_sets_changed",
            {"Id": "change-123", "WaiterConfig": {"Delay": 30, "MaxAttempts": 60}},
        ),
    ],
)
def test_waiter_wrappers(function, args, waiter_name, expected_kwargs):
    """Ensure each wrapper requests the correct waiter and arguments."""
    client = MagicMock()
    waiter = MagicMock()
    client.get_waiter.return_value = waiter

    function(client, *args)

    client.get_waiter.assert_called_once_with(waiter_name)
    waiter.wait.assert_called_once_with(**expected_kwargs)
