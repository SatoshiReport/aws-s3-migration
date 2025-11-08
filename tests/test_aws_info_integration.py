"""
Unit tests for aws_info.py - Output Format and Integration

Tests the main() function's output formatting and integration with aws_utils.
Uses pytest and unittest.mock to mock aws_utils functions.
"""

from unittest import mock

import aws_info
from tests.assertions import assert_equal

# ============================================================================
# Tests for main() - Output Format and Integration
# ============================================================================


def test_main_calls_get_aws_identity():
    """Test that main() calls get_aws_identity to retrieve identity information."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = []

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity) as mock_get_identity:
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print"):
                aws_info.main()

                # Verify get_aws_identity was called once
                mock_get_identity.assert_called_once()


def test_main_calls_list_s3_buckets():
    """Test that main() calls list_s3_buckets to retrieve bucket information."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = ["bucket-1", "bucket-2"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets) as mock_list_buckets:
            with mock.patch("builtins.print"):
                aws_info.main()

                # Verify list_s3_buckets was called once
                mock_list_buckets.assert_called_once()


def test_main_full_output_format_no_buckets():
    """Test complete output format with no buckets."""
    mock_identity = {
        "account_id": "111111111111",
        "username": "admin",
        "user_arn": "arn:aws:iam::111111111111:user/admin",
    }
    mock_buckets = []

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                # Verify print was called the correct number of times
                # Account ID, Username, User ARN, S3 Buckets header (with blank line in the string)
                assert_equal(mock_print.call_count, 4)
                calls = [call[0][0] for call in mock_print.call_args_list]
                assert calls[0] == "Account ID: 111111111111"
                assert calls[1] == "Username: admin"
                assert calls[2] == "User ARN: arn:aws:iam::111111111111:user/admin"
                assert calls[3] == "\nS3 Buckets (0):"


def test_main_full_output_format_with_buckets():
    """Test complete output format with multiple buckets."""
    mock_identity = {
        "account_id": "999999999999",
        "username": "developer",
        "user_arn": "arn:aws:iam::999999999999:user/developer",
    }
    mock_buckets = ["app-data", "logs", "backups"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                # Verify print was called for each line
                # Account ID, Username, User ARN, S3 Buckets header
                # (with blank line in the string), 3 bucket names
                assert_equal(mock_print.call_count, 7)
                calls = [call[0][0] for call in mock_print.call_args_list]
                assert calls[0] == "Account ID: 999999999999"
                assert calls[1] == "Username: developer"
                assert calls[2] == "User ARN: arn:aws:iam::999999999999:user/developer"
                assert calls[3] == "\nS3 Buckets (3):"
                assert calls[4] == "  - app-data"
                assert calls[5] == "  - logs"
                assert calls[6] == "  - backups"


def test_main_bucket_formatting_has_proper_indentation():
    """Test that bucket names are printed with proper indentation (two spaces and dash)."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = ["test-bucket"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                # Find bucket name call
                calls = [call[0][0] for call in mock_print.call_args_list]
                bucket_calls = [c for c in calls if "test-bucket" in c]
                assert len(bucket_calls) == 1
                assert bucket_calls[0] == "  - test-bucket"
                assert bucket_calls[0].startswith("  ")


def test_main_prints_blank_line_between_identity_and_buckets():
    """Test that main() prints a blank line between identity info and bucket list."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = ["bucket-1"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                calls = [call[0][0] for call in mock_print.call_args_list]
                # The blank line should appear as "\nS3 Buckets (1):"
                assert any("\nS3 Buckets" in c for c in calls)


def test_main_entry_point():
    """Test that main() can be called as an entry point."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = ["bucket-1"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print"):
                # Should execute without raising any exception
                aws_info.main()
