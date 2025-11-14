"""Tests for cost_toolkit/scripts/management/ebs_manager/reporting.py module."""

from __future__ import annotations

from cost_toolkit.scripts.management.ebs_manager.reporting import (
    print_snapshot_summary,
    print_volume_detailed_report,
)


def test_print_volume_detailed_report_basic(capsys):
    """Test print_volume_detailed_report with basic volume info."""
    volume_info = {
        "volume_id": "vol-123456",
        "region": "us-east-1",
        "volume_type": "gp3",
        "size_gb": 100,
        "state": "available",
        "create_time": "2024-01-01",
        "availability_zone": "us-east-1a",
        "encrypted": True,
        "iops": 3000,
        "throughput": 125,
        "attached_to_instance_id": None,
        "attached_to_instance_name": "Not attached",
        "device": None,
        "attach_time": None,
        "delete_on_termination": False,
        "tags": {},
        "last_read_activity": "Never",
    }

    print_volume_detailed_report(volume_info)

    captured = capsys.readouterr()
    assert "vol-123456" in captured.out
    assert "us-east-1" in captured.out
    assert "gp3" in captured.out
    assert "100 GB" in captured.out


def test_print_volume_detailed_report_attached(capsys):
    """Test print_volume_detailed_report with attached volume."""
    volume_info = {
        "volume_id": "vol-789012",
        "region": "us-west-2",
        "volume_type": "gp2",
        "size_gb": 50,
        "state": "in-use",
        "create_time": "2024-01-15",
        "availability_zone": "us-west-2b",
        "encrypted": False,
        "iops": "N/A",
        "throughput": "N/A",
        "attached_to_instance_id": "i-abcdef123456",
        "attached_to_instance_name": "WebServer",
        "device": "/dev/sda1",
        "attach_time": "2024-01-15 10:00:00",
        "delete_on_termination": True,
        "tags": {"Name": "RootVolume", "Environment": "Production"},
        "last_read_activity": "2024-01-20",
    }

    print_volume_detailed_report(volume_info)

    captured = capsys.readouterr()
    assert "vol-789012" in captured.out
    assert "i-abcdef123456" in captured.out
    assert "WebServer" in captured.out
    assert "/dev/sda1" in captured.out
    assert "Name: RootVolume" in captured.out


def test_print_volume_detailed_report_with_tags(capsys):
    """Test print_volume_detailed_report displays tags correctly."""
    volume_info = {
        "volume_id": "vol-with-tags",
        "region": "eu-west-1",
        "volume_type": "io1",
        "size_gb": 200,
        "state": "available",
        "create_time": "2024-02-01",
        "availability_zone": "eu-west-1a",
        "encrypted": True,
        "iops": 5000,
        "throughput": "N/A",
        "attached_to_instance_id": None,
        "attached_to_instance_name": "Not attached",
        "device": None,
        "attach_time": None,
        "delete_on_termination": False,
        "tags": {
            "Project": "DataWarehouse",
            "CostCenter": "Engineering",
            "Backup": "Daily",
        },
        "last_read_activity": "2024-02-10",
    }

    print_volume_detailed_report(volume_info)

    captured = capsys.readouterr()
    assert "Project: DataWarehouse" in captured.out
    assert "CostCenter: Engineering" in captured.out
    assert "Backup: Daily" in captured.out


def test_print_volume_detailed_report_no_tags(capsys):
    """Test print_volume_detailed_report when volume has no tags."""
    volume_info = {
        "volume_id": "vol-no-tags",
        "region": "ap-southeast-1",
        "volume_type": "st1",
        "size_gb": 500,
        "state": "available",
        "create_time": "2024-03-01",
        "availability_zone": "ap-southeast-1a",
        "encrypted": False,
        "iops": "N/A",
        "throughput": "N/A",
        "attached_to_instance_id": None,
        "attached_to_instance_name": "Unattached",
        "device": None,
        "attach_time": None,
        "delete_on_termination": False,
        "tags": {},
        "last_read_activity": "Unknown",
    }

    print_volume_detailed_report(volume_info)

    captured = capsys.readouterr()
    assert "Tags: None" in captured.out


def test_print_snapshot_summary_single(capsys):
    """Test print_snapshot_summary with single snapshot."""
    snapshots = [
        {
            "snapshot_id": "snap-123",
            "volume_name": "TestVolume",
            "volume_size": 100,
        }
    ]

    print_snapshot_summary(snapshots)

    captured = capsys.readouterr()
    assert "SNAPSHOT SUMMARY" in captured.out
    assert "Created 1 snapshots" in captured.out
    assert "Total size: 100 GB" in captured.out
    assert "$5.00" in captured.out  # 100 GB * 0.05
    assert "snap-123" in captured.out


def test_print_snapshot_summary_multiple(capsys):
    """Test print_snapshot_summary with multiple snapshots."""
    snapshots = [
        {"snapshot_id": "snap-001", "volume_name": "Vol1", "volume_size": 50},
        {"snapshot_id": "snap-002", "volume_name": "Vol2", "volume_size": 75},
        {"snapshot_id": "snap-003", "volume_name": "Vol3", "volume_size": 25},
    ]

    print_snapshot_summary(snapshots)

    captured = capsys.readouterr()
    assert "Created 3 snapshots" in captured.out
    assert "Total size: 150 GB" in captured.out
    assert "$7.50" in captured.out  # 150 GB * 0.05
    assert "snap-001" in captured.out
    assert "snap-002" in captured.out
    assert "snap-003" in captured.out


def test_print_snapshot_summary_background_message(capsys):
    """Test that print_snapshot_summary includes background creation message."""
    snapshots = [{"snapshot_id": "snap-bg", "volume_name": "BGVol", "volume_size": 10}]

    print_snapshot_summary(snapshots)

    captured = capsys.readouterr()
    assert "background" in captured.out.lower()
    assert "available shortly" in captured.out.lower()
