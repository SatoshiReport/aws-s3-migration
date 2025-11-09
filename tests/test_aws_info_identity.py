"""
Unit tests for aws_info.py - AWS Identity Display

Tests the main() function's AWS identity display functionality.
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
        "user_arn": (
            "arn:aws:iam::123456789012:user/" "very-long-username-with-many-characters-and-dashes"
        ),
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
