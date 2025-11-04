"""
Unit tests for aws_info.py - S3 Buckets Display

Tests the main() function's S3 bucket listing functionality.
Uses pytest and unittest.mock to mock aws_utils functions.
"""

from unittest import mock

import aws_info

# ============================================================================
# Tests for main() - S3 Buckets Display
# ============================================================================


def test_main_displays_bucket_count_zero_buckets():
    """Test that main() displays correct bucket count when there are no buckets."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = []

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                # Verify bucket count header is printed with (0)
                call_args = [str(call) for call in mock_print.call_args_list]
                assert any("S3 Buckets (0)" in str(call) for call in call_args)


def test_main_displays_bucket_count_single_bucket():
    """Test that main() displays correct bucket count with one bucket."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = ["my-bucket"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                # Verify bucket count header shows (1)
                call_args = [str(call) for call in mock_print.call_args_list]
                assert any("S3 Buckets (1)" in str(call) for call in call_args)


def test_main_displays_bucket_count_multiple_buckets():
    """Test that main() displays correct bucket count with multiple buckets."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = ["bucket-1", "bucket-2", "bucket-3", "bucket-4", "bucket-5"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                # Verify bucket count header shows (5)
                call_args = [str(call) for call in mock_print.call_args_list]
                assert any("S3 Buckets (5)" in str(call) for call in call_args)


def test_main_displays_bucket_names_single():
    """Test that main() displays bucket names when there is one bucket."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = ["my-data-bucket"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                # Verify bucket name is printed with proper formatting
                call_args = [str(call) for call in mock_print.call_args_list]
                assert any("- my-data-bucket" in str(call) for call in call_args)


def test_main_displays_bucket_names_multiple():
    """Test that main() displays all bucket names in proper format."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = ["bucket-a", "bucket-b", "bucket-c"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                # Verify all bucket names are printed with proper formatting
                call_args = [str(call) for call in mock_print.call_args_list]
                assert any("- bucket-a" in str(call) for call in call_args)
                assert any("- bucket-b" in str(call) for call in call_args)
                assert any("- bucket-c" in str(call) for call in call_args)


def test_main_displays_buckets_with_special_characters():
    """Test that main() displays bucket names with special characters correctly."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = ["my-prod-bucket-2024", "data.archive.backup", "test-backup-001"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                # Verify all bucket names are printed correctly
                call_args = [str(call) for call in mock_print.call_args_list]
                assert any("- my-prod-bucket-2024" in str(call) for call in call_args)
                assert any("- data.archive.backup" in str(call) for call in call_args)
                assert any("- test-backup-001" in str(call) for call in call_args)


def test_main_handles_empty_bucket_list():
    """Test that main() handles an empty bucket list without errors."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=[]):
            with mock.patch("builtins.print"):
                # Should not raise any exception
                aws_info.main()


def test_main_handles_many_buckets():
    """Test that main() correctly handles a large number of buckets."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    # Create 100 buckets
    mock_buckets = [f"bucket-{i:03d}" for i in range(100)]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                # Verify bucket count is correct
                call_args = [str(call) for call in mock_print.call_args_list]
                assert any("S3 Buckets (100)" in str(call) for call in call_args)
                # Verify all 100 bucket names appear
                for i in range(100):
                    bucket_name = f"bucket-{i:03d}"
                    assert any(bucket_name in str(call) for call in call_args)


def test_main_with_long_bucket_names():
    """Test that main() displays long bucket names correctly."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = ["very-long-bucket-name-with-many-characters-2024-prod-backup"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                call_args = [str(call) for call in mock_print.call_args_list]
                assert any(
                    "very-long-bucket-name-with-many-characters-2024-prod-backup" in str(call)
                    for call in call_args
                )


def test_main_with_numbered_bucket_names():
    """Test that main() handles bucket names with numbers correctly."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = ["bucket1", "bucket2", "bucket-123", "bucket456789"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                call_args = [str(call) for call in mock_print.call_args_list]
                assert any("- bucket1" in str(call) for call in call_args)
                assert any("- bucket2" in str(call) for call in call_args)
                assert any("- bucket-123" in str(call) for call in call_args)
                assert any("- bucket456789" in str(call) for call in call_args)
