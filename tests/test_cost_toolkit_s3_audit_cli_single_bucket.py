"""Tests for cost_toolkit/scripts/audit/s3_audit/cli.py - single bucket processing"""

from __future__ import annotations

from collections import defaultdict
from unittest.mock import patch

from cost_toolkit.scripts.audit.s3_audit.cli import (
    _process_single_bucket,
)
from tests.assertions import assert_equal


def test_process_single_bucket_success(capsys):
    """Test _process_single_bucket with successful bucket analysis."""
    storage_class_summary = defaultdict(lambda: {"count": 0, "size_bytes": 0, "cost": 0})

    bucket_analysis = {
        "bucket_name": "test-bucket",
        "region": "us-east-1",
        "total_objects": 100,
        "total_size_bytes": 1024**3,  # 1 GB
        "storage_classes": {"STANDARD": {"count": 100, "size_bytes": 1024**3}},
        "versioning_enabled": True,
        "lifecycle_policy": [],
        "encryption": None,
        "public_access": False,
        "last_modified_oldest": None,
        "last_modified_newest": None,
        "large_objects": [],
        "old_objects": [],
    }

    recommendations = [
        {
            "type": "lifecycle_policy",
            "description": "No lifecycle policy configured",
            "potential_savings": 0,
            "action": "Consider implementing lifecycle policies",
        }
    ]

    with patch(
        "cost_toolkit.scripts.audit.s3_audit.cli.analyze_bucket_objects",
        return_value=bucket_analysis,
    ):
        with patch(
            "cost_toolkit.scripts.audit.s3_audit.cli.calculate_monthly_cost",
            return_value=23.0,
        ):
            with patch("cost_toolkit.scripts.audit.s3_audit.cli.display_bucket_summary"):
                with patch(
                    "cost_toolkit.scripts.audit.s3_audit.cli.generate_optimization_recommendations",
                    return_value=recommendations,
                ):
                    result = _process_single_bucket("test-bucket", "us-east-1", storage_class_summary)

    analysis, obj_count, size, cost, recs = result

    assert_equal(analysis, bucket_analysis)
    assert_equal(obj_count, 100)
    assert_equal(size, 1024**3)
    assert_equal(cost, 23.0)
    assert_equal(len(recs), 1)
    assert_equal(recs[0][0], "test-bucket")
    assert_equal(recs[0][1]["type"], "lifecycle_policy")

    # Check storage class summary was updated
    assert_equal(storage_class_summary["STANDARD"]["count"], 100)
    assert_equal(storage_class_summary["STANDARD"]["size_bytes"], 1024**3)
    assert_equal(storage_class_summary["STANDARD"]["cost"], 23.0)

    captured = capsys.readouterr()
    assert "Analyzing bucket: test-bucket" in captured.out


def test_process_single_bucket_no_recommendations():
    """Test _process_single_bucket with no recommendations."""
    storage_class_summary = defaultdict(lambda: {"count": 0, "size_bytes": 0, "cost": 0})

    bucket_analysis = {
        "bucket_name": "test-bucket",
        "region": "us-east-1",
        "total_objects": 50,
        "total_size_bytes": 1024**2,  # 1 MB
        "storage_classes": {"STANDARD": {"count": 50, "size_bytes": 1024**2}},
        "versioning_enabled": False,
        "lifecycle_policy": [],
        "encryption": None,
        "public_access": False,
        "last_modified_oldest": None,
        "last_modified_newest": None,
        "large_objects": [],
        "old_objects": [],
    }

    with patch(
        "cost_toolkit.scripts.audit.s3_audit.cli.analyze_bucket_objects",
        return_value=bucket_analysis,
    ):
        with patch(
            "cost_toolkit.scripts.audit.s3_audit.cli.calculate_monthly_cost",
            return_value=0.023,
        ):
            with patch("cost_toolkit.scripts.audit.s3_audit.cli.display_bucket_summary"):
                with patch(
                    "cost_toolkit.scripts.audit.s3_audit.cli.generate_optimization_recommendations",
                    return_value=[],
                ):
                    result = _process_single_bucket("test-bucket", "us-east-1", storage_class_summary)

    analysis, obj_count, size, cost, recs = result

    assert_equal(analysis, bucket_analysis)
    assert_equal(obj_count, 50)
    assert_equal(size, 1024**2)
    assert_equal(cost, 0.023)
    assert_equal(len(recs), 0)


def test_process_single_bucket_multiple_storage_classes():
    """Test _process_single_bucket with multiple storage classes."""
    storage_class_summary = defaultdict(lambda: {"count": 0, "size_bytes": 0, "cost": 0})

    bucket_analysis = {
        "bucket_name": "test-bucket",
        "region": "us-west-2",
        "total_objects": 200,
        "total_size_bytes": 3 * 1024**3,  # 3 GB
        "storage_classes": {
            "STANDARD": {"count": 100, "size_bytes": 2 * 1024**3},
            "GLACIER": {"count": 100, "size_bytes": 1024**3},
        },
        "versioning_enabled": False,
        "lifecycle_policy": [],
        "encryption": None,
        "public_access": False,
        "last_modified_oldest": None,
        "last_modified_newest": None,
        "large_objects": [],
        "old_objects": [],
    }

    cost_map = {"STANDARD": 46.0, "GLACIER": 4.0}

    with patch(
        "cost_toolkit.scripts.audit.s3_audit.cli.analyze_bucket_objects",
        return_value=bucket_analysis,
    ):
        with patch(
            "cost_toolkit.scripts.audit.s3_audit.cli.calculate_monthly_cost",
            side_effect=lambda size, cls: cost_map[cls],
        ):
            with patch("cost_toolkit.scripts.audit.s3_audit.cli.display_bucket_summary"):
                with patch(
                    "cost_toolkit.scripts.audit.s3_audit.cli.generate_optimization_recommendations",
                    return_value=[],
                ):
                    result = _process_single_bucket("test-bucket", "us-west-2", storage_class_summary)

    _, obj_count, size, cost, recs = result

    assert_equal(obj_count, 200)
    assert_equal(size, 3 * 1024**3)
    assert_equal(cost, 50.0)  # 46 + 4
    assert_equal(len(recs), 0)  # Verify no recommendations

    # Check both storage classes in summary
    assert_equal(storage_class_summary["STANDARD"]["count"], 100)
    assert_equal(storage_class_summary["STANDARD"]["size_bytes"], 2 * 1024**3)
    assert_equal(storage_class_summary["STANDARD"]["cost"], 46.0)
    assert_equal(storage_class_summary["GLACIER"]["count"], 100)
    assert_equal(storage_class_summary["GLACIER"]["size_bytes"], 1024**3)
    assert_equal(storage_class_summary["GLACIER"]["cost"], 4.0)


def test_process_single_bucket_analysis_fails(capsys):
    """Test _process_single_bucket when bucket analysis fails."""
    storage_class_summary = defaultdict(lambda: {"count": 0, "size_bytes": 0, "cost": 0})

    with patch(
        "cost_toolkit.scripts.audit.s3_audit.cli.analyze_bucket_objects",
        return_value=None,
    ):
        result = _process_single_bucket("failed-bucket", "us-east-1", storage_class_summary)

    analysis, obj_count, size, cost, recs = result

    assert_equal(analysis, None)
    assert_equal(obj_count, 0)
    assert_equal(size, 0)
    assert_equal(cost, 0)
    assert_equal(len(recs), 0)

    captured = capsys.readouterr()
    assert "Could not analyze bucket failed-bucket" in captured.out


def test_process_single_bucket_accumulates_recommendations():
    """Test that _process_single_bucket properly accumulates multiple recommendations."""
    storage_class_summary = defaultdict(lambda: {"count": 0, "size_bytes": 0, "cost": 0})

    bucket_analysis = {
        "bucket_name": "test-bucket",
        "region": "us-east-1",
        "total_objects": 100,
        "total_size_bytes": 1024**3,
        "storage_classes": {"STANDARD": {"count": 100, "size_bytes": 1024**3}},
        "versioning_enabled": True,
        "lifecycle_policy": [],
        "encryption": None,
        "public_access": False,
        "last_modified_oldest": None,
        "last_modified_newest": None,
        "large_objects": [],
        "old_objects": [],
    }

    recommendations = [
        {
            "type": "lifecycle_policy",
            "description": "No lifecycle policy",
            "potential_savings": 0,
            "action": "Add lifecycle",
        },
        {
            "type": "security_optimization",
            "description": "Public access",
            "potential_savings": 0,
            "action": "Block public access",
        },
    ]

    with patch(
        "cost_toolkit.scripts.audit.s3_audit.cli.analyze_bucket_objects",
        return_value=bucket_analysis,
    ):
        with patch(
            "cost_toolkit.scripts.audit.s3_audit.cli.calculate_monthly_cost",
            return_value=23.0,
        ):
            with patch("cost_toolkit.scripts.audit.s3_audit.cli.display_bucket_summary"):
                with patch(
                    "cost_toolkit.scripts.audit.s3_audit.cli.generate_optimization_recommendations",
                    return_value=recommendations,
                ):
                    result = _process_single_bucket("test-bucket", "us-east-1", storage_class_summary)

    _, obj_count, size, cost, recs = result

    assert_equal(obj_count, 100)
    assert_equal(size, 1024**3)
    assert_equal(cost, 23.0)
    assert_equal(len(recs), 2)
    assert_equal(recs[0][0], "test-bucket")
    assert_equal(recs[0][1]["type"], "lifecycle_policy")
    assert_equal(recs[1][0], "test-bucket")
    assert_equal(recs[1][1]["type"], "security_optimization")
