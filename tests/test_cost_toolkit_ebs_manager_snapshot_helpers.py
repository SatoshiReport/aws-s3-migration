"""Tests for cost_toolkit/scripts/management/ebs_manager/snapshot.py - helper functions"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from cost_toolkit.scripts.management.ebs_manager.snapshot import (
    SnapshotCreationError,
    VolumeNotFoundError,
    VolumeRetrievalError,
    _create_snapshot_tags,
    _generate_snapshot_description,
)
from tests.assertions import assert_equal


# Exception class tests
def test_volume_not_found_error_message():
    """Test VolumeNotFoundError generates correct error message."""
    error = VolumeNotFoundError("vol-1234567890abcdef0")
    assert_equal(
        str(error),
        "Volume vol-1234567890abcdef0 not found in any region",
    )


def test_volume_retrieval_error_message():
    """Test VolumeRetrievalError generates correct error message."""
    original_error = Exception("Network timeout")
    error = VolumeRetrievalError("vol-1234567890abcdef0", original_error)
    assert_equal(
        str(error),
        "Error retrieving volume vol-1234567890abcdef0: Network timeout",
    )


def test_snapshot_creation_error_message():
    """Test SnapshotCreationError generates correct error message."""
    original_error = Exception("Insufficient permissions")
    error = SnapshotCreationError("vol-1234567890abcdef0", original_error)
    assert_equal(
        str(error),
        "Error creating snapshot for volume vol-1234567890abcdef0: Insufficient permissions",
    )


# Helper function tests
def test_generate_snapshot_description():
    """Test _generate_snapshot_description creates formatted description."""
    with patch("cost_toolkit.scripts.management.ebs_manager.snapshot.datetime") as mock_dt:
        mock_now = datetime(2025, 3, 15, 14, 30, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = mock_now

        result = _generate_snapshot_description("my-volume", "vol-1234567890abcdef0", 100)

        assert_equal(
            result,
            "Snapshot of my-volume (vol-1234567890abcdef0) - 100GB - 2025-03-15 14:30 UTC",
        )


def test_generate_snapshot_description_unnamed_volume():
    """Test _generate_snapshot_description with unnamed volume."""
    with patch("cost_toolkit.scripts.management.ebs_manager.snapshot.datetime") as mock_dt:
        mock_now = datetime(2025, 3, 15, 14, 30, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = mock_now

        result = _generate_snapshot_description("Unnamed", "vol-abc123", 50)

        assert_equal(
            result,
            "Snapshot of Unnamed (vol-abc123) - 50GB - 2025-03-15 14:30 UTC",
        )


def test_create_snapshot_tags_with_name():
    """Test _create_snapshot_tags creates correct tags with Name tag."""
    with patch("cost_toolkit.scripts.management.ebs_manager.snapshot.datetime") as mock_dt:
        mock_now = datetime(2025, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = mock_now

        volume_tags = {
            "Name": "production-db",
            "Environment": "production",
            "Owner": "platform-team",
        }

        result = _create_snapshot_tags(volume_tags, "vol-1234567890abcdef0")

        expected_tags = [
            {"Key": "Name", "Value": "production-db-snapshot"},
            {"Key": "Environment", "Value": "production"},
            {"Key": "Owner", "Value": "platform-team"},
            {"Key": "SourceVolume", "Value": "vol-1234567890abcdef0"},
            {"Key": "CreatedBy", "Value": "aws_ebs_volume_manager"},
            {"Key": "CreatedDate", "Value": "2025-03-15"},
        ]

        assert_equal(result, expected_tags)


def test_create_snapshot_tags_without_name():
    """Test _create_snapshot_tags creates correct tags without Name tag."""
    with patch("cost_toolkit.scripts.management.ebs_manager.snapshot.datetime") as mock_dt:
        mock_now = datetime(2025, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = mock_now

        volume_tags = {
            "Environment": "staging",
            "CostCenter": "engineering",
        }

        result = _create_snapshot_tags(volume_tags, "vol-abc123")

        expected_tags = [
            {"Key": "Environment", "Value": "staging"},
            {"Key": "CostCenter", "Value": "engineering"},
            {"Key": "SourceVolume", "Value": "vol-abc123"},
            {"Key": "CreatedBy", "Value": "aws_ebs_volume_manager"},
            {"Key": "CreatedDate", "Value": "2025-03-15"},
        ]

        assert_equal(result, expected_tags)


def test_create_snapshot_tags_empty_tags():
    """Test _create_snapshot_tags with empty volume tags."""
    with patch("cost_toolkit.scripts.management.ebs_manager.snapshot.datetime") as mock_dt:
        mock_now = datetime(2025, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = mock_now

        volume_tags = {}

        result = _create_snapshot_tags(volume_tags, "vol-xyz789")

        expected_tags = [
            {"Key": "SourceVolume", "Value": "vol-xyz789"},
            {"Key": "CreatedBy", "Value": "aws_ebs_volume_manager"},
            {"Key": "CreatedDate", "Value": "2025-03-15"},
        ]

        assert_equal(result, expected_tags)
