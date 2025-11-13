"""Tests for cost_toolkit/scripts/audit/s3_audit/reporting.py - Display and Summary Functions"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import patch

from cost_toolkit.scripts.audit.s3_audit.reporting import (
    _print_bucket_age_info,
    _print_bucket_optimization_opportunities,
    _print_bucket_storage_classes,
    display_bucket_summary,
    print_overall_summary,
)
from tests.assertions import assert_equal


def test_print_bucket_storage_classes_empty():
    """Test _print_bucket_storage_classes with empty storage classes."""
    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        _print_bucket_storage_classes({})
        output = mock_stdout.getvalue()
        assert_equal(output, "")


def test_print_bucket_storage_classes_with_data():
    """Test _print_bucket_storage_classes with storage class data."""
    storage_classes = {
        "STANDARD": {"count": 100, "size_bytes": 1024**3},
        "GLACIER": {"count": 50, "size_bytes": 5 * 1024**3},
    }

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        _print_bucket_storage_classes(storage_classes)
        output = mock_stdout.getvalue()

        assert "Storage classes:" in output
        assert "STANDARD:" in output
        assert "100 objects" in output
        assert "GLACIER:" in output
        assert "50 objects" in output


def test_print_bucket_age_info_no_dates():
    """Test _print_bucket_age_info with no date information."""
    bucket_analysis = {"last_modified_oldest": None, "last_modified_newest": None}

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        _print_bucket_age_info(bucket_analysis)
        output = mock_stdout.getvalue()
        assert_equal(output, "")


def test_print_bucket_age_info_only_oldest():
    """Test _print_bucket_age_info with only oldest date."""
    bucket_analysis = {
        "last_modified_oldest": datetime.now(timezone.utc) - timedelta(days=100),
        "last_modified_newest": None,
    }

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        _print_bucket_age_info(bucket_analysis)
        output = mock_stdout.getvalue()
        assert_equal(output, "")


def test_print_bucket_age_info_only_newest():
    """Test _print_bucket_age_info with only newest date."""
    bucket_analysis = {
        "last_modified_oldest": None,
        "last_modified_newest": datetime.now(timezone.utc) - timedelta(days=1),
    }

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        _print_bucket_age_info(bucket_analysis)
        output = mock_stdout.getvalue()
        assert_equal(output, "")


def test_print_bucket_age_info_with_dates():
    """Test _print_bucket_age_info with valid date range."""
    bucket_analysis = {
        "last_modified_oldest": datetime.now(timezone.utc) - timedelta(days=100),
        "last_modified_newest": datetime.now(timezone.utc) - timedelta(days=1),
    }

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        _print_bucket_age_info(bucket_analysis)
        output = mock_stdout.getvalue()

        assert "Object age range:" in output
        assert "1 to 100 days" in output


def test_print_bucket_optimization_opportunities_empty():
    """Test _print_bucket_optimization_opportunities with no opportunities."""
    bucket_analysis = {"old_objects": [], "large_objects": []}

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        _print_bucket_optimization_opportunities(bucket_analysis)
        output = mock_stdout.getvalue()
        assert_equal(output, "")


def test_print_bucket_optimization_opportunities_old_objects():
    """Test _print_bucket_optimization_opportunities with old objects."""
    bucket_analysis = {
        "old_objects": [
            {"size_bytes": 1024**3},
            {"size_bytes": 2 * 1024**3},
        ],
        "large_objects": [],
    }

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        _print_bucket_optimization_opportunities(bucket_analysis)
        output = mock_stdout.getvalue()

        assert "Old objects (>90 days):" in output
        assert "2 objects" in output


def test_print_bucket_optimization_opportunities_large_objects():
    """Test _print_bucket_optimization_opportunities with large objects."""
    bucket_analysis = {
        "old_objects": [],
        "large_objects": [
            {"size_bytes": 200 * 1024**2},
            {"size_bytes": 300 * 1024**2},
        ],
    }

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        _print_bucket_optimization_opportunities(bucket_analysis)
        output = mock_stdout.getvalue()

        assert "Large objects (>100MB):" in output
        assert "2 objects" in output


def test_print_bucket_optimization_opportunities_both():
    """Test _print_bucket_optimization_opportunities with both types."""
    bucket_analysis = {
        "old_objects": [{"size_bytes": 1024**3}],
        "large_objects": [{"size_bytes": 200 * 1024**2}],
    }

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        _print_bucket_optimization_opportunities(bucket_analysis)
        output = mock_stdout.getvalue()

        assert "Old objects (>90 days):" in output
        assert "Large objects (>100MB):" in output


def test_display_bucket_summary_minimal():
    """Test display_bucket_summary with minimal bucket data."""
    bucket_analysis = {
        "total_objects": 100,
        "total_size_bytes": 1024**3,
        "versioning_enabled": False,
        "lifecycle_policy": [],
        "encryption": None,
        "public_access": False,
        "storage_classes": {},
        "last_modified_oldest": None,
        "last_modified_newest": None,
        "old_objects": [],
        "large_objects": [],
    }
    bucket_cost = 10.50

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        display_bucket_summary(bucket_analysis, bucket_cost)
        output = mock_stdout.getvalue()

        assert "Objects: 100" in output
        assert "Total size:" in output
        assert "Estimated monthly cost: $10.50" in output
        assert "Versioning: Disabled" in output
        assert "Lifecycle policies: 0 configured" in output
        assert "Encryption: Not configured" in output
        assert "Public access: Blocked" in output


def test_display_bucket_summary_full_features_basic():
    """Test display_bucket_summary shows basic stats."""
    bucket_analysis = {
        "total_objects": 500,
        "total_size_bytes": 10 * 1024**3,
        "versioning_enabled": True,
        "lifecycle_policy": [{"id": "rule1"}, {"id": "rule2"}],
        "encryption": {
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        },
        "public_access": True,
        "storage_classes": {
            "STANDARD": {"count": 300, "size_bytes": 5 * 1024**3},
            "GLACIER": {"count": 200, "size_bytes": 5 * 1024**3},
        },
        "last_modified_oldest": datetime.now(timezone.utc) - timedelta(days=100),
        "last_modified_newest": datetime.now(timezone.utc) - timedelta(days=1),
        "old_objects": [{"size_bytes": 1024**3}],
        "large_objects": [{"size_bytes": 200 * 1024**2}],
    }
    bucket_cost = 25.75

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        display_bucket_summary(bucket_analysis, bucket_cost)
        output = mock_stdout.getvalue()

        assert "Objects: 500" in output
        assert "Estimated monthly cost: $25.75" in output
        assert "Versioning: Enabled" in output


def test_display_bucket_summary_full_features_policies():
    """Test display_bucket_summary shows policies and security."""
    bucket_analysis = {
        "total_objects": 500,
        "total_size_bytes": 10 * 1024**3,
        "versioning_enabled": True,
        "lifecycle_policy": [{"id": "rule1"}, {"id": "rule2"}],
        "encryption": {
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        },
        "public_access": True,
        "storage_classes": {
            "STANDARD": {"count": 300, "size_bytes": 5 * 1024**3},
            "GLACIER": {"count": 200, "size_bytes": 5 * 1024**3},
        },
        "last_modified_oldest": datetime.now(timezone.utc) - timedelta(days=100),
        "last_modified_newest": datetime.now(timezone.utc) - timedelta(days=1),
        "old_objects": [{"size_bytes": 1024**3}],
        "large_objects": [{"size_bytes": 200 * 1024**2}],
    }
    bucket_cost = 25.75

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        display_bucket_summary(bucket_analysis, bucket_cost)
        output = mock_stdout.getvalue()

        assert "Lifecycle policies: 2 configured" in output
        assert "Encryption: Configured" in output
        assert "Public access: Possible" in output


def test_display_bucket_summary_full_features_storage():
    """Test display_bucket_summary shows storage details."""
    bucket_analysis = {
        "total_objects": 500,
        "total_size_bytes": 10 * 1024**3,
        "versioning_enabled": True,
        "lifecycle_policy": [{"id": "rule1"}, {"id": "rule2"}],
        "encryption": {
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        },
        "public_access": True,
        "storage_classes": {
            "STANDARD": {"count": 300, "size_bytes": 5 * 1024**3},
            "GLACIER": {"count": 200, "size_bytes": 5 * 1024**3},
        },
        "last_modified_oldest": datetime.now(timezone.utc) - timedelta(days=100),
        "last_modified_newest": datetime.now(timezone.utc) - timedelta(days=1),
        "old_objects": [{"size_bytes": 1024**3}],
        "large_objects": [{"size_bytes": 200 * 1024**2}],
    }
    bucket_cost = 25.75

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        display_bucket_summary(bucket_analysis, bucket_cost)
        output = mock_stdout.getvalue()

        assert "Storage classes:" in output
        assert "Object age range:" in output
        assert "Old objects (>90 days):" in output
        assert "Large objects (>100MB):" in output


def test_print_overall_summary():
    """Test print_overall_summary output."""
    all_bucket_analyses = [
        {"bucket_name": "bucket1"},
        {"bucket_name": "bucket2"},
        {"bucket_name": "bucket3"},
    ]
    total_objects = 1000
    total_size_bytes = 100 * 1024**3
    total_monthly_cost = 250.00

    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        print_overall_summary(
            all_bucket_analyses, total_objects, total_size_bytes, total_monthly_cost
        )
        output = mock_stdout.getvalue()

        assert "OVERALL S3 SUMMARY" in output
        assert "Total buckets analyzed: 3" in output
        assert "Total objects: 1,000" in output
        assert "Total storage size:" in output
        assert "Estimated monthly cost: $250.00" in output
