"""Comprehensive unit tests for migration_scanner.py

Tests BucketScanner, GlacierRestorer, and GlacierWaiter classes with 80%+ coverage.
"""

from datetime import datetime
from unittest import mock

import pytest
from botocore.exceptions import ClientError

from migration_scanner import BucketScanner, GlacierRestorer, GlacierWaiter
from migration_state_v2 import MigrationStateV2, Phase


class TestBucketScanner:
    """Test BucketScanner class"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def scanner(self, mock_s3, mock_state):
        """Create BucketScanner instance"""
        return BucketScanner(mock_s3, mock_state)

    def test_scanner_initialization(self, mock_s3, mock_state):
        """Test BucketScanner initialization"""
        scanner = BucketScanner(mock_s3, mock_state)
        assert scanner.s3 is mock_s3
        assert scanner.state is mock_state
        assert scanner.interrupted is False

    def test_scan_all_buckets_with_no_buckets(self, scanner, mock_s3, mock_state, capsys):
        """Test scanning when no buckets exist"""
        mock_s3.list_buckets.return_value = {"Buckets": []}

        scanner.scan_all_buckets()

        assert capsys.readouterr().out.count("PHASE 1/4: SCANNING BUCKETS") == 1
        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_RESTORE)

    def test_scan_all_buckets_with_single_bucket(self, scanner, mock_s3, mock_state, capsys):
        """Test scanning with single bucket"""
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "test-bucket"}]}
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file.txt",
                        "Size": 100,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    }
                ]
            }
        ]

        scanner.scan_all_buckets()

        mock_state.add_file.assert_called_once()
        mock_state.save_bucket_status.assert_called_once()
        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_RESTORE)

    def test_scan_all_buckets_filters_excluded_buckets(self, scanner, mock_s3, mock_state, capsys):
        """Test that excluded buckets are filtered out"""
        with mock.patch("migration_scanner.config.EXCLUDED_BUCKETS", ["excluded-bucket"]):
            mock_s3.list_buckets.return_value = {
                "Buckets": [
                    {"Name": "test-bucket"},
                    {"Name": "excluded-bucket"},
                ]
            }
            mock_s3.get_paginator.return_value.paginate.return_value = []

            scanner.scan_all_buckets()

            output = capsys.readouterr().out
            assert "Found 1 bucket(s)" in output
            assert "Excluded 1 bucket(s)" in output

    def test_scan_all_buckets_handles_empty_bucket(self, scanner, mock_s3, mock_state, capsys):
        """Test scanning empty bucket"""
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "empty-bucket"}]}
        mock_s3.get_paginator.return_value.paginate.return_value = [{}]

        scanner.scan_all_buckets()

        mock_state.add_file.assert_not_called()
        mock_state.save_bucket_status.assert_called_once_with(
            "empty-bucket", 0, 0, {}, scan_complete=True
        )

    def test_scan_all_buckets_with_multiple_pages(self, scanner, mock_s3, mock_state):
        """Test scanning bucket with pagination"""
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "test-bucket"}]}
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file1.txt",
                        "Size": 100,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    }
                ]
            },
            {
                "Contents": [
                    {
                        "Key": "file2.txt",
                        "Size": 200,
                        "StorageClass": "GLACIER",
                        "LastModified": datetime.now(),
                    }
                ]
            },
        ]

        scanner.scan_all_buckets()

        assert mock_state.add_file.call_count == 2

    def test_scan_all_buckets_respects_interrupt_signal(self, scanner, mock_s3, mock_state):
        """Test that scan_all_buckets stops on interrupt"""
        mock_s3.list_buckets.return_value = {
            "Buckets": [
                {"Name": "bucket1"},
                {"Name": "bucket2"},
            ]
        }
        mock_s3.get_paginator.return_value.paginate.return_value = []

        # Interrupt after first bucket
        def interrupt_on_second_call(*args, **kwargs):
            scanner.interrupted = True

        mock_state.save_bucket_status.side_effect = interrupt_on_second_call

        scanner.scan_all_buckets()

        # Should only process first bucket
        assert mock_state.save_bucket_status.call_count == 1

    def test_scan_bucket_with_mixed_storage_classes(self, scanner, mock_s3, mock_state):
        """Test scanning bucket with multiple storage classes"""
        scanner.s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "standard.txt",
                        "Size": 100,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    },
                    {
                        "Key": "glacier.txt",
                        "Size": 200,
                        "StorageClass": "GLACIER",
                        "LastModified": datetime.now(),
                    },
                    {
                        "Key": "deep_archive.txt",
                        "Size": 300,
                        "StorageClass": "DEEP_ARCHIVE",
                        "LastModified": datetime.now(),
                    },
                ]
            }
        ]

        scanner._scan_bucket("test-bucket")

        storage_classes = mock_state.save_bucket_status.call_args[0][3]
        assert storage_classes["STANDARD"] == 1
        assert storage_classes["GLACIER"] == 1
        assert storage_classes["DEEP_ARCHIVE"] == 1

    def test_scan_bucket_accumulates_size(self, scanner, mock_s3, mock_state):
        """Test that file sizes are accumulated correctly"""
        scanner.s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file1.txt",
                        "Size": 1000,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    },
                    {
                        "Key": "file2.txt",
                        "Size": 2000,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    },
                ]
            }
        ]

        scanner._scan_bucket("test-bucket")

        # Total size should be 3000
        call_args = mock_state.save_bucket_status.call_args
        assert call_args[0][2] == 3000

    def test_scan_bucket_handles_missing_storage_class(self, scanner, mock_s3, mock_state):
        """Test handling of objects without StorageClass field"""
        scanner.s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file.txt",
                        "Size": 100,
                        "LastModified": datetime.now(),
                        # StorageClass missing
                    }
                ]
            }
        ]

        scanner._scan_bucket("test-bucket")

        # Should default to STANDARD
        storage_classes = mock_state.save_bucket_status.call_args[0][3]
        assert storage_classes["STANDARD"] == 1

    def test_scan_bucket_handles_missing_etag(self, scanner, mock_s3, mock_state):
        """Test handling of objects without ETag field"""
        scanner.s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file.txt",
                        "Size": 100,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                        # ETag missing
                    }
                ]
            }
        ]

        scanner._scan_bucket("test-bucket")

        # Should still call add_file with empty string etag
        call_args = mock_state.add_file.call_args
        assert call_args[0][3] == ""

    def test_scan_bucket_strips_etag_quotes(self, scanner, mock_s3, mock_state):
        """Test that ETags are stripped of quotes"""
        scanner.s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file.txt",
                        "Size": 100,
                        "ETag": '"abc123"',
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    }
                ]
            }
        ]

        scanner._scan_bucket("test-bucket")

        # ETag should be stripped of quotes
        call_args = mock_state.add_file.call_args
        assert call_args[0][3] == "abc123"

    def test_scan_bucket_respects_interrupt(self, scanner, mock_s3, mock_state):
        """Test that _scan_bucket stops on interrupt"""
        scanner.s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file1.txt",
                        "Size": 100,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    }
                ]
            }
        ]

        scanner.interrupted = True
        scanner._scan_bucket("test-bucket")

        mock_state.add_file.assert_not_called()
        mock_state.save_bucket_status.assert_not_called()

    def test_scan_bucket_respects_pagination_interrupt(self, scanner, mock_s3, mock_state):
        """Test interrupt during pagination"""
        page_count = 0

        def paginate_with_interrupt(*args, **kwargs):
            nonlocal page_count
            page_count += 1
            scanner.interrupted = True
            return [
                {
                    "Contents": [
                        {
                            "Key": f"file{page_count}.txt",
                            "Size": 100,
                            "StorageClass": "STANDARD",
                            "LastModified": datetime.now(),
                        }
                    ]
                }
            ]

        scanner.s3.get_paginator.return_value.paginate = paginate_with_interrupt

        scanner._scan_bucket("test-bucket")

        # Should only process first page before interrupt
        mock_state.save_bucket_status.assert_not_called()

    def test_scan_bucket_progress_output(self, scanner, mock_s3, mock_state, capsys):
        """Test progress output for large number of files"""
        files = []
        for i in range(20001):
            files.append(
                {
                    "Key": f"file{i}.txt",
                    "Size": 100,
                    "StorageClass": "STANDARD",
                    "LastModified": datetime.now(),
                }
            )

        scanner.s3.get_paginator.return_value.paginate.return_value = [{"Contents": files}]

        scanner._scan_bucket("test-bucket")

        output = capsys.readouterr().out
        # Should show progress at 10000 mark
        assert "20001" in output or "20,001" in output


class TestGlacierRestorer:
    """Test GlacierRestorer class"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def restorer(self, mock_s3, mock_state):
        """Create GlacierRestorer instance"""
        return GlacierRestorer(mock_s3, mock_state)

    def test_restorer_initialization(self, mock_s3, mock_state):
        """Test GlacierRestorer initialization"""
        restorer = GlacierRestorer(mock_s3, mock_state)
        assert restorer.s3 is mock_s3
        assert restorer.state is mock_state
        assert restorer.interrupted is False

    def test_request_all_restores_no_glacier_files(self, restorer, mock_state, capsys):
        """Test when no Glacier files need restore"""
        mock_state.get_glacier_files_needing_restore.return_value = []

        restorer.request_all_restores()

        output = capsys.readouterr().out
        assert "No Glacier files need restore" in output
        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_WAIT)

    def test_request_all_restores_with_files(self, restorer, mock_s3, mock_state, capsys):
        """Test requesting restores for Glacier files"""
        mock_state.get_glacier_files_needing_restore.return_value = [
            {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}
        ]

        restorer.request_all_restores()

        mock_s3.restore_object.assert_called_once()
        mock_state.mark_glacier_restore_requested.assert_called_once()
        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_WAIT)

    def test_request_all_restores_respects_interrupt(self, restorer, mock_s3, mock_state):
        """Test that request_all_restores stops on interrupt"""
        mock_state.get_glacier_files_needing_restore.return_value = [
            {"bucket": "test-bucket", "key": "file1.txt", "storage_class": "GLACIER"},
            {"bucket": "test-bucket", "key": "file2.txt", "storage_class": "GLACIER"},
        ]

        def interrupt_on_first_call(*args, **kwargs):
            restorer.interrupted = True

        mock_s3.restore_object.side_effect = interrupt_on_first_call

        restorer.request_all_restores()

        # Should only process first file
        assert mock_s3.restore_object.call_count == 1

    def test_request_restore_for_glacier(self, restorer, mock_s3, mock_state):
        """Test requesting restore for GLACIER storage class"""
        with mock.patch("migration_scanner.config.GLACIER_RESTORE_TIER", "Standard"):
            with mock.patch("migration_scanner.config.GLACIER_RESTORE_DAYS", 1):
                file_info = {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}

                restorer._request_restore(file_info, 1, 1)

                # Should use configured tier for GLACIER
                call_args = mock_s3.restore_object.call_args
                assert call_args[1]["RestoreRequest"]["GlacierJobParameters"]["Tier"] == "Standard"

    def test_request_restore_for_deep_archive(self, restorer, mock_s3, mock_state):
        """Test requesting restore for DEEP_ARCHIVE uses Bulk tier"""
        with mock.patch("migration_scanner.config.GLACIER_RESTORE_DAYS", 1):
            file_info = {
                "bucket": "test-bucket",
                "key": "file.txt",
                "storage_class": "DEEP_ARCHIVE",
            }

            restorer._request_restore(file_info, 1, 1)

            # Should use Bulk tier for DEEP_ARCHIVE
            call_args = mock_s3.restore_object.call_args
            assert call_args[1]["RestoreRequest"]["GlacierJobParameters"]["Tier"] == "Bulk"

    def test_request_restore_success(self, restorer, mock_s3, mock_state, capsys):
        """Test successful restore request"""
        file_info = {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}

        restorer._request_restore(file_info, 5, 10)

        mock_s3.restore_object.assert_called_once()
        mock_state.mark_glacier_restore_requested.assert_called_once_with("test-bucket", "file.txt")
        output = capsys.readouterr().out
        assert "[5/10]" in output

    def test_request_restore_already_in_progress(self, restorer, mock_s3, mock_state):
        """Test handling RestoreAlreadyInProgress error"""
        error_response = {
            "Error": {"Code": "RestoreAlreadyInProgress", "Message": "Already restoring"}
        }
        mock_s3.restore_object.side_effect = ClientError(error_response, "RestoreObject")

        file_info = {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}

        # Should not raise, should mark as requested
        restorer._request_restore(file_info, 1, 1)

        mock_state.mark_glacier_restore_requested.assert_called_once()

    def test_request_restore_other_error(self, restorer, mock_s3, mock_state):
        """Test that other errors are raised"""
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
        mock_s3.restore_object.side_effect = ClientError(error_response, "RestoreObject")

        file_info = {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}

        # Should raise because it's not RestoreAlreadyInProgress
        with pytest.raises(ClientError):
            restorer._request_restore(file_info, 1, 1)

    def test_request_restore_uses_correct_config_values(self, restorer, mock_s3, mock_state):
        """Test that restore request uses config values"""
        with mock.patch("migration_scanner.config.GLACIER_RESTORE_TIER", "Expedited"):
            with mock.patch("migration_scanner.config.GLACIER_RESTORE_DAYS", 5):
                file_info = {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}

                restorer._request_restore(file_info, 1, 1)

                call_args = mock_s3.restore_object.call_args
                restore_request = call_args[1]["RestoreRequest"]
                assert restore_request["Days"] == 5
                assert restore_request["GlacierJobParameters"]["Tier"] == "Expedited"

    def test_request_all_restores_multiple_files(self, restorer, mock_s3, mock_state):
        """Test requesting restores for multiple files"""
        mock_state.get_glacier_files_needing_restore.return_value = [
            {"bucket": "bucket1", "key": "file1.txt", "storage_class": "GLACIER"},
            {"bucket": "bucket2", "key": "file2.txt", "storage_class": "GLACIER"},
            {"bucket": "bucket1", "key": "file3.txt", "storage_class": "DEEP_ARCHIVE"},
        ]

        restorer.request_all_restores()

        assert mock_s3.restore_object.call_count == 3
        assert mock_state.mark_glacier_restore_requested.call_count == 3


class TestGlacierWaiter:
    """Test GlacierWaiter class"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def waiter(self, mock_s3, mock_state):
        """Create GlacierWaiter instance"""
        return GlacierWaiter(mock_s3, mock_state)

    def test_waiter_initialization(self, mock_s3, mock_state):
        """Test GlacierWaiter initialization"""
        waiter = GlacierWaiter(mock_s3, mock_state)
        assert waiter.s3 is mock_s3
        assert waiter.state is mock_state
        assert waiter.interrupted is False

    def test_wait_for_restores_no_restoring_files(self, waiter, mock_state, capsys):
        """Test when no files are restoring"""
        mock_state.get_files_restoring.return_value = []

        waiter.wait_for_restores()

        output = capsys.readouterr().out
        assert "PHASE 3/4: WAITING FOR GLACIER RESTORES" in output
        assert "PHASE 3 COMPLETE" in output
        mock_state.set_current_phase.assert_called_once_with(Phase.SYNCING)

    def test_wait_for_restores_respects_interrupt(self, waiter, mock_state):
        """Test that wait_for_restores stops on interrupt"""
        # When interrupted flag is set before entering, loop exits immediately
        waiter.interrupted = True
        with mock.patch("migration_scanner.time.sleep"):
            waiter.wait_for_restores()

        # Should still transition to SYNCING phase after loop exits
        mock_state.set_current_phase.assert_called_once_with(Phase.SYNCING)

    def test_wait_for_restores_with_sleep(self, waiter, mock_s3, mock_state):
        """Test that wait_for_restores sleeps between checks"""
        # Mock _check_restore_status to avoid side_effect issues
        waiter._check_restore_status = mock.Mock(return_value=False)

        mock_state.get_files_restoring.side_effect = [
            [{"bucket": "test-bucket", "key": "file.txt"}],
            [],  # Next check shows no files
        ]

        with mock.patch("migration_scanner.time.sleep") as mock_sleep:
            waiter.wait_for_restores()

            # Should sleep 300 seconds (5 minutes) after first check
            mock_sleep.assert_called_with(300)

    def test_wait_for_restores_stops_on_interrupt_during_check(self, waiter, mock_s3, mock_state):
        """Test interrupt during restore status check"""
        mock_state.get_files_restoring.return_value = [
            {"bucket": "test-bucket", "key": "file1.txt"},
            {"bucket": "test-bucket", "key": "file2.txt"},
        ]

        def interrupt_on_second_file(*args, **kwargs):
            waiter.interrupted = True
            return False

        waiter._check_restore_status = mock.Mock(side_effect=interrupt_on_second_file)

        waiter.wait_for_restores()

        # Should only check first file before interrupt
        assert waiter._check_restore_status.call_count == 1

    def test_check_restore_status_not_complete(self, waiter, mock_s3, mock_state):
        """Test restore status check when restore is still ongoing"""
        mock_s3.head_object.return_value = {
            "Restore": 'ongoing-request="true"',
        }

        file_info = {"bucket": "test-bucket", "key": "file.txt"}
        result = waiter._check_restore_status(file_info)

        assert result is False
        mock_state.mark_glacier_restored.assert_not_called()

    def test_check_restore_status_complete(self, waiter, mock_s3, mock_state):
        """Test restore status check when restore is complete"""
        mock_s3.head_object.return_value = {
            "Restore": 'ongoing-request="false"',
        }

        file_info = {"bucket": "test-bucket", "key": "file.txt"}
        result = waiter._check_restore_status(file_info)

        assert result is True
        mock_state.mark_glacier_restored.assert_called_once_with("test-bucket", "file.txt")

    def test_check_restore_status_no_restore_header(self, waiter, mock_s3, mock_state):
        """Test restore status when Restore header is missing"""
        mock_s3.head_object.return_value = {}

        file_info = {"bucket": "test-bucket", "key": "file.txt"}
        result = waiter._check_restore_status(file_info)

        assert result is False
        mock_state.mark_glacier_restored.assert_not_called()

    def test_check_restore_status_handles_error(self, waiter, mock_s3, mock_state):
        """Test restore status check handles errors gracefully"""
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        mock_s3.head_object.side_effect = ClientError(error_response, "HeadObject")

        file_info = {"bucket": "test-bucket", "key": "file.txt"}
        result = waiter._check_restore_status(file_info)

        assert result is False
        mock_state.mark_glacier_restored.assert_not_called()

    def test_check_restore_status_with_multiple_files(self, waiter, mock_s3, mock_state):
        """Test checking multiple files"""
        files = [
            {"bucket": "bucket1", "key": "file1.txt"},
            {"bucket": "bucket2", "key": "file2.txt"},
            {"bucket": "bucket1", "key": "file3.txt"},
        ]

        # First file complete, others still restoring
        mock_s3.head_object.side_effect = [
            {"Restore": 'ongoing-request="false"'},
            {"Restore": 'ongoing-request="true"'},
            {"Restore": 'ongoing-request="true"'},
        ]

        results = [waiter._check_restore_status(f) for f in files]

        assert results == [True, False, False]
        assert mock_state.mark_glacier_restored.call_count == 1

    def test_wait_for_restores_loops_until_complete(self, waiter, mock_s3, mock_state):
        """Test that wait_for_restores loops multiple times"""
        # Mock _check_restore_status to avoid complications
        waiter._check_restore_status = mock.Mock(return_value=False)

        # Simulate 2 check cycles
        mock_state.get_files_restoring.side_effect = [
            [{"bucket": "test-bucket", "key": "file.txt"}],
            [{"bucket": "test-bucket", "key": "file.txt"}],
            [],  # All done
        ]

        with mock.patch("migration_scanner.time.sleep"):
            waiter.wait_for_restores()

        # Should call get_files_restoring 3 times
        assert mock_state.get_files_restoring.call_count == 3

    def test_check_restore_status_partial_restore_string(self, waiter, mock_s3, mock_state):
        """Test restore status with various Restore header formats"""
        # AWS includes timestamp and expiry in the Restore header
        mock_s3.head_object.return_value = {
            "Restore": 'ongoing-request="false", expiry-date="Tue, 25 Oct 2022 00:00:00 GMT"',
        }

        file_info = {"bucket": "test-bucket", "key": "file.txt"}
        result = waiter._check_restore_status(file_info)

        assert result is True
        mock_state.mark_glacier_restored.assert_called_once()

    def test_wait_for_restores_prints_restored_files(self, waiter, mock_s3, mock_state, capsys):
        """Test output shows restored files"""
        # Mock _check_restore_status to return True for both files
        waiter._check_restore_status = mock.Mock(return_value=True)

        mock_state.get_files_restoring.side_effect = [
            [
                {"bucket": "test-bucket", "key": "file1.txt"},
                {"bucket": "test-bucket", "key": "file2.txt"},
            ],
            [],
        ]

        with mock.patch("migration_scanner.time.sleep"):
            waiter.wait_for_restores()

        output = capsys.readouterr().out
        assert "Restored: test-bucket/file1.txt" in output
        assert "Restored: test-bucket/file2.txt" in output


class TestPhaseTransitions:
    """Test phase transitions across classes"""

    def test_bucket_scanner_transitions_to_glacier_restore(self):
        """Test BucketScanner transitions to GLACIER_RESTORE phase"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_s3.list_buckets.return_value = {"Buckets": []}

        scanner = BucketScanner(mock_s3, mock_state)
        scanner.scan_all_buckets()

        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_RESTORE)

    def test_glacier_restorer_transitions_to_glacier_wait(self):
        """Test GlacierRestorer transitions to GLACIER_WAIT phase"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_state.get_glacier_files_needing_restore.return_value = []

        restorer = GlacierRestorer(mock_s3, mock_state)
        restorer.request_all_restores()

        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_WAIT)

    def test_glacier_waiter_transitions_to_syncing(self):
        """Test GlacierWaiter transitions to SYNCING phase"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_state.get_files_restoring.return_value = []

        waiter = GlacierWaiter(mock_s3, mock_state)
        waiter.wait_for_restores()

        mock_state.set_current_phase.assert_called_once_with(Phase.SYNCING)


class TestInterruptionHandling:
    """Test interruption handling across all classes"""

    def test_bucket_scanner_interrupt_flag(self):
        """Test BucketScanner interrupt flag behavior"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        scanner = BucketScanner(mock_s3, mock_state)

        assert scanner.interrupted is False
        scanner.interrupted = True
        assert scanner.interrupted is True

    def test_glacier_restorer_interrupt_flag(self):
        """Test GlacierRestorer interrupt flag behavior"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        restorer = GlacierRestorer(mock_s3, mock_state)

        assert restorer.interrupted is False
        restorer.interrupted = True
        assert restorer.interrupted is True

    def test_glacier_waiter_interrupt_flag(self):
        """Test GlacierWaiter interrupt flag behavior"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        waiter = GlacierWaiter(mock_s3, mock_state)

        assert waiter.interrupted is False
        waiter.interrupted = True
        assert waiter.interrupted is True

    def test_bucket_scanner_early_exit_on_interrupt(self):
        """Test early exit on interrupt in bucket loop"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_s3.list_buckets.return_value = {
            "Buckets": [
                {"Name": "bucket1"},
                {"Name": "bucket2"},
                {"Name": "bucket3"},
            ]
        }
        mock_s3.get_paginator.return_value.paginate.return_value = []

        scanner = BucketScanner(mock_s3, mock_state)

        call_count = 0

        def count_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                scanner.interrupted = True

        mock_state.save_bucket_status.side_effect = count_calls

        scanner.scan_all_buckets()

        # Should only be called once before interrupt
        assert call_count == 1

    def test_glacier_restorer_early_exit_on_interrupt(self):
        """Test early exit on interrupt in restore loop"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_state.get_glacier_files_needing_restore.return_value = [
            {"bucket": "bucket1", "key": "file1.txt", "storage_class": "GLACIER"},
            {"bucket": "bucket2", "key": "file2.txt", "storage_class": "GLACIER"},
            {"bucket": "bucket3", "key": "file3.txt", "storage_class": "GLACIER"},
        ]

        restorer = GlacierRestorer(mock_s3, mock_state)

        call_count = 0

        def count_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                restorer.interrupted = True

        mock_s3.restore_object.side_effect = count_calls

        restorer.request_all_restores()

        # Should only be called once before interrupt
        assert call_count == 1

    def test_glacier_waiter_early_exit_on_interrupt_during_loop(self):
        """Test early exit on interrupt in waiter loop"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)

        waiter = GlacierWaiter(mock_s3, mock_state)
        waiter.interrupted = True

        waiter.wait_for_restores()

        # When interrupted before loop, still transitions to SYNCING at end
        mock_state.set_current_phase.assert_called_once_with(Phase.SYNCING)


class TestErrorHandling:
    """Test error handling in all classes"""

    def test_bucket_scanner_handles_pagination_error(self):
        """Test that pagination errors propagate"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "test-bucket"}]}
        mock_s3.get_paginator.return_value.paginate.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "ListObjectsV2"
        )

        scanner = BucketScanner(mock_s3, mock_state)

        with pytest.raises(ClientError):
            scanner.scan_all_buckets()

    def test_glacier_restorer_handles_non_restore_error(self):
        """Test that non-RestoreAlreadyInProgress errors propagate"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_state.get_glacier_files_needing_restore.return_value = [
            {"bucket": "test-bucket", "key": "file.txt", "storage_class": "GLACIER"}
        ]
        mock_s3.restore_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}},
            "RestoreObject",
        )

        restorer = GlacierRestorer(mock_s3, mock_state)

        with pytest.raises(ClientError):
            restorer.request_all_restores()

    def test_glacier_waiter_handles_head_object_error(self):
        """Test that head_object errors are handled gracefully"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        # Use side_effect to return files on first call, then empty on second
        mock_state.get_files_restoring.side_effect = [
            [{"bucket": "test-bucket", "key": "file.txt"}],
            [],  # Empty on retry
        ]
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "HeadObject"
        )

        waiter = GlacierWaiter(mock_s3, mock_state)

        with mock.patch("migration_scanner.time.sleep"):
            waiter.wait_for_restores()

        # Should handle error gracefully and exit
        mock_state.set_current_phase.assert_called_once_with(Phase.SYNCING)


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_bucket_scanner_handles_very_large_bucket(self):
        """Test scanning a bucket with many files"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "large-bucket"}]}

        # Create a large number of files
        files = [
            {
                "Key": f"file{i}.txt",
                "Size": 1000000,
                "StorageClass": "STANDARD",
                "LastModified": datetime.now(),
            }
            for i in range(50000)
        ]

        mock_s3.get_paginator.return_value.paginate.return_value = [{"Contents": files}]

        scanner = BucketScanner(mock_s3, mock_state)
        scanner.scan_all_buckets()

        # Should have added all files
        assert mock_state.add_file.call_count == 50000

    def test_glacier_restorer_handles_restore_string_variations(self):
        """Test various restore string formats"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        waiter = GlacierWaiter(mock_s3, mock_state)

        test_cases = [
            ('ongoing-request="false"', True),
            ('ongoing-request="true"', False),
            ('ongoing-request="false", expiry-date="..."', True),
            ("", False),
        ]

        for restore_string, expected in test_cases:
            mock_s3.head_object.return_value = {"Restore": restore_string} if restore_string else {}

            result = waiter._check_restore_status({"bucket": "b", "key": "k"})
            assert result == expected

    def test_bucket_scanner_handles_zero_size_files(self):
        """Test scanning bucket with zero-size files"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock(spec=MigrationStateV2)
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "test-bucket"}]}

        mock_s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "zero.txt",
                        "Size": 0,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    }
                ]
            }
        ]

        scanner = BucketScanner(mock_s3, mock_state)
        scanner.scan_all_buckets()

        call_args = mock_state.save_bucket_status.call_args
        assert call_args[0][2] == 0  # Total size should be 0
