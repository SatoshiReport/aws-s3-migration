"""Tests for cost_toolkit/scripts/audit/s3_audit/cli.py - all buckets processing"""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.scripts.audit.s3_audit.cli import (
    _process_all_buckets,
)
from tests.assertions import assert_equal


def test_process_all_buckets_success():
    """Test _process_all_buckets with multiple successful buckets."""
    buckets = [
        {"Name": "bucket1"},
        {"Name": "bucket2"},
    ]

    bucket1_analysis = {
        "bucket_name": "bucket1",
        "total_objects": 100,
        "total_size_bytes": 1024**3,
    }

    bucket2_analysis = {
        "bucket_name": "bucket2",
        "total_objects": 50,
        "total_size_bytes": 512 * 1024**2,
    }

    with patch(
        "cost_toolkit.scripts.audit.s3_audit.cli.get_bucket_region",
        return_value="us-east-1",
    ):
        with patch(
            "cost_toolkit.scripts.audit.s3_audit.cli._process_single_bucket",
            side_effect=[
                (bucket1_analysis, 100, 1024**3, 23.0, [("bucket1", {"type": "test"})]),
                (bucket2_analysis, 50, 512 * 1024**2, 11.5, []),
            ],
        ):
            result = _process_all_buckets(buckets)

    (
        all_analyses,
        _,
        all_recs,
        total_objects,
        total_size,
        total_cost,
    ) = result

    assert_equal(len(all_analyses), 2)
    assert_equal(total_objects, 150)
    assert_equal(total_size, 1024**3 + 512 * 1024**2)
    assert_equal(total_cost, 34.5)
    assert_equal(len(all_recs), 1)


def test_process_all_buckets_some_fail():
    """Test _process_all_buckets when some buckets fail analysis."""
    buckets = [
        {"Name": "bucket1"},
        {"Name": "bucket2"},
        {"Name": "bucket3"},
    ]

    bucket1_analysis = {
        "bucket_name": "bucket1",
        "total_objects": 100,
        "total_size_bytes": 1024**3,
    }

    with patch(
        "cost_toolkit.scripts.audit.s3_audit.cli.get_bucket_region",
        return_value="us-east-1",
    ):
        with patch(
            "cost_toolkit.scripts.audit.s3_audit.cli._process_single_bucket",
            side_effect=[
                (bucket1_analysis, 100, 1024**3, 23.0, []),
                (None, 0, 0, 0, []),  # bucket2 fails
                (bucket1_analysis, 100, 1024**3, 23.0, []),
            ],
        ):
            result = _process_all_buckets(buckets)

    (
        all_analyses,
        _,
        _,
        total_objects,
        total_size,
        total_cost,
    ) = result

    # Only 2 buckets should be in results (bucket2 failed)
    assert_equal(len(all_analyses), 2)
    assert_equal(total_objects, 200)
    assert_equal(total_size, 2 * 1024**3)
    assert_equal(total_cost, 46.0)


def test_process_all_buckets_empty():
    """Test _process_all_buckets with empty bucket list."""
    result = _process_all_buckets([])

    (
        all_analyses,
        _,
        all_recs,
        total_objects,
        total_size,
        total_cost,
    ) = result

    assert_equal(len(all_analyses), 0)
    assert_equal(total_objects, 0)
    assert_equal(total_size, 0)
    assert_equal(total_cost, 0)
    assert_equal(len(all_recs), 0)


def test_process_all_buckets_aggregates_recommendations():
    """Test _process_all_buckets aggregates recommendations from multiple buckets."""
    buckets = [
        {"Name": "bucket1"},
        {"Name": "bucket2"},
    ]

    bucket1_recs = [("bucket1", {"type": "test1"})]
    bucket2_recs = [("bucket2", {"type": "test2"}), ("bucket2", {"type": "test3"})]

    with patch(
        "cost_toolkit.scripts.audit.s3_audit.cli.get_bucket_region",
        return_value="us-east-1",
    ):
        with patch(
            "cost_toolkit.scripts.audit.s3_audit.cli._process_single_bucket",
            side_effect=[
                ({"bucket_name": "bucket1"}, 100, 1024**3, 23.0, bucket1_recs),
                ({"bucket_name": "bucket2"}, 50, 512 * 1024**2, 11.5, bucket2_recs),
            ],
        ):
            result = _process_all_buckets(buckets)

    (
        _,
        _,
        all_recs,
        total_objects,
        total_size,
        total_cost,
    ) = result

    assert_equal(total_objects, 150)
    assert_equal(total_size, 1024**3 + 512 * 1024**2)
    assert_equal(total_cost, 34.5)
    assert_equal(len(all_recs), 3)
    assert_equal(all_recs[0][0], "bucket1")
    assert_equal(all_recs[1][0], "bucket2")
    assert_equal(all_recs[2][0], "bucket2")
