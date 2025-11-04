"""Unit tests for StatusReporter class from migration_orchestrator.py

Tests cover:
- Status display for all migration phases (scanning, glacier_restore, syncing, complete)
- Overall summary and bucket progress reporting
- Individual bucket details display
"""

from unittest import mock

import pytest

from migration_orchestrator import StatusReporter
from migration_state_v2 import Phase


class TestStatusReporter:
    """Tests for StatusReporter class"""

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock()

    @pytest.fixture
    def reporter(self, mock_state):
        """Create StatusReporter instance"""
        return StatusReporter(mock_state)

    def test_show_status_scanning_phase(self, reporter, mock_state):
        """Test show_status for SCANNING phase"""
        mock_state.get_current_phase.return_value = Phase.SCANNING
        mock_state.get_all_buckets.return_value = []
        mock_state.get_scan_summary.return_value = {
            "bucket_count": 0,
            "total_files": 0,
            "total_size": 0,
        }

        with mock.patch("builtins.print") as mock_print:
            reporter.show_status()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "MIGRATION STATUS" in printed_text
        assert "scanning" in printed_text.lower()

    def test_show_status_glacier_restore_phase_shows_summary(self, reporter, mock_state):
        """Test show_status for GLACIER_RESTORE phase shows scan summary"""
        mock_state.get_current_phase.return_value = Phase.GLACIER_RESTORE
        mock_state.get_all_buckets.return_value = ["bucket-1", "bucket-2"]
        mock_state.get_scan_summary.return_value = {
            "bucket_count": 2,
            "total_files": 1000,
            "total_size": 10737418240,
        }
        mock_state.get_completed_buckets_for_phase.return_value = []

        bucket_infos = [
            {
                "file_count": 500,
                "total_size": 5368709120,
                "sync_complete": False,
                "verify_complete": False,
                "delete_complete": False,
            },
            {
                "file_count": 500,
                "total_size": 5368709120,
                "sync_complete": False,
                "verify_complete": False,
                "delete_complete": False,
            },
        ]
        mock_state.get_bucket_info.side_effect = bucket_infos

        with mock.patch("builtins.print") as mock_print:
            reporter.show_status()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "Overall Summary" in printed_text
        assert "Total Buckets: 2" in printed_text
        assert "Total Files: 1,000" in printed_text

    def test_show_status_shows_bucket_progress(self, reporter, mock_state):
        """Test show_status displays bucket progress"""
        mock_state.get_current_phase.return_value = Phase.SYNCING
        mock_state.get_all_buckets.return_value = ["bucket-1", "bucket-2", "bucket-3"]
        mock_state.get_scan_summary.return_value = {
            "bucket_count": 3,
            "total_files": 1500,
            "total_size": 15000000000,
        }
        mock_state.get_completed_buckets_for_phase.return_value = ["bucket-1"]

        bucket_infos = [
            {
                "file_count": 500,
                "total_size": 5000000000,
                "sync_complete": True,
                "verify_complete": True,
                "delete_complete": True,
            },
            {
                "file_count": 500,
                "total_size": 5000000000,
                "sync_complete": False,
                "verify_complete": False,
                "delete_complete": False,
            },
            {
                "file_count": 500,
                "total_size": 5000000000,
                "sync_complete": False,
                "verify_complete": False,
                "delete_complete": False,
            },
        ]
        mock_state.get_bucket_info.side_effect = bucket_infos

        with mock.patch("builtins.print") as mock_print:
            reporter.show_status()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "Bucket Progress" in printed_text
        assert "Completed: 1/3" in printed_text

    def test_show_status_displays_bucket_details(self, reporter, mock_state):
        """Test show_status shows individual bucket details"""
        mock_state.get_current_phase.return_value = Phase.SYNCING
        mock_state.get_all_buckets.return_value = ["bucket-1"]
        mock_state.get_scan_summary.return_value = {
            "bucket_count": 1,
            "total_files": 100,
            "total_size": 1000000,
        }
        mock_state.get_completed_buckets_for_phase.return_value = []

        mock_state.get_bucket_info.return_value = {
            "file_count": 100,
            "total_size": 1000000,
            "sync_complete": True,
            "verify_complete": False,
            "delete_complete": False,
        }

        with mock.patch("builtins.print") as mock_print:
            reporter.show_status()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "bucket-1" in printed_text
        assert "100" in printed_text

    def test_show_status_no_buckets(self, reporter, mock_state):
        """Test show_status when no buckets exist"""
        mock_state.get_current_phase.return_value = Phase.SCANNING
        mock_state.get_all_buckets.return_value = []
        mock_state.get_scan_summary.return_value = {
            "bucket_count": 0,
            "total_files": 0,
            "total_size": 0,
        }

        with mock.patch("builtins.print") as mock_print:
            reporter.show_status()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "MIGRATION STATUS" in printed_text

    def test_show_status_complete_phase(self, reporter, mock_state):
        """Test show_status for COMPLETE phase"""
        mock_state.get_current_phase.return_value = Phase.COMPLETE
        mock_state.get_all_buckets.return_value = ["bucket-1"]
        mock_state.get_scan_summary.return_value = {
            "bucket_count": 1,
            "total_files": 100,
            "total_size": 1000000,
        }
        mock_state.get_completed_buckets_for_phase.return_value = ["bucket-1"]
        mock_state.get_bucket_info.return_value = {
            "file_count": 100,
            "total_size": 1000000,
            "sync_complete": True,
            "verify_complete": True,
            "delete_complete": True,
        }

        with mock.patch("builtins.print") as mock_print:
            reporter.show_status()

        printed_text = " ".join([str(call) for call in mock_print.call_args_list])
        assert "MIGRATION STATUS" in printed_text
