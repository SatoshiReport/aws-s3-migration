"""Tests for cost_toolkit/scripts/snapshot_export_common.py module."""

from __future__ import annotations

from cost_toolkit.scripts.snapshot_export_common import (
    SAMPLE_SNAPSHOTS,
    print_export_results,
    print_export_summary,
)


def test_print_export_summary_basic(capsys):
    """Test print_export_summary with basic snapshot data."""
    snapshots = [
        {"size_gb": 8, "snapshot_id": "snap-001"},
        {"size_gb": 64, "snapshot_id": "snap-002"},
        {"size_gb": 384, "snapshot_id": "snap-003"},
    ]

    total_savings = {
        "ebs_cost": 22.8,
        "s3_cost": 10.488,
        "monthly_savings": 12.312,
        "annual_savings": 147.744,
        "savings_percentage": 54.0,
    }

    print_export_summary(snapshots, total_savings)

    captured = capsys.readouterr()
    assert "3 snapshots" in captured.out
    assert "456 GB total" in captured.out
    assert "$22.80" in captured.out
    assert "$10.49" in captured.out
    assert "$12.31" in captured.out
    assert "54.0%" in captured.out
    assert "$147.74" in captured.out


def test_print_export_summary_single_snapshot(capsys):
    """Test print_export_summary with single snapshot."""
    snapshots = [{"size_gb": 100, "snapshot_id": "snap-solo"}]

    total_savings = {
        "ebs_cost": 5.0,
        "s3_cost": 2.3,
        "monthly_savings": 2.7,
        "annual_savings": 32.4,
        "savings_percentage": 54.0,
    }

    print_export_summary(snapshots, total_savings)

    captured = capsys.readouterr()
    assert "1 snapshots" in captured.out
    assert "100 GB total" in captured.out
    assert "$5.00" in captured.out
    assert "$2.30" in captured.out


def test_print_export_summary_zero_size(capsys):
    """Test print_export_summary with zero size snapshots."""
    snapshots = []

    total_savings = {
        "ebs_cost": 0.0,
        "s3_cost": 0.0,
        "monthly_savings": 0.0,
        "annual_savings": 0.0,
        "savings_percentage": 0.0,
    }

    print_export_summary(snapshots, total_savings)

    captured = capsys.readouterr()
    assert "0 snapshots" in captured.out
    assert "0 GB total" in captured.out
    assert "$0.00" in captured.out


def test_print_export_results_basic(capsys):
    """Test print_export_results with basic export data."""
    export_results = [
        {
            "monthly_savings": 1.23,
            "snapshot_id": "snap-001",
            "bucket_name": "test-bucket",
            "s3_key": "exports/snap-001.vmdk",
        },
        {
            "monthly_savings": 4.56,
            "snapshot_id": "snap-002",
            "bucket_name": "test-bucket",
            "s3_key": "exports/snap-002.vmdk",
        },
    ]

    print_export_results(export_results)

    captured = capsys.readouterr()
    assert "$5.79" in captured.out  # Total monthly savings
    assert "$69.48" in captured.out  # Total annual savings


def test_print_export_results_snapshot_ids(capsys):
    """Test print_export_results displays snapshot IDs."""
    export_results = [
        {
            "monthly_savings": 1.23,
            "snapshot_id": "snap-001",
            "bucket_name": "test-bucket",
            "s3_key": "exports/snap-001.vmdk",
        },
        {
            "monthly_savings": 4.56,
            "snapshot_id": "snap-002",
            "bucket_name": "test-bucket",
            "s3_key": "exports/snap-002.vmdk",
        },
    ]

    print_export_results(export_results)

    captured = capsys.readouterr()
    assert "snap-001" in captured.out
    assert "snap-002" in captured.out


def test_print_export_results_s3_paths(capsys):
    """Test print_export_results displays S3 paths."""
    export_results = [
        {
            "monthly_savings": 1.23,
            "snapshot_id": "snap-001",
            "bucket_name": "test-bucket",
            "s3_key": "exports/snap-001.vmdk",
        },
        {
            "monthly_savings": 4.56,
            "snapshot_id": "snap-002",
            "bucket_name": "test-bucket",
            "s3_key": "exports/snap-002.vmdk",
        },
    ]

    print_export_results(export_results)

    captured = capsys.readouterr()
    assert "s3://test-bucket/exports/snap-001.vmdk" in captured.out
    assert "s3://test-bucket/exports/snap-002.vmdk" in captured.out


def test_print_export_results_next_steps(capsys):
    """Test print_export_results displays next steps."""
    export_results = [
        {
            "monthly_savings": 1.23,
            "snapshot_id": "snap-001",
            "bucket_name": "test-bucket",
            "s3_key": "exports/snap-001.vmdk",
        },
    ]

    print_export_results(export_results)

    captured = capsys.readouterr()
    assert "Next Steps:" in captured.out
    assert "Verify exports in S3 console" in captured.out
    assert "Test restore process" in captured.out
    assert "Delete original snapshots" in captured.out


def test_print_export_results_single_export(capsys):
    """Test print_export_results with single export."""
    export_results = [
        {
            "monthly_savings": 10.0,
            "snapshot_id": "snap-single",
            "bucket_name": "my-bucket",
            "s3_key": "path/to/export.vmdk",
        }
    ]

    print_export_results(export_results)

    captured = capsys.readouterr()
    assert "$10.00" in captured.out
    assert "$120.00" in captured.out
    assert "snap-single" in captured.out
    assert "s3://my-bucket/path/to/export.vmdk" in captured.out


def test_print_export_results_empty_list(capsys):
    """Test print_export_results with empty list."""
    export_results = []

    print_export_results(export_results)

    captured = capsys.readouterr()
    assert "$0.00" in captured.out
    assert "Next Steps:" in captured.out


def test_print_export_results_large_savings(capsys):
    """Test print_export_results with large savings amounts."""
    export_results = [
        {
            "monthly_savings": 1234.56,
            "snapshot_id": "snap-large",
            "bucket_name": "large-bucket",
            "s3_key": "large/export.vmdk",
        }
    ]

    print_export_results(export_results)

    captured = capsys.readouterr()
    assert "$1234.56" in captured.out
    assert "$14814.72" in captured.out  # 1234.56 * 12


def test_sample_snapshots_structure():
    """Test SAMPLE_SNAPSHOTS has expected structure."""
    assert len(SAMPLE_SNAPSHOTS) == 3
    assert all("snapshot_id" in snap for snap in SAMPLE_SNAPSHOTS)
    assert all("region" in snap for snap in SAMPLE_SNAPSHOTS)
    assert all("size_gb" in snap for snap in SAMPLE_SNAPSHOTS)
    assert all("description" in snap for snap in SAMPLE_SNAPSHOTS)


def test_sample_snapshots_content():
    """Test SAMPLE_SNAPSHOTS has expected content."""
    # Check first snapshot
    assert SAMPLE_SNAPSHOTS[0]["snapshot_id"] == "snap-036eee4a7c291fd26"
    assert SAMPLE_SNAPSHOTS[0]["region"] == "us-east-2"
    assert SAMPLE_SNAPSHOTS[0]["size_gb"] == 8

    # Check second snapshot
    assert SAMPLE_SNAPSHOTS[1]["snapshot_id"] == "snap-046b7eace8694913b"
    assert SAMPLE_SNAPSHOTS[1]["region"] == "eu-west-2"
    assert SAMPLE_SNAPSHOTS[1]["size_gb"] == 64

    # Check third snapshot
    assert SAMPLE_SNAPSHOTS[2]["snapshot_id"] == "snap-0f68820355c25e73e"
    assert SAMPLE_SNAPSHOTS[2]["region"] == "eu-west-2"
    assert SAMPLE_SNAPSHOTS[2]["size_gb"] == 384


def test_print_export_summary_various_sizes(capsys):
    """Test print_export_summary with various snapshot sizes."""
    snapshots = [
        {"size_gb": 1, "snapshot_id": "snap-tiny"},
        {"size_gb": 500, "snapshot_id": "snap-medium"},
        {"size_gb": 1000, "snapshot_id": "snap-large"},
    ]

    total_savings = {
        "ebs_cost": 75.05,
        "s3_cost": 34.523,
        "monthly_savings": 40.527,
        "annual_savings": 486.324,
        "savings_percentage": 54.0,
    }

    print_export_summary(snapshots, total_savings)

    captured = capsys.readouterr()
    assert "1501 GB total" in captured.out


def test_print_export_results_special_characters_in_paths(capsys):
    """Test print_export_results handles special characters in S3 paths."""
    export_results = [
        {
            "monthly_savings": 5.0,
            "snapshot_id": "snap-special-chars",
            "bucket_name": "bucket-with-dashes",
            "s3_key": "path/with/multiple/levels/export.vmdk",
        }
    ]

    print_export_results(export_results)

    captured = capsys.readouterr()
    assert "s3://bucket-with-dashes/path/with/multiple/levels/export.vmdk" in captured.out


def test_print_export_summary_fractional_gb(capsys):
    """Test print_export_summary with fractional GB sizes."""
    snapshots = [
        {"size_gb": 0.5, "snapshot_id": "snap-small-1"},
        {"size_gb": 1.25, "snapshot_id": "snap-small-2"},
        {"size_gb": 2.75, "snapshot_id": "snap-small-3"},
    ]

    total_savings = {
        "ebs_cost": 0.225,
        "s3_cost": 0.10425,
        "monthly_savings": 0.12075,
        "annual_savings": 1.449,
        "savings_percentage": 53.7,
    }

    print_export_summary(snapshots, total_savings)

    captured = capsys.readouterr()
    # Should show fractional GB total (0.5 + 1.25 + 2.75 = 4.5)
    assert "3 snapshots" in captured.out


def test_print_export_results_zero_savings(capsys):
    """Test print_export_results with zero monthly savings."""
    export_results = [
        {
            "monthly_savings": 0.0,
            "snapshot_id": "snap-no-savings",
            "bucket_name": "test-bucket",
            "s3_key": "test.vmdk",
        }
    ]

    print_export_results(export_results)

    captured = capsys.readouterr()
    assert "$0.00" in captured.out


def test_print_export_summary_high_savings_percentage(capsys):
    """Test print_export_summary with high savings percentage."""
    snapshots = [{"size_gb": 100, "snapshot_id": "snap-high-savings"}]

    total_savings = {
        "ebs_cost": 10.0,
        "s3_cost": 0.5,
        "monthly_savings": 9.5,
        "annual_savings": 114.0,
        "savings_percentage": 95.0,
    }

    print_export_summary(snapshots, total_savings)

    captured = capsys.readouterr()
    assert "95.0%" in captured.out


def test_print_export_summary_low_savings_percentage(capsys):
    """Test print_export_summary with low savings percentage."""
    snapshots = [{"size_gb": 10, "snapshot_id": "snap-low-savings"}]

    total_savings = {
        "ebs_cost": 1.0,
        "s3_cost": 0.9,
        "monthly_savings": 0.1,
        "annual_savings": 1.2,
        "savings_percentage": 10.0,
    }

    print_export_summary(snapshots, total_savings)

    captured = capsys.readouterr()
    assert "10.0%" in captured.out
