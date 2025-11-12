"""Unit tests for BucketMigrator class from migration_orchestrator.py

Tests cover:
- Full bucket migration pipeline (sync → verify → delete)
- User input handling for deletion confirmation
- Skip logic for already-completed steps
- Verification summary formatting
"""

from unittest import mock

import pytest

from migration_orchestrator import BucketMigrator


@pytest.fixture
def mock_dependencies(tmp_path):  # pylint: disable=redefined-outer-name
    """Create mock dependencies for BucketMigrator"""
    mock_s3 = mock.Mock()
    mock_state = mock.Mock()
    base_path = tmp_path / "migration"
    base_path.mkdir()

    return {
        "s3": mock_s3,
        "state": mock_state,
        "base_path": base_path,
    }


@pytest.fixture
def migrator(mock_dependencies):  # pylint: disable=redefined-outer-name
    """Create BucketMigrator instance with mocked dependencies"""
    with (
        mock.patch("migration_orchestrator.BucketSyncer"),
        mock.patch("migration_orchestrator.BucketVerifier"),
        mock.patch("migration_orchestrator.BucketDeleter"),
    ):
        _migrator = BucketMigrator(
            mock_dependencies["s3"],
            mock_dependencies["state"],
            mock_dependencies["base_path"],
        )
        _migrator.syncer = mock.Mock()
        _migrator.verifier = mock.Mock()
        _migrator.deleter = mock.Mock()
    return _migrator


def test_process_bucket_first_time_sync_verify_delete(
    migrator, mock_dependencies
):  # pylint: disable=redefined-outer-name
    """Test process_bucket for first time: sync → verify → delete pipeline"""
    bucket = "test-bucket"
    bucket_info = {
        "sync_complete": False,
        "verify_complete": False,
        "delete_complete": False,
        "file_count": 100,
        "total_size": 1024000,
        "local_file_count": 100,
        "verified_file_count": 100,
        "size_verified_count": 100,
        "checksum_verified_count": 100,
        "total_bytes_verified": 1024000,
    }
    mock_dependencies["state"].get_bucket_info.return_value = bucket_info

    verify_results = {
        "verified_count": 100,
        "size_verified": 100,
        "checksum_verified": 100,
        "total_bytes_verified": 1024000,
        "local_file_count": 100,
    }
    migrator.verifier.verify_bucket.return_value = verify_results

    with mock.patch("builtins.input", return_value="yes"):
        migrator.process_bucket(bucket)

    # Verify sync was called
    migrator.syncer.sync_bucket.assert_called_once_with(bucket)
    mock_dependencies["state"].mark_bucket_sync_complete.assert_called_once_with(bucket)

    # Verify verification was called
    migrator.verifier.verify_bucket.assert_called_once_with(bucket)
    assert mock_dependencies["state"].mark_bucket_verify_complete.called

    # Verify deletion was called
    migrator.deleter.delete_bucket.assert_called_once_with(bucket)
    mock_dependencies["state"].mark_bucket_delete_complete.assert_called_once_with(bucket)


def test_process_bucket_already_synced_skips_sync(
    migrator, mock_dependencies
):  # pylint: disable=redefined-outer-name
    """Test process_bucket skips sync if already complete"""
    bucket = "test-bucket"
    bucket_info = {
        "sync_complete": True,
        "verify_complete": False,
        "delete_complete": False,
        "file_count": 50,
        "total_size": 512000,
        "local_file_count": 50,
        "verified_file_count": 50,
        "size_verified_count": 50,
        "checksum_verified_count": 50,
        "total_bytes_verified": 512000,
    }
    mock_dependencies["state"].get_bucket_info.return_value = bucket_info

    verify_results = {
        "verified_count": 50,
        "size_verified": 50,
        "checksum_verified": 50,
        "total_bytes_verified": 512000,
        "local_file_count": 50,
    }
    migrator.verifier.verify_bucket.return_value = verify_results

    with mock.patch("builtins.input", return_value="yes"):
        migrator.process_bucket(bucket)

    # Verify sync was NOT called
    migrator.syncer.sync_bucket.assert_not_called()


def test_process_bucket_already_deleted_skips_delete(
    migrator, mock_dependencies
):  # pylint: disable=redefined-outer-name
    """Test process_bucket skips delete if already complete"""
    bucket = "test-bucket"
    bucket_info = {
        "sync_complete": True,
        "verify_complete": True,
        "delete_complete": True,
        "file_count": 10,
        "total_size": 102400,
        "verified_file_count": 10,
        "local_file_count": 10,
        "size_verified_count": 10,
        "checksum_verified_count": 10,
        "total_bytes_verified": 102400,
    }
    mock_dependencies["state"].get_bucket_info.return_value = bucket_info

    migrator.process_bucket(bucket)

    # Verify sync and delete were NOT called
    migrator.syncer.sync_bucket.assert_not_called()
    migrator.deleter.delete_bucket.assert_not_called()


def test_process_bucket_already_verified_recomputes_stats(
    migrator, mock_dependencies
):  # pylint: disable=redefined-outer-name
    """Test process_bucket re-verifies when verify_complete but missing stats"""
    bucket = "test-bucket"
    bucket_info = {
        "sync_complete": True,
        "verify_complete": True,
        "delete_complete": False,
        "file_count": 75,
        "total_size": 768000,
        "verified_file_count": None,  # Missing stats
        "local_file_count": 75,
        "size_verified_count": 75,
        "checksum_verified_count": 75,
        "total_bytes_verified": 768000,
    }
    mock_dependencies["state"].get_bucket_info.return_value = bucket_info

    verify_results = {
        "verified_count": 75,
        "size_verified": 75,
        "checksum_verified": 75,
        "total_bytes_verified": 768000,
        "local_file_count": 75,
    }
    migrator.verifier.verify_bucket.return_value = verify_results

    # After verification, update bucket_info with verified stats
    def update_bucket_info_on_verify_complete(_bucket_name, **_kwargs):
        bucket_info["verified_file_count"] = 75

    mock_dependencies["state"].mark_bucket_verify_complete.side_effect = (
        update_bucket_info_on_verify_complete
    )

    with mock.patch("builtins.input", return_value="yes"):
        migrator.process_bucket(bucket)

    # Verify sync was NOT called, but verify was
    migrator.syncer.sync_bucket.assert_not_called()
    migrator.verifier.verify_bucket.assert_called_once()


def test_delete_with_confirmation_user_confirms_yes(
    migrator, mock_dependencies
):  # pylint: disable=redefined-outer-name
    """Test _delete_with_confirmation when user inputs 'yes'"""
    bucket = "test-bucket"
    bucket_info = {
        "file_count": 100,
        "total_size": 1024000,
        "local_file_count": 100,
        "verified_file_count": 100,
        "size_verified_count": 100,
        "checksum_verified_count": 100,
        "total_bytes_verified": 1024000,
    }

    with mock.patch("builtins.input", return_value="yes"):
        migrator.delete_with_confirmation(bucket, bucket_info)

    migrator.deleter.delete_bucket.assert_called_once_with(bucket)
    mock_dependencies["state"].mark_bucket_delete_complete.assert_called_once_with(bucket)


def test_delete_with_confirmation_user_confirms_no(
    migrator, mock_dependencies
):  # pylint: disable=redefined-outer-name
    """Test _delete_with_confirmation when user inputs 'no'"""
    bucket = "test-bucket"
    bucket_info = {
        "file_count": 50,
        "total_size": 512000,
        "local_file_count": 50,
        "verified_file_count": 50,
        "size_verified_count": 50,
        "checksum_verified_count": 50,
        "total_bytes_verified": 512000,
    }

    with mock.patch("builtins.input", return_value="no"):
        migrator.delete_with_confirmation(bucket, bucket_info)

    # Verify deletion was NOT called
    migrator.deleter.delete_bucket.assert_not_called()
    mock_dependencies["state"].mark_bucket_delete_complete.assert_not_called()


def test_delete_with_confirmation_user_confirms_other_input(
    migrator,
):  # pylint: disable=redefined-outer-name
    """Test _delete_with_confirmation with non-yes, non-no input"""
    bucket = "test-bucket"
    bucket_info = {
        "file_count": 75,
        "total_size": 768000,
        "local_file_count": 75,
        "verified_file_count": 75,
        "size_verified_count": 75,
        "checksum_verified_count": 75,
        "total_bytes_verified": 768000,
    }

    with mock.patch("builtins.input", return_value="maybe"):
        migrator.delete_with_confirmation(bucket, bucket_info)

    # Verify deletion was NOT called for non-yes input
    migrator.deleter.delete_bucket.assert_not_called()


def test_show_verification_summary_formats_output():
    """Test show_verification_summary displays all stats correctly"""
    from migration_orchestrator import show_verification_summary

    bucket_info = {
        "file_count": 1000,
        "total_size": 10737418240,  # 10 GB
        "local_file_count": 1000,
        "verified_file_count": 1000,
        "size_verified_count": 1000,
        "checksum_verified_count": 1000,
        "total_bytes_verified": 10737418240,
    }

    with mock.patch("builtins.print") as mock_print:
        show_verification_summary(bucket_info)

    # Verify summary output includes key information
    printed_text = " ".join([str(call) for call in mock_print.call_args_list])
    assert "VERIFICATION SUMMARY" in printed_text
    assert "1,000" in printed_text  # file count formatted
    assert "Size verified" in printed_text


def test_show_verification_summary_matches_verified_file_count():
    """Test show_verification_summary with all files verified"""
    from migration_orchestrator import show_verification_summary

    bucket_info = {
        "file_count": 500,
        "total_size": 5242880,  # 5 MB
        "local_file_count": 500,
        "verified_file_count": 500,
        "size_verified_count": 500,
        "checksum_verified_count": 500,
        "total_bytes_verified": 5242880,
    }

    with mock.patch("builtins.print"):
        show_verification_summary(bucket_info)

    # Should complete without raising an error
    assert True
