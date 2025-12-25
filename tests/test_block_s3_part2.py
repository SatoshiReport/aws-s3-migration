"""
Comprehensive unit tests for block_s3.py - Part 2: Interactive Mode and AWS Utils

Tests cover:
- main() in interactive mode
- AWS utils integration
"""

from unittest import mock

import pytest

import block_s3


class TestMainInteractiveMode:
    """Tests for main() function in interactive mode (no arguments)"""

    def test_main_interactive_mode_exits_with_zero(self, setup_test_env, mock_aws_identity):
        """Test main() in interactive mode exits with status 0"""
        _ = setup_test_env  # Used for test isolation
        _ = setup_test_env  # Used for test isolation
        sample_buckets = ["bucket1", "bucket2"]

        with mock.patch("sys.argv", ["block_s3.py"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value=mock_aws_identity,
            ):
                with mock.patch("block_s3.list_s3_buckets", return_value=sample_buckets):
                    with pytest.raises(SystemExit) as exc_info:
                        block_s3.main()

                    # Verify it exits with code 0
                    assert exc_info.value.code == 0

    def test_main_interactive_mode_displays_help_message(self, setup_test_env, mock_aws_identity, capsys):
        """Test interactive mode displays help message"""
        _ = setup_test_env  # Used for test isolation
        sample_buckets = ["bucket1", "bucket2"]

        with mock.patch("sys.argv", ["block_s3.py"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value=mock_aws_identity,
            ):
                with mock.patch("block_s3.list_s3_buckets", return_value=sample_buckets):
                    with pytest.raises(SystemExit):
                        block_s3.main()

                    captured = capsys.readouterr()
                    assert "No buckets specified. Available options:" in captured.out
                    assert "python block_s3.py bucket1 bucket2" in captured.out
                    assert "python block_s3.py --all" in captured.out

    def test_main_interactive_mode_lists_available_buckets(self, setup_test_env, mock_aws_identity, capsys):
        """Test interactive mode lists available buckets"""
        _ = setup_test_env  # Used for test isolation
        sample_buckets = ["my-bucket-1", "my-bucket-2", "my-bucket-3"]

        with mock.patch("sys.argv", ["block_s3.py"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value=mock_aws_identity,
            ):
                with mock.patch("block_s3.list_s3_buckets", return_value=sample_buckets):
                    with pytest.raises(SystemExit):
                        block_s3.main()

                    captured = capsys.readouterr()
                    assert "Available buckets:" in captured.out
                    assert "- my-bucket-1" in captured.out
                    assert "- my-bucket-2" in captured.out
                    assert "- my-bucket-3" in captured.out

    def test_main_interactive_mode_does_not_generate_policies(self, setup_test_env, mock_aws_identity):
        """Test interactive mode does not generate or save policies"""
        _ = setup_test_env  # Used for test isolation
        with mock.patch("sys.argv", ["block_s3.py"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value=mock_aws_identity,
            ):
                with mock.patch("block_s3.list_s3_buckets", return_value=["bucket1"]):
                    with mock.patch("block_s3.generate_restrictive_bucket_policy") as mock_gen:
                        with mock.patch("block_s3.save_policy_to_file") as mock_save:
                            with pytest.raises(SystemExit):
                                block_s3.main()

                            # Verify policies were not generated or saved
                            mock_gen.assert_not_called()
                            mock_save.assert_not_called()


class TestAwsUtilsIntegration:
    """Tests for integration with aws_utils functions"""

    def test_main_calls_get_aws_identity(self, setup_test_env, mock_aws_identity):
        """Test that main() calls get_aws_identity()"""
        _ = setup_test_env  # Used for test isolation
        _ = setup_test_env  # Used for test isolation
        with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
            with mock.patch("block_s3.get_aws_identity") as mock_identity:
                mock_identity.return_value = mock_aws_identity
                with mock.patch("block_s3.generate_restrictive_bucket_policy"):
                    with mock.patch("block_s3.save_policy_to_file"):
                        block_s3.main()

                        mock_identity.assert_called_once()

    def test_main_passes_correct_arn_to_generate_policy(self, setup_test_env, mock_block_s3_context):
        """Test that main() passes correct ARN to generate_restrictive_bucket_policy()"""
        _ = setup_test_env  # Used for test isolation
        test_arn = "arn:aws:iam::123456789012:user/testuser"
        test_policy = {"Version": "2012-10-17", "Statement": []}

        # Override identity for this test
        mock_block_s3_context.identity = {"user_arn": test_arn}

        with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
            with mock_block_s3_context.with_policy(test_policy) as ctx:
                block_s3.main()

                # Verify generate_restrictive_bucket_policy was called with correct ARN
                call_args = ctx.policy_mock.call_args[0]
                assert call_args[0] == test_arn

    def test_main_passes_bucket_name_to_generate_policy(self, setup_test_env, mock_block_s3_context):
        """Test that main() passes bucket name to generate_restrictive_bucket_policy()"""
        _ = setup_test_env  # Used for test isolation
        test_policy = {"Version": "2012-10-17", "Statement": []}

        with mock.patch("sys.argv", ["block_s3.py", "my-special-bucket"]):
            with mock_block_s3_context.with_policy(test_policy) as ctx:
                block_s3.main()

                # Verify bucket name was passed correctly
                call_args = ctx.policy_mock.call_args[0]
                assert call_args[1] == "my-special-bucket"

    def test_main_calls_save_policy_with_policy_object_and_filename(self, setup_test_env, sample_policy, mock_block_s3_context):
        """Test that main() calls save_policy_to_file() with correct arguments"""
        _ = setup_test_env  # Used for test isolation
        with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
            with mock_block_s3_context.with_policy(sample_policy) as ctx:
                block_s3.main()

                # Verify save was called with policy and filename
                ctx.save_policy_mock.assert_called_once()
                saved_policy, saved_filename = ctx.save_policy_mock.call_args[0]
                assert saved_policy == sample_policy
                assert saved_filename.endswith("test-bucket_policy.json")


class TestOutputMessages:
    """Tests for output messages and logging"""

    def test_main_prints_success_message_for_single_bucket(self, setup_test_env, mock_block_s3_context, capsys):
        """Test that main() prints success message when generating policy"""
        _ = setup_test_env  # Used for test isolation
        test_policy = {"Version": "2012-10-17", "Statement": []}

        with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
            with mock_block_s3_context.with_policy(test_policy):
                block_s3.main()

                captured = capsys.readouterr()
                assert "Successfully generated 1 policy file(s)" in captured.out
                assert "Saved" in captured.out

    def test_main_prints_success_message_for_multiple_buckets(self, setup_test_env, mock_block_s3_context, capsys):
        """Test that main() prints correct count for multiple buckets"""
        _ = setup_test_env  # Used for test isolation
        test_policy = {"Version": "2012-10-17", "Statement": []}

        with mock.patch("sys.argv", ["block_s3.py", "bucket1", "bucket2", "bucket3"]):
            with mock_block_s3_context.with_policy(test_policy):
                block_s3.main()

                captured = capsys.readouterr()
                assert "Successfully generated 3 policy file(s)" in captured.out

    def test_main_prints_status_for_each_saved_file(self, setup_test_env, mock_block_s3_context, capsys):
        """Test that main() prints message for each saved policy file"""
        _ = setup_test_env  # Used for test isolation
        test_policy = {"Version": "2012-10-17", "Statement": []}

        with mock.patch("sys.argv", ["block_s3.py", "bucket1", "bucket2"]):
            with mock_block_s3_context.with_policy(test_policy):
                block_s3.main()

                captured = capsys.readouterr()
                # Should print status for bucket1
                assert "bucket1_policy.json" in captured.out
                # Should print status for bucket2
                assert "bucket2_policy.json" in captured.out
