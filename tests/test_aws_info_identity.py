"""
Unit tests for aws_info.py - AWS Identity Display

Tests the main() function's AWS identity display functionality.
Uses pytest and unittest.mock to mock aws_utils functions.
"""

import aws_info

# ============================================================================
# Tests for main() - AWS Identity Display
# ============================================================================


def test_main_displays_account_id(mock_aws_info_context):
    """Test that main() prints the account ID."""
    with mock_aws_info_context.with_buckets(["bucket-1", "bucket-2"]):
        aws_info.main()

        # Verify account ID is printed
        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("Account ID: 123456789012" in str(call) for call in call_args)


def test_main_displays_username(mock_aws_info_context):
    """Test that main() prints the username."""
    with mock_aws_info_context.with_buckets(["bucket-1"]):
        aws_info.main()

        # Verify username is printed
        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("Username: test-user" in str(call) for call in call_args)


def test_main_displays_user_arn(mock_aws_info_context):
    """Test that main() prints the user ARN."""
    with mock_aws_info_context.with_buckets([]):
        aws_info.main()

        # Verify user ARN is printed
        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("User ARN: arn:aws:iam::123456789012:user/test-user" in str(call) for call in call_args)


def test_main_displays_identity_in_correct_order(mock_aws_info_context):
    """Test that identity information is displayed in the correct order."""
    with mock_aws_info_context.with_buckets([]):
        aws_info.main()

        # Verify order of calls: Account ID, Username, User ARN
        calls = mock_aws_info_context.print_mock.call_args_list
        assert "Account ID" in str(calls[0])
        assert "Username" in str(calls[1])
        assert "User ARN" in str(calls[2])


def test_main_with_long_account_id(mock_aws_info_context):
    """Test that main() handles long account IDs correctly."""
    mock_identity = {
        "account_id": "999999999999999999",
        "username": "test-user",
        "user_arn": "arn:aws:iam::999999999999999999:user/test-user",
    }

    # Override the default identity for this test
    mock_aws_info_context.identity = mock_identity

    with mock_aws_info_context.with_buckets([]):
        aws_info.main()

        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("Account ID: 999999999999999999" in str(call) for call in call_args)


def test_main_with_long_username(mock_aws_info_context):
    """Test that main() handles long usernames correctly."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "very-long-username-with-many-characters-and-dashes",
        "user_arn": ("arn:aws:iam::123456789012:user/" "very-long-username-with-many-characters-and-dashes"),
    }

    # Override the default identity for this test
    mock_aws_info_context.identity = mock_identity

    with mock_aws_info_context.with_buckets([]):
        aws_info.main()

        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("very-long-username-with-many-characters-and-dashes" in str(call) for call in call_args)


def test_main_with_various_arn_formats(mock_aws_info_context):
    """Test that main() displays various ARN formats correctly."""
    mock_identity = {
        "account_id": "123456789012",
        "username": "service-role",
        "user_arn": "arn:aws:iam::123456789012:role/service-role",
    }

    # Override the default identity for this test
    mock_aws_info_context.identity = mock_identity

    with mock_aws_info_context.with_buckets([]):
        aws_info.main()

        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("arn:aws:iam::123456789012:role/service-role" in str(call) for call in call_args)
