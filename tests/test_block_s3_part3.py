"""
Comprehensive unit tests for block_s3.py - Part 3: Edge Cases and Miscellaneous

Tests cover:
- Edge cases and error handling
- Argparse behavior
- Real file operations
- Multiple consecutive calls
- Module import
"""

import os
from unittest import mock

import block_s3
from tests.assertions import assert_equal


def test_main_with_bucket_names_and_all_flag_prefers_all(setup_test_env, mock_block_s3_context, capsys):
    """Test that --all flag takes precedence over specific bucket names"""
    _ = setup_test_env  # Used for test isolation
    all_buckets = ["bucket-from-all-flag"]
    test_policy = {"Version": "2012-10-17", "Statement": []}

    with mock.patch("sys.argv", ["block_s3.py", "ignored-bucket", "--all"]):
        with mock.patch("block_s3.list_s3_buckets", return_value=all_buckets):
            with mock_block_s3_context.with_policy(test_policy) as ctx:
                block_s3.main()

                # Verify list_s3_buckets was called (--all flag was used)
                captured = capsys.readouterr()
                assert "Generating policies for all" in captured.out
                # Verify only 1 bucket processed (from all flag, not from args)
                assert ctx.save_policy_mock.call_count == 1


def test_main_policies_directory_with_existing_directory(policies_dir, mock_block_s3_context):
    """Test main() when policies directory already exists"""
    # policies_dir fixture already creates the directory
    test_policy = {"Version": "2012-10-17", "Statement": []}

    with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
        with mock_block_s3_context.with_policy(test_policy):
            # Should not raise an error
            block_s3.main()

            # Directory should still exist
            assert policies_dir.exists()


def test_main_with_bucket_name_containing_special_characters(setup_test_env, mock_block_s3_context):
    """Test main() with bucket names containing hyphens and numbers"""
    _ = setup_test_env  # Used for test isolation
    special_bucket_name = "my-test-bucket-123"
    test_policy = {"Version": "2012-10-17", "Statement": []}

    with mock.patch("sys.argv", ["block_s3.py", special_bucket_name]):
        with mock_block_s3_context.with_policy(test_policy) as ctx:
            block_s3.main()

            # Verify filename contains the bucket name
            call_args = ctx.save_policy_mock.call_args[0]
            filename = call_args[1]
            assert special_bucket_name in filename


def test_argparse_accepts_multiple_positional_arguments(setup_test_env, mock_block_s3_context):
    """Test that argparse correctly handles multiple positional bucket arguments"""
    _ = setup_test_env  # Used for test isolation
    test_policy = {"Version": "2012-10-17", "Statement": []}

    # This should work without raising any argparse errors
    with mock.patch("sys.argv", ["block_s3.py", "bucket1", "bucket2", "bucket3"]):
        with mock_block_s3_context.with_policy(test_policy) as ctx:
            block_s3.main()
            # Should process all three buckets without error
            assert_equal(ctx.save_policy_mock.call_count, 3)


def test_argparse_recognizes_all_flag(setup_test_env, mock_block_s3_context):
    """Test that argparse correctly recognizes --all flag"""
    _ = setup_test_env  # Used for test isolation
    test_policy = {"Version": "2012-10-17", "Statement": []}

    with mock.patch("sys.argv", ["block_s3.py", "--all"]):
        with mock.patch("block_s3.list_s3_buckets", return_value=["bucket1"]):
            with mock_block_s3_context.with_policy(test_policy) as ctx:
                block_s3.main()
                # list_s3_buckets should be called when --all is used
                assert ctx.save_policy_mock.call_count == 1


def test_policies_directory_actually_created(setup_test_env, mock_block_s3_context):
    """Integration test: verify policies directory is actually created on disk"""
    _ = setup_test_env  # Used for test isolation
    test_policy = {"Version": "2012-10-17", "Statement": []}

    with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
        with mock_block_s3_context.with_policy(test_policy):
            block_s3.main()

            # Check on actual filesystem
            policies_path = setup_test_env / "policies"
            assert os.path.isdir(str(policies_path))


def test_policy_file_path_constructed_correctly(setup_test_env, mock_block_s3_context):
    """Test that policy file paths are constructed with correct directory"""
    _ = setup_test_env  # Used for test isolation
    test_policy = {"Version": "2012-10-17", "Statement": []}

    with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
        with mock_block_s3_context.with_policy(test_policy) as ctx:
            block_s3.main()

            # Verify filename format
            call_args = ctx.save_policy_mock.call_args[0]
            captured_filename = call_args[1]
            assert captured_filename is not None
            filename_str = str(captured_filename)  # Convert to str for pylint
            assert filename_str.startswith("policies")
            assert filename_str.endswith("test-bucket_policy.json")
            # Verify path uses OS separator
            assert os.sep in filename_str


def test_main_can_be_called_multiple_times(setup_test_env, mock_block_s3_context):
    """Test that main() can be called multiple times without state issues"""
    _ = setup_test_env  # Used for test isolation
    test_policy = {"Version": "2012-10-17", "Statement": []}

    with mock_block_s3_context.with_policy(test_policy):
        # First call
        with mock.patch("sys.argv", ["block_s3.py", "bucket1"]):
            block_s3.main()

        # Second call
        with mock.patch("sys.argv", ["block_s3.py", "bucket2"]):
            block_s3.main()

        # Both should succeed without errors


class TestModuleImport:
    """Tests for module import and attributes"""

    def test_module_has_main_function(self):
        """Test that block_s3 module has a main() function"""
        assert hasattr(block_s3, "main")
        assert callable(block_s3.main)

    def test_main_function_is_callable(self):
        """Test that main is a callable function"""
        assert callable(getattr(block_s3, "main"))
