"""
Comprehensive unit tests for aws_info.py

Tests the main() function with various bucket counts and validates output format.
Uses pytest and unittest.mock to mock aws_utils functions.
"""

from unittest import mock

import aws_info

# ============================================================================
# Tests for main() - AWS Identity Display
# ============================================================================


def test_main_displays_account_id():
    """Test that main() prints the account ID."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }
    mock_buckets = ["bucket-1", "bucket-2"]

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                # Verify account ID is printed
                call_args = [str(call) for call in mock_print.call_args_list]
                assert any("Account ID: 123456789012" in str(call) for call in call_args)


def test_main_displays_username():
    """Test that main() prints the username."""
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

                # Verify username is printed
                call_args = [str(call) for call in mock_print.call_args_list]
                assert any("Username: test-user" in str(call) for call in call_args)


def test_main_displays_user_arn():
    """Test that main() prints the user ARN."""
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

                # Verify user ARN is printed
                call_args = [str(call) for call in mock_print.call_args_list]
                assert any(
                    "User ARN: arn:aws:iam::123456789012:user/test-user" in str(call)
                    for call in call_args
                )


def test_main_displays_identity_in_correct_order():
    """Test that identity information is displayed in the correct order."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "my-user",
        "user_arn": "arn:aws:iam::123456789012:user/my-user",
    }
    mock_buckets = []

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                # Verify order of calls: Account ID, Username, User ARN
                calls = mock_print.call_args_list
                assert "Account ID" in str(calls[0])
                assert "Username" in str(calls[1])
                assert "User ARN" in str(calls[2])


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
                assert mock_print.call_count == 4
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
                # Account ID, Username, User ARN, S3 Buckets header (with blank line in the string), 3 bucket names
                assert mock_print.call_count == 7
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


# ============================================================================
# Tests for main() - Edge Cases and Robustness
# ============================================================================


def test_main_with_long_account_id():
    """Test that main() handles long account IDs correctly."""
    mock_identity = {
        "account_id": "999999999999999999",
        "username": "test-user",
        "user_arn": "arn:aws:iam::999999999999999999:user/test-user",
    }
    mock_buckets = []

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                call_args = [str(call) for call in mock_print.call_args_list]
                assert any("Account ID: 999999999999999999" in str(call) for call in call_args)


def test_main_with_long_username():
    """Test that main() handles long usernames correctly."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "very-long-username-with-many-characters-and-dashes",
        "user_arn": "arn:aws:iam::123456789012:user/very-long-username-with-many-characters-and-dashes",
    }
    mock_buckets = []

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                call_args = [str(call) for call in mock_print.call_args_list]
                assert any(
                    "very-long-username-with-many-characters-and-dashes" in str(call)
                    for call in call_args
                )


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


def test_main_with_various_arn_formats():
    """Test that main() displays various ARN formats correctly."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "service-role",
        "user_arn": "arn:aws:iam::123456789012:role/service-role",
    }
    mock_buckets = []

    with mock.patch("aws_info.get_aws_identity", return_value=mock_identity):
        with mock.patch("aws_info.list_s3_buckets", return_value=mock_buckets):
            with mock.patch("builtins.print") as mock_print:
                aws_info.main()

                call_args = [str(call) for call in mock_print.call_args_list]
                assert any(
                    "arn:aws:iam::123456789012:role/service-role" in str(call) for call in call_args
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


# ============================================================================
# Tests for Module Entry Point
# ============================================================================


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
