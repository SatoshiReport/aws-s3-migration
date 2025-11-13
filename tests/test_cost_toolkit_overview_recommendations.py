"""Tests for cost_toolkit/overview/recommendations.py module."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from cost_toolkit.overview.recommendations import (
    _add_accelerator_recommendations,
    _add_database_recommendations,
    _add_ec2_recommendations,
    _add_lightsail_recommendations,
    _add_storage_recommendations,
    _add_vpc_recommendations,
    get_completed_cleanups,
)


def test_get_completed_cleanups_file_exists():
    """Test get_completed_cleanups when cleanup log exists."""
    log_data = {
        "cleanup_actions": [
            {"service": "lightsail", "status": "completed"},
            {"service": "rds", "status": "pending"},
            {"service": "ec2", "status": "completed"},
        ]
    }

    with patch("builtins.open", mock_open(read_data=json.dumps(log_data))):
        with patch("os.path.exists", return_value=True):
            result = get_completed_cleanups()

            assert "lightsail" in result
            assert "ec2" in result
            assert "rds" not in result


def test_get_completed_cleanups_file_not_exists():
    """Test get_completed_cleanups when cleanup log doesn't exist."""
    with patch("os.path.exists", return_value=False):
        result = get_completed_cleanups()

        assert isinstance(result, set)
        assert len(result) == 0


def test_get_completed_cleanups_invalid_json():
    """Test get_completed_cleanups handles invalid JSON."""
    with patch("builtins.open", mock_open(read_data="invalid json")):
        with patch("os.path.exists", return_value=True):
            result = get_completed_cleanups()

            assert isinstance(result, set)


def test_add_storage_recommendations():
    """Test _add_storage_recommendations adds correct messages."""
    recommendations = []
    _add_storage_recommendations(recommendations, "S3", 100.50, 25.5)

    assert len(recommendations) == 3
    assert "S3" in recommendations[0]
    assert "100.50" in recommendations[0]
    assert "lifecycle" in recommendations[1].lower()
    assert "Glacier" in recommendations[2]


def test_add_ec2_recommendations():
    """Test _add_ec2_recommendations adds correct messages."""
    recommendations = []
    _add_ec2_recommendations(recommendations, "EC2", 200.00, 40.0)

    assert len(recommendations) == 3
    assert "EC2" in recommendations[0]
    assert "200.00" in recommendations[0]
    assert "Reserved" in recommendations[1] or "Savings Plans" in recommendations[1]


def test_add_database_recommendations():
    """Test _add_database_recommendations adds correct messages."""
    recommendations = []
    _add_database_recommendations(recommendations, "RDS", 150.75, 30.5)

    assert len(recommendations) == 3
    assert "RDS" in recommendations[0]
    assert "150.75" in recommendations[0]
    assert "Aurora" in recommendations[1] or "Serverless" in recommendations[1]


def test_add_lightsail_recommendations_completed():
    """Test _add_lightsail_recommendations when cleanup is completed."""
    recommendations = []
    completed_cleanups = {"lightsail"}

    _add_lightsail_recommendations(recommendations, "Lightsail", 50.00, 10.0, completed_cleanups)

    assert len(recommendations) == 3
    assert "✅" in recommendations[0]
    assert "previously completed" in recommendations[1].lower()


def test_add_lightsail_recommendations_not_completed():
    """Test _add_lightsail_recommendations when cleanup is not completed."""
    recommendations = []
    completed_cleanups = set()

    _add_lightsail_recommendations(recommendations, "Lightsail", 50.00, 10.0, completed_cleanups)

    assert len(recommendations) == 3
    assert "💡" in recommendations[0]
    assert "cleanup.py" in recommendations[2]


def test_add_accelerator_recommendations():
    """Test _add_accelerator_recommendations adds correct messages."""
    recommendations = []
    _add_accelerator_recommendations(recommendations, "Global Accelerator", 75.00, 15.0)

    assert len(recommendations) == 3
    assert "Global Accelerator" in recommendations[0]
    assert "75.00" in recommendations[0]
    assert "listener" in recommendations[1].lower() or "accelerator" in recommendations[1].lower()


def test_add_vpc_recommendations():
    """Test _add_vpc_recommendations adds correct messages."""
    recommendations = []
    _add_vpc_recommendations(recommendations, "VPC", 30.00, 6.0)

    assert len(recommendations) == 3
    assert "VPC" in recommendations[0]
    assert "30.00" in recommendations[0]
    assert "NAT" in recommendations[1] or "Elastic IP" in recommendations[1]
