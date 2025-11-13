"""
Tests for cost_toolkit/scripts/audit/s3_audit/reporting.py - Optimization and
Cleanup Functions
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from cost_toolkit.scripts.audit.s3_audit.reporting import (
    _collect_cleanup_candidates,
    print_cleanup_opportunities,
    print_optimization_recommendations,
    print_storage_class_breakdown,
)
from tests.assertions import assert_equal


def test_print_storage_class_breakdown_empty():
    """Test print_storage_class_breakdown with no storage classes."""
    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        print_storage_class_breakdown({}, 0)
        output = mock_stdout.getvalue()
        assert_equal(output, "")


def test_print_storage_class_breakdown_single_class():
    """Test print_storage_class_breakdown with single storage class."""
    storage_class_summary = {
        "STANDARD": {"count": 100, "size_bytes": 10 * 1024**3, "cost": 23.0},
    }
    total_size_bytes = 10 * 1024**3

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        print_storage_class_breakdown(storage_class_summary, total_size_bytes)
        output = mock_stdout.getvalue()

        assert "Storage Class Breakdown:" in output
        assert "STANDARD:" in output
        assert "Objects: 100" in output
        assert "(100.0%)" in output
        assert "Cost: $23.00/month" in output


def test_print_storage_class_breakdown_multiple_classes():
    """Test print_storage_class_breakdown with multiple storage classes sorted by cost."""
    storage_class_summary = {
        "STANDARD": {"count": 100, "size_bytes": 10 * 1024**3, "cost": 23.0},
        "GLACIER": {"count": 200, "size_bytes": 20 * 1024**3, "cost": 8.0},
        "DEEP_ARCHIVE": {"count": 50, "size_bytes": 5 * 1024**3, "cost": 0.5},
    }
    total_size_bytes = 35 * 1024**3

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        print_storage_class_breakdown(storage_class_summary, total_size_bytes)
        output = mock_stdout.getvalue()

        assert "Storage Class Breakdown:" in output
        assert "STANDARD:" in output
        assert "GLACIER:" in output
        assert "DEEP_ARCHIVE:" in output

        # Verify percentage calculations
        assert "(28.6%)" in output  # STANDARD: 10/35
        assert "(57.1%)" in output  # GLACIER: 20/35
        assert "(14.3%)" in output  # DEEP_ARCHIVE: 5/35


def test_print_storage_class_breakdown_zero_total_size():
    """Test print_storage_class_breakdown with zero total size."""
    storage_class_summary = {
        "STANDARD": {"count": 0, "size_bytes": 0, "cost": 0.0},
    }
    total_size_bytes = 0

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        print_storage_class_breakdown(storage_class_summary, total_size_bytes)
        output = mock_stdout.getvalue()

        assert "Storage Class Breakdown:" in output
        assert "(0.0%)" in output


def test_print_optimization_recommendations_empty():
    """Test print_optimization_recommendations with no recommendations."""
    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        print_optimization_recommendations([])
        output = mock_stdout.getvalue()

        assert "No immediate optimization opportunities found" in output


def test_print_optimization_recommendations_without_savings():
    """Test print_optimization_recommendations with recommendations but no savings."""
    all_recommendations = [
        (
            "bucket1",
            {
                "description": "Enable versioning",
                "action": "Use lifecycle policies",
                "potential_savings": 0,
            },
        ),
    ]

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        print_optimization_recommendations(all_recommendations)
        output = mock_stdout.getvalue()

        assert "OPTIMIZATION RECOMMENDATIONS:" in output
        assert "bucket1:" in output
        assert "Enable versioning" in output
        assert "Action: Use lifecycle policies" in output
        # Should not include savings line
        assert "Potential savings:" not in output
        assert "Total potential monthly savings:" not in output


def test_print_optimization_recommendations_with_savings():
    """Test print_optimization_recommendations with potential savings."""
    all_recommendations = [
        (
            "bucket1",
            {
                "description": "Move old objects to Glacier",
                "action": "Configure lifecycle rule",
                "potential_savings": 15.50,
            },
        ),
        (
            "bucket2",
            {
                "description": "Archive infrequent data",
                "action": "Transition to Deep Archive",
                "potential_savings": 25.75,
            },
        ),
    ]

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        print_optimization_recommendations(all_recommendations)
        output = mock_stdout.getvalue()

        assert "OPTIMIZATION RECOMMENDATIONS:" in output
        assert "bucket1:" in output
        assert "Move old objects to Glacier" in output
        assert "Potential savings: $15.50/month" in output
        assert "bucket2:" in output
        assert "Archive infrequent data" in output
        assert "Potential savings: $25.75/month" in output
        assert "Total potential monthly savings: $41.25" in output
        assert "Annual potential savings: $495.00" in output


def test_collect_cleanup_candidates_empty():
    """Test _collect_cleanup_candidates with no old objects."""
    all_bucket_analyses = [
        {
            "bucket_name": "bucket1",
            "old_objects": [],
        },
    ]

    candidates = _collect_cleanup_candidates(all_bucket_analyses)
    assert_equal(len(candidates), 0)


def test_collect_cleanup_candidates_old_but_not_very_old():
    """Test _collect_cleanup_candidates with old but not very old objects."""
    all_bucket_analyses = [
        {
            "bucket_name": "bucket1",
            "old_objects": [
                {"age_days": 100, "size_bytes": 1024**3, "storage_class": "STANDARD"},
                {"age_days": 200, "size_bytes": 2 * 1024**3, "storage_class": "STANDARD"},
            ],
        },
    ]

    candidates = _collect_cleanup_candidates(all_bucket_analyses)
    assert_equal(len(candidates), 0)


def test_collect_cleanup_candidates_very_old_objects():
    """Test _collect_cleanup_candidates with very old objects (>365 days)."""
    all_bucket_analyses = [
        {
            "bucket_name": "bucket1",
            "old_objects": [
                {"age_days": 400, "size_bytes": 1024**3, "storage_class": "STANDARD"},
                {"age_days": 500, "size_bytes": 2 * 1024**3, "storage_class": "GLACIER"},
            ],
        },
    ]

    candidates = _collect_cleanup_candidates(all_bucket_analyses)

    assert_equal(len(candidates), 1)
    assert_equal(candidates[0]["bucket"], "bucket1")
    assert_equal(candidates[0]["type"], "very_old_objects")
    assert_equal(candidates[0]["count"], 2)
    assert_equal(candidates[0]["size"], 3 * 1024**3)
    assert "Objects older than 1 year" in candidates[0]["description"]


def test_collect_cleanup_candidates_multiple_buckets():
    """Test _collect_cleanup_candidates with multiple buckets."""
    all_bucket_analyses = [
        {
            "bucket_name": "bucket1",
            "old_objects": [
                {"age_days": 400, "size_bytes": 1024**3, "storage_class": "STANDARD"},
            ],
        },
        {
            "bucket_name": "bucket2",
            "old_objects": [
                {"age_days": 500, "size_bytes": 2 * 1024**3, "storage_class": "GLACIER"},
            ],
        },
    ]

    candidates = _collect_cleanup_candidates(all_bucket_analyses)

    assert_equal(len(candidates), 2)
    assert_equal(candidates[0]["bucket"], "bucket1")
    assert_equal(candidates[1]["bucket"], "bucket2")


def test_print_cleanup_opportunities_no_candidates():
    """Test print_cleanup_opportunities with no cleanup candidates."""
    all_bucket_analyses = [
        {
            "bucket_name": "bucket1",
            "old_objects": [],
        },
    ]

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        print_cleanup_opportunities(all_bucket_analyses)
        output = mock_stdout.getvalue()

        assert "CLEANUP OPPORTUNITIES" in output
        assert "No obvious cleanup candidates found" in output


def test_print_cleanup_opportunities_with_candidates():
    """Test print_cleanup_opportunities with cleanup candidates."""
    all_bucket_analyses = [
        {
            "bucket_name": "bucket1",
            "old_objects": [
                {"age_days": 400, "size_bytes": 1024**3, "storage_class": "STANDARD"},
                {"age_days": 500, "size_bytes": 2 * 1024**3, "storage_class": "STANDARD"},
            ],
        },
        {
            "bucket_name": "bucket2",
            "old_objects": [
                {"age_days": 600, "size_bytes": 5 * 1024**3, "storage_class": "GLACIER"},
            ],
        },
    ]

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        print_cleanup_opportunities(all_bucket_analyses)
        output = mock_stdout.getvalue()

        assert "CLEANUP OPPORTUNITIES" in output
        assert "Found 2 cleanup opportunities:" in output
        assert "Objects older than 1 year in bucket1" in output
        assert "2 objects" in output
        assert "Objects older than 1 year in bucket2" in output
        assert "1 objects" in output
        assert "Total cleanup potential:" in output
        assert "savings" in output
