"""
Unit tests for aws_info.py - S3 Buckets Display

Tests the main() function's S3 bucket listing functionality.
Uses pytest and unittest.mock to mock aws_utils functions.
"""

import aws_info

# ============================================================================
# Tests for main() - S3 Buckets Display
# ============================================================================


def test_main_displays_bucket_count_zero_buckets(mock_aws_info_context):
    """Test that main() displays correct bucket count when there are no buckets."""
    with mock_aws_info_context.with_buckets([]):
        aws_info.main()

        # Verify bucket count header is printed with (0)
        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("S3 Buckets (0)" in str(call) for call in call_args)


def test_main_displays_bucket_count_single_bucket(mock_aws_info_context):
    """Test that main() displays correct bucket count with one bucket."""
    with mock_aws_info_context.with_buckets(["my-bucket"]):
        aws_info.main()

        # Verify bucket count header shows (1)
        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("S3 Buckets (1)" in str(call) for call in call_args)


def test_main_displays_bucket_count_multiple_buckets(mock_aws_info_context):
    """Test that main() displays correct bucket count with multiple buckets."""
    with mock_aws_info_context.with_buckets(
        ["bucket-1", "bucket-2", "bucket-3", "bucket-4", "bucket-5"]
    ):
        aws_info.main()

        # Verify bucket count header shows (5)
        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("S3 Buckets (5)" in str(call) for call in call_args)


def test_main_displays_bucket_names_single(mock_aws_info_context):
    """Test that main() displays bucket names when there is one bucket."""
    with mock_aws_info_context.with_buckets(["my-data-bucket"]):
        aws_info.main()

        # Verify bucket name is printed with proper formatting
        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("- my-data-bucket" in str(call) for call in call_args)


def test_main_displays_bucket_names_multiple(mock_aws_info_context):
    """Test that main() displays all bucket names in proper format."""
    with mock_aws_info_context.with_buckets(["bucket-a", "bucket-b", "bucket-c"]):
        aws_info.main()

        # Verify all bucket names are printed with proper formatting
        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("- bucket-a" in str(call) for call in call_args)
        assert any("- bucket-b" in str(call) for call in call_args)
        assert any("- bucket-c" in str(call) for call in call_args)


def test_main_displays_buckets_with_special_characters(mock_aws_info_context):
    """Test that main() displays bucket names with special characters correctly."""
    with mock_aws_info_context.with_buckets(
        ["my-prod-bucket-2024", "data.archive.backup", "test-backup-001"]
    ):
        aws_info.main()

        # Verify all bucket names are printed correctly
        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("- my-prod-bucket-2024" in str(call) for call in call_args)
        assert any("- data.archive.backup" in str(call) for call in call_args)
        assert any("- test-backup-001" in str(call) for call in call_args)


def test_main_handles_empty_bucket_list(mock_aws_info_context):
    """Test that main() handles an empty bucket list without errors."""
    with mock_aws_info_context.with_buckets([]):
        # Should not raise any exception
        aws_info.main()


def test_main_handles_many_buckets(mock_aws_info_context):
    """Test that main() correctly handles a large number of buckets."""
    # Create 100 buckets
    mock_buckets = [f"bucket-{i:03d}" for i in range(100)]

    with mock_aws_info_context.with_buckets(mock_buckets):
        aws_info.main()

        # Verify bucket count is correct
        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("S3 Buckets (100)" in str(call) for call in call_args)
        # Verify all 100 bucket names appear
        for i in range(100):
            bucket_name = f"bucket-{i:03d}"
            assert any(bucket_name in str(call) for call in call_args)


def test_main_with_long_bucket_names(mock_aws_info_context):
    """Test that main() displays long bucket names correctly."""
    with mock_aws_info_context.with_buckets(
        ["very-long-bucket-name-with-many-characters-2024-prod-backup"]
    ):
        aws_info.main()

        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any(
            "very-long-bucket-name-with-many-characters-2024-prod-backup" in str(call)
            for call in call_args
        )


def test_main_with_numbered_bucket_names(mock_aws_info_context):
    """Test that main() handles bucket names with numbers correctly."""
    with mock_aws_info_context.with_buckets(["bucket1", "bucket2", "bucket-123", "bucket456789"]):
        aws_info.main()

        call_args = [str(call) for call in mock_aws_info_context.print_mock.call_args_list]
        assert any("- bucket1" in str(call) for call in call_args)
        assert any("- bucket2" in str(call) for call in call_args)
        assert any("- bucket-123" in str(call) for call in call_args)
        assert any("- bucket456789" in str(call) for call in call_args)
