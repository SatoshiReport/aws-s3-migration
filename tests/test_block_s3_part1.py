"""
Comprehensive unit tests for block_s3.py - Part 1: Basic Functionality

Tests cover:
- main() with specific bucket names
- main() with --all flag
"""

from unittest import mock

import block_s3
from tests.assertions import assert_equal


def test_main_with_single_bucket(setup_test_env, sample_policy, mock_block_s3_context):
    """Test main() with a single bucket name"""
    _ = setup_test_env  # Used for test isolation
    with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
        with mock_block_s3_context.with_policy(sample_policy) as ctx:
            block_s3.main()

            # Verify save was called with correct parameters
            ctx.save_policy_mock.assert_called_once()
            args, _kwargs = ctx.save_policy_mock.call_args
            assert args[0] == sample_policy
            assert "test-bucket_policy.json" in args[1]


def test_main_with_multiple_buckets(setup_test_env, sample_policy, mock_block_s3_context, capsys):
    """Test main() with multiple bucket names"""
    _ = setup_test_env  # Used for test isolation
    with mock.patch("sys.argv", ["block_s3.py", "bucket1", "bucket2"]):
        with mock_block_s3_context.with_policy(sample_policy) as ctx:
            block_s3.main()

            # Verify save was called twice (once for each bucket)
            assert_equal(ctx.save_policy_mock.call_count, 2)

            # Verify output mentions both buckets
            captured = capsys.readouterr()
            assert "Generating policies for 2 specified bucket(s)" in captured.out


def test_main_creates_policies_directory(setup_test_env, sample_policy, mock_block_s3_context):
    """Test that main() creates the policies directory"""
    # Verify policies directory doesn't exist yet
    policies_dir = setup_test_env / "policies"
    assert not policies_dir.exists()

    with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
        with mock_block_s3_context.with_policy(sample_policy):
            block_s3.main()

            # Verify policies directory was created
            assert policies_dir.exists()
            assert policies_dir.is_dir()


def test_main_saves_policy_with_correct_filename(setup_test_env, sample_policy, mock_block_s3_context):
    """Test that policy files are saved with correct bucket names"""
    _ = setup_test_env  # Used for test isolation
    with mock.patch("sys.argv", ["block_s3.py", "my-bucket"]):
        with mock_block_s3_context.with_policy(sample_policy) as ctx:
            block_s3.main()

            # Verify filename format
            call_args = ctx.save_policy_mock.call_args[0]
            filename = call_args[1]
            assert filename.endswith("my-bucket_policy.json")
            assert filename.startswith("policies/")


def test_main_with_all_flag(setup_test_env, sample_policy, mock_block_s3_context, capsys):
    """Test main() with --all flag processes all buckets"""
    _ = setup_test_env  # Used for test isolation
    all_buckets = ["bucket1", "bucket2", "bucket3"]

    with mock.patch("sys.argv", ["block_s3.py", "--all"]):
        with mock.patch("block_s3.list_s3_buckets", return_value=all_buckets):
            with mock_block_s3_context.with_policy(sample_policy) as ctx:
                block_s3.main()

                # Verify save was called for each bucket
                assert_equal(ctx.save_policy_mock.call_count, 3)

                # Verify output message
                captured = capsys.readouterr()
                assert f"Generating policies for all {len(all_buckets)} buckets" in captured.out


def test_main_with_all_flag_empty_account(setup_test_env, mock_block_s3_context, capsys):
    """Test main() with --all flag when account has no buckets"""
    _ = setup_test_env  # Used for test isolation
    with mock.patch("sys.argv", ["block_s3.py", "--all"]):
        with mock.patch("block_s3.list_s3_buckets", return_value=[]):
            with mock_block_s3_context as ctx:
                block_s3.main()

                # Verify no policies were generated
                ctx.policy_mock.assert_not_called()
                ctx.save_policy_mock.assert_not_called()

                # Verify output message
                captured = capsys.readouterr()
                assert "Generating policies for all 0 buckets" in captured.out


def test_main_with_all_flag_retrieves_buckets_from_aws(setup_test_env, mock_aws_identity):
    """Test that --all flag calls list_s3_buckets() to get all buckets"""
    _ = setup_test_env  # Used for test isolation
    with mock.patch("sys.argv", ["block_s3.py", "--all"]):
        with mock.patch(
            "block_s3.get_aws_identity",
            return_value=mock_aws_identity,
        ):
            with mock.patch("block_s3.list_s3_buckets", return_value=[]) as mock_list:
                with mock.patch("block_s3.generate_restrictive_bucket_policy"):
                    with mock.patch("block_s3.save_policy_to_file"):
                        block_s3.main()

                        # Verify list_s3_buckets was called
                        mock_list.assert_called_once()
