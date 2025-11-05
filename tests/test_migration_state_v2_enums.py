"""Unit tests for Phase enum and BucketStatus data class from migration_state_v2.py."""

import pytest

from migration_state_v2 import BucketStatus, Phase


class TestPhaseEnum:
    """Test Phase enum values and functionality."""

    def test_phase_scanning_value(self):
        """Phase.SCANNING has correct value."""
        assert Phase.SCANNING.value == "scanning"

    def test_phase_glacier_restore_value(self):
        """Phase.GLACIER_RESTORE has correct value."""
        assert Phase.GLACIER_RESTORE.value == "glacier_restore"

    def test_phase_glacier_wait_value(self):
        """Phase.GLACIER_WAIT has correct value."""
        assert Phase.GLACIER_WAIT.value == "glacier_wait"

    def test_phase_syncing_value(self):
        """Phase.SYNCING has correct value."""
        assert Phase.SYNCING.value == "syncing"

    def test_phase_verifying_value(self):
        """Phase.VERIFYING has correct value."""
        assert Phase.VERIFYING.value == "verifying"

    def test_phase_deleting_value(self):
        """Phase.DELETING has correct value."""
        assert Phase.DELETING.value == "deleting"

    def test_phase_complete_value(self):
        """Phase.COMPLETE has correct value."""
        assert Phase.COMPLETE.value == "complete"

    def test_phase_enum_from_string(self):
        """Can construct Phase from string value."""
        phase = Phase("scanning")
        assert phase == Phase.SCANNING

    def test_all_phases_exist(self):
        """All expected phases are defined."""
        expected_phases = {
            "SCANNING",
            "GLACIER_RESTORE",
            "GLACIER_WAIT",
            "SYNCING",
            "VERIFYING",
            "DELETING",
            "COMPLETE",
        }
        actual_phases = {member.name for member in Phase}
        assert expected_phases == actual_phases


class TestBucketStatus:
    """Test BucketStatus initialization and data handling."""

    def test_bucket_status_initialization_basic(self):
        """BucketStatus initializes with basic fields."""
        row = {
            "bucket": "test-bucket",
            "file_count": 100,
            "total_size": 5000,
            "storage_class_counts": '{"STANDARD": 80, "GLACIER": 20}',
            "scan_complete": 1,
            "sync_complete": 0,
            "verify_complete": 0,
            "delete_complete": 0,
        }
        status = BucketStatus(row)

        assert status.bucket == "test-bucket"
        assert status.file_count == 100
        assert status.total_size == 5000
        assert status.scan_complete is True
        assert status.sync_complete is False
        assert status.verify_complete is False
        assert status.delete_complete is False

    def test_bucket_status_storage_classes_parsing(self):
        """BucketStatus correctly parses storage class JSON."""
        row = {
            "bucket": "test-bucket",
            "file_count": 50,
            "total_size": 2000,
            "storage_class_counts": '{"STANDARD": 30, "GLACIER": 15, "DEEP_ARCHIVE": 5}',
            "scan_complete": 0,
            "sync_complete": 0,
            "verify_complete": 0,
            "delete_complete": 0,
        }
        status = BucketStatus(row)

        assert status.storage_classes == {
            "STANDARD": 30,
            "GLACIER": 15,
            "DEEP_ARCHIVE": 5,
        }

    def test_bucket_status_empty_storage_classes(self):
        """BucketStatus handles empty storage_class_counts."""
        row = {
            "bucket": "empty-bucket",
            "file_count": 0,
            "total_size": 0,
            "storage_class_counts": None,
            "scan_complete": 0,
            "sync_complete": 0,
            "verify_complete": 0,
            "delete_complete": 0,
        }
        status = BucketStatus(row)

        assert status.storage_classes == {}

    def test_bucket_status_boolean_conversion(self):
        """BucketStatus converts integer flags to booleans."""
        row = {
            "bucket": "test-bucket",
            "file_count": 10,
            "total_size": 100,
            "storage_class_counts": "{}",
            "scan_complete": 1,
            "sync_complete": 1,
            "verify_complete": 1,
            "delete_complete": 1,
        }
        status = BucketStatus(row)

        assert isinstance(status.scan_complete, bool)
        assert isinstance(status.sync_complete, bool)
        assert isinstance(status.verify_complete, bool)
        assert isinstance(status.delete_complete, bool)
        assert all(
            [
                status.scan_complete,
                status.sync_complete,
                status.verify_complete,
                status.delete_complete,
            ]
        )
