"""Tests for cost_toolkit/scripts/audit/s3_audit/recommendations.py"""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.scripts.audit.s3_audit.recommendations import (
    _check_large_objects_and_security,
    _check_lifecycle_and_versioning,
    _check_storage_class_optimization,
    _create_glacier_recommendation,
    _create_ia_recommendation,
    generate_optimization_recommendations,
)
from tests.assertions import assert_equal


def test_create_ia_recommendation_no_old_standard_objects():
    """Test _create_ia_recommendation returns None when no old STANDARD objects."""
    old_objects = [
        {"storage_class": "GLACIER", "age_days": 100, "size_bytes": 1024},
        {"storage_class": "STANDARD", "age_days": 10, "size_bytes": 2048},
    ]
    with patch("cost_toolkit.scripts.audit.s3_audit.recommendations.DAYS_THRESHOLD_IA", 30):
        result = _create_ia_recommendation(old_objects)
        assert_equal(result, None)


def test_create_ia_recommendation_with_old_standard_objects():
    """Test _create_ia_recommendation generates recommendation for old STANDARD objects."""
    old_objects = [
        {"storage_class": "STANDARD", "age_days": 60, "size_bytes": 1024**3},
        {"storage_class": "STANDARD", "age_days": 45, "size_bytes": 2 * 1024**3},
        {"storage_class": "GLACIER", "age_days": 100, "size_bytes": 1024**3},
    ]
    with (
        patch("cost_toolkit.scripts.audit.s3_audit.recommendations.DAYS_THRESHOLD_IA", 30),
        patch(
            "cost_toolkit.scripts.audit.s3_audit.recommendations.calculate_monthly_cost",
            side_effect=[0.069, 0.0375],
        ),
        patch(
            "cost_toolkit.scripts.audit.s3_audit.recommendations.format_bytes",
            return_value="3.00 GB",
        ),
    ):
        result = _create_ia_recommendation(old_objects)
        assert_equal(result["type"], "storage_class_optimization")
        assert abs(result["potential_savings"] - 0.0315) < 0.0001
        assert "2 objects" in result["description"]
        assert "3.00 GB" in result["description"]


def test_create_glacier_recommendation_no_very_old_objects():
    """Test _create_glacier_recommendation returns None when no very old objects."""
    old_objects = [
        {"storage_class": "STANDARD", "age_days": 60, "size_bytes": 1024},
        {"storage_class": "GLACIER", "age_days": 100, "size_bytes": 2048},
    ]
    with patch("cost_toolkit.scripts.audit.s3_audit.recommendations.DAYS_THRESHOLD_GLACIER", 90):
        result = _create_glacier_recommendation(old_objects)
        assert_equal(result, None)


def test_create_glacier_recommendation_with_very_old_objects():
    """Test _create_glacier_recommendation generates recommendation for very old objects."""
    old_objects = [
        {"storage_class": "STANDARD", "age_days": 120, "size_bytes": 1024**3},
        {"storage_class": "STANDARD_IA", "age_days": 150, "size_bytes": 2 * 1024**3},
        {"storage_class": "GLACIER", "age_days": 200, "size_bytes": 1024**3},
    ]
    with (
        patch("cost_toolkit.scripts.audit.s3_audit.recommendations.DAYS_THRESHOLD_GLACIER", 90),
        patch(
            "cost_toolkit.scripts.audit.s3_audit.recommendations.calculate_monthly_cost",
            side_effect=[0.069, 0.012],
        ),
        patch(
            "cost_toolkit.scripts.audit.s3_audit.recommendations.format_bytes",
            return_value="3.00 GB",
        ),
    ):
        result = _create_glacier_recommendation(old_objects)
        assert_equal(result["type"], "archival_optimization")
        assert abs(result["potential_savings"] - 0.057) < 0.0001
        assert "2 objects" in result["description"]
        assert "3.00 GB" in result["description"]


def test_check_storage_class_optimization_no_standard_objects():
    """Test _check_storage_class_optimization when no STANDARD objects exist."""
    bucket_analysis = {
        "storage_classes": {"GLACIER": {"count": 5, "size_bytes": 1024**3}},
        "old_objects": [],
    }
    result = _check_storage_class_optimization(bucket_analysis)
    assert_equal(result, [])


def test_check_storage_class_optimization_with_recommendations():
    """Test _check_storage_class_optimization generates both IA and Glacier recommendations."""
    bucket_analysis = {
        "storage_classes": {"STANDARD": {"count": 10, "size_bytes": 10 * 1024**3}},
        "old_objects": [
            {"storage_class": "STANDARD", "age_days": 60, "size_bytes": 1024**3},
            {"storage_class": "STANDARD", "age_days": 120, "size_bytes": 2 * 1024**3},
        ],
    }
    with (
        patch(
            "cost_toolkit.scripts.audit.s3_audit.recommendations._create_ia_recommendation",
            return_value={"type": "storage_class_optimization", "potential_savings": 0.05},
        ),
        patch(
            "cost_toolkit.scripts.audit.s3_audit.recommendations._create_glacier_recommendation",
            return_value={"type": "archival_optimization", "potential_savings": 0.1},
        ),
    ):
        result = _check_storage_class_optimization(bucket_analysis)
        assert_equal(len(result), 2)
        assert_equal(result[0]["type"], "storage_class_optimization")
        assert_equal(result[1]["type"], "archival_optimization")


def test_check_storage_class_optimization_only_ia_recommendation():
    """Test _check_storage_class_optimization when only IA recommendation is generated."""
    bucket_analysis = {
        "storage_classes": {"STANDARD": {"count": 10, "size_bytes": 10 * 1024**3}},
        "old_objects": [
            {"storage_class": "STANDARD", "age_days": 60, "size_bytes": 1024**3},
        ],
    }
    with (
        patch(
            "cost_toolkit.scripts.audit.s3_audit.recommendations._create_ia_recommendation",
            return_value={"type": "storage_class_optimization", "potential_savings": 0.05},
        ),
        patch(
            "cost_toolkit.scripts.audit.s3_audit.recommendations._create_glacier_recommendation",
            return_value=None,
        ),
    ):
        result = _check_storage_class_optimization(bucket_analysis)
        assert_equal(len(result), 1)
        assert_equal(result[0]["type"], "storage_class_optimization")


def test_check_lifecycle_and_versioning_no_issues():
    """Test _check_lifecycle_and_versioning when lifecycle policy exists."""
    bucket_analysis = {
        "lifecycle_policy": True,
        "versioning_enabled": False,
    }
    result = _check_lifecycle_and_versioning(bucket_analysis)
    assert_equal(result, [])


def test_check_lifecycle_and_versioning_no_lifecycle_policy():
    """Test _check_lifecycle_and_versioning recommends lifecycle policy."""
    bucket_analysis = {
        "lifecycle_policy": False,
        "versioning_enabled": False,
    }
    result = _check_lifecycle_and_versioning(bucket_analysis)
    assert_equal(len(result), 1)
    assert_equal(result[0]["type"], "lifecycle_policy")
    assert_equal(result[0]["potential_savings"], 0)
    assert "No lifecycle policy" in result[0]["description"]


def test_check_lifecycle_and_versioning_versioning_without_lifecycle():
    """Test _check_lifecycle_and_versioning when versioning enabled without lifecycle."""
    bucket_analysis = {
        "lifecycle_policy": False,
        "versioning_enabled": True,
    }
    result = _check_lifecycle_and_versioning(bucket_analysis)
    assert_equal(len(result), 2)
    assert_equal(result[0]["type"], "lifecycle_policy")
    assert_equal(result[1]["type"], "versioning_optimization")
    assert "Versioning enabled" in result[1]["description"]


def test_check_lifecycle_and_versioning_versioning_with_lifecycle():
    """Test _check_lifecycle_and_versioning when both versioning and lifecycle exist."""
    bucket_analysis = {
        "lifecycle_policy": True,
        "versioning_enabled": True,
    }
    result = _check_lifecycle_and_versioning(bucket_analysis)
    assert_equal(result, [])


def test_check_large_objects_and_security_no_issues():
    """Test _check_large_objects_and_security when no issues found."""
    bucket_analysis = {
        "large_objects": [],
        "public_access": False,
    }
    result = _check_large_objects_and_security(bucket_analysis)
    assert_equal(result, [])


def test_check_large_objects_and_security_with_large_objects():
    """Test _check_large_objects_and_security recommends optimization for large objects."""
    bucket_analysis = {
        "large_objects": [
            {"size_bytes": 1024**3},
            {"size_bytes": 2 * 1024**3},
        ],
        "public_access": False,
    }
    with patch(
        "cost_toolkit.scripts.audit.s3_audit.recommendations.format_bytes",
        return_value="3.00 GB",
    ):
        result = _check_large_objects_and_security(bucket_analysis)
        assert_equal(len(result), 1)
        assert_equal(result[0]["type"], "large_object_optimization")
        assert "2 large objects" in result[0]["description"]
        assert "3.00 GB" in result[0]["description"]


def test_check_large_objects_and_security_with_public_access():
    """Test _check_large_objects_and_security recommends restricting public access."""
    bucket_analysis = {
        "large_objects": [],
        "public_access": True,
    }
    result = _check_large_objects_and_security(bucket_analysis)
    assert_equal(len(result), 1)
    assert_equal(result[0]["type"], "security_optimization")
    assert "public access" in result[0]["description"]


def test_check_large_objects_and_security_both_issues():
    """Test _check_large_objects_and_security with both large objects and public access."""
    bucket_analysis = {
        "large_objects": [{"size_bytes": 1024**3}],
        "public_access": True,
    }
    with patch(
        "cost_toolkit.scripts.audit.s3_audit.recommendations.format_bytes",
        return_value="1.00 GB",
    ):
        result = _check_large_objects_and_security(bucket_analysis)
        assert_equal(len(result), 2)
        assert_equal(result[0]["type"], "large_object_optimization")
        assert_equal(result[1]["type"], "security_optimization")


def test_generate_optimization_recommendations_comprehensive():
    """Test generate_optimization_recommendations combines all checks."""
    bucket_analysis = {
        "storage_classes": {"STANDARD": {"count": 10, "size_bytes": 10 * 1024**3}},
        "old_objects": [
            {"storage_class": "STANDARD", "age_days": 60, "size_bytes": 1024**3},
        ],
        "lifecycle_policy": False,
        "versioning_enabled": True,
        "large_objects": [{"size_bytes": 1024**3}],
        "public_access": True,
    }
    with (
        patch(
            "cost_toolkit.scripts.audit.s3_audit.recommendations._check_storage_class_optimization",
            return_value=[{"type": "storage_class_optimization"}],
        ),
        patch(
            "cost_toolkit.scripts.audit.s3_audit.recommendations._check_lifecycle_and_versioning",
            return_value=[{"type": "lifecycle_policy"}, {"type": "versioning_optimization"}],
        ),
        patch(
            "cost_toolkit.scripts.audit.s3_audit.recommendations._check_large_objects_and_security",
            return_value=[{"type": "large_object_optimization"}, {"type": "security_optimization"}],
        ),
    ):
        result = generate_optimization_recommendations(bucket_analysis)
        assert_equal(len(result), 5)
        assert_equal(result[0]["type"], "storage_class_optimization")
        assert_equal(result[1]["type"], "lifecycle_policy")
        assert_equal(result[2]["type"], "versioning_optimization")
        assert_equal(result[3]["type"], "large_object_optimization")
        assert_equal(result[4]["type"], "security_optimization")


def test_generate_optimization_recommendations_empty():
    """Test generate_optimization_recommendations with no issues."""
    bucket_analysis = {
        "storage_classes": {"GLACIER": {"count": 5, "size_bytes": 1024**3}},
        "old_objects": [],
        "lifecycle_policy": True,
        "versioning_enabled": False,
        "large_objects": [],
        "public_access": False,
    }
    result = generate_optimization_recommendations(bucket_analysis)
    assert_equal(result, [])


def test_create_ia_recommendation_empty_old_objects():
    """Test _create_ia_recommendation with empty old_objects list."""
    old_objects = []
    result = _create_ia_recommendation(old_objects)
    assert_equal(result, None)


def test_create_glacier_recommendation_empty_old_objects():
    """Test _create_glacier_recommendation with empty old_objects list."""
    old_objects = []
    result = _create_glacier_recommendation(old_objects)
    assert_equal(result, None)


def test_check_storage_class_optimization_zero_size_bytes():
    """Test _check_storage_class_optimization when STANDARD storage has zero bytes."""
    bucket_analysis = {
        "storage_classes": {"STANDARD": {"count": 0, "size_bytes": 0}},
        "old_objects": [],
    }
    result = _check_storage_class_optimization(bucket_analysis)
    assert_equal(result, [])


def test_check_storage_class_optimization_missing_standard_key():
    """Test _check_storage_class_optimization when STANDARD key is missing."""
    bucket_analysis = {
        "storage_classes": {"GLACIER": {"count": 5, "size_bytes": 1024**3}},
        "old_objects": [],
    }
    result = _check_storage_class_optimization(bucket_analysis)
    assert_equal(result, [])
