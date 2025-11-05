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

    def test_main_interactive_mode_exits_with_zero(self, tmp_path, monkeypatch):
        """Test main() in interactive mode exits with status 0"""
        monkeypatch.chdir(tmp_path)
        sample_buckets = ["bucket1", "bucket2"]

        with mock.patch("sys.argv", ["block_s3.py"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch("block_s3.list_s3_buckets", return_value=sample_buckets):
                    with pytest.raises(SystemExit) as exc_info:
                        block_s3.main()

                    # Verify it exits with code 0
                    assert exc_info.value.code == 0

    def test_main_interactive_mode_displays_help_message(self, tmp_path, monkeypatch, capsys):
        """Test interactive mode displays help message"""
        monkeypatch.chdir(tmp_path)
        sample_buckets = ["bucket1", "bucket2"]

        with mock.patch("sys.argv", ["block_s3.py"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch("block_s3.list_s3_buckets", return_value=sample_buckets):
                    with pytest.raises(SystemExit):
                        block_s3.main()

                    captured = capsys.readouterr()
                    assert "No buckets specified. Available options:" in captured.out
                    assert "python block_s3.py bucket1 bucket2" in captured.out
                    assert "python block_s3.py --all" in captured.out

    def test_main_interactive_mode_lists_available_buckets(self, tmp_path, monkeypatch, capsys):
        """Test interactive mode lists available buckets"""
        monkeypatch.chdir(tmp_path)
        sample_buckets = ["my-bucket-1", "my-bucket-2", "my-bucket-3"]

        with mock.patch("sys.argv", ["block_s3.py"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch("block_s3.list_s3_buckets", return_value=sample_buckets):
                    with pytest.raises(SystemExit):
                        block_s3.main()

                    captured = capsys.readouterr()
                    assert "Available buckets:" in captured.out
                    assert "- my-bucket-1" in captured.out
                    assert "- my-bucket-2" in captured.out
                    assert "- my-bucket-3" in captured.out

    def test_main_interactive_mode_does_not_generate_policies(self, tmp_path, monkeypatch):
        """Test interactive mode does not generate or save policies"""
        monkeypatch.chdir(tmp_path)

        with mock.patch("sys.argv", ["block_s3.py"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
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

    def test_main_calls_get_aws_identity(self, tmp_path, monkeypatch):
        """Test that main() calls get_aws_identity()"""
        monkeypatch.chdir(tmp_path)

        with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
            with mock.patch("block_s3.get_aws_identity") as mock_identity:
                mock_identity.return_value = {"user_arn": "arn:aws:iam::123:user/test"}
                with mock.patch("block_s3.generate_restrictive_bucket_policy"):
                    with mock.patch("block_s3.save_policy_to_file"):
                        block_s3.main()

                        mock_identity.assert_called_once()

    def test_main_passes_correct_arn_to_generate_policy(self, tmp_path, monkeypatch):
        """Test that main() passes correct ARN to generate_restrictive_bucket_policy()"""
        monkeypatch.chdir(tmp_path)
        test_arn = "arn:aws:iam::123456789012:user/testuser"

        with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": test_arn},
            ):
                with mock.patch("block_s3.generate_restrictive_bucket_policy") as mock_gen:
                    mock_gen.return_value = {"Version": "2012-10-17", "Statement": []}
                    with mock.patch("block_s3.save_policy_to_file"):
                        block_s3.main()

                        # Verify generate_restrictive_bucket_policy was called with correct ARN
                        call_args = mock_gen.call_args[0]
                        assert call_args[0] == test_arn

    def test_main_passes_bucket_name_to_generate_policy(self, tmp_path, monkeypatch):
        """Test that main() passes bucket name to generate_restrictive_bucket_policy()"""
        monkeypatch.chdir(tmp_path)

        with mock.patch("sys.argv", ["block_s3.py", "my-special-bucket"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch("block_s3.generate_restrictive_bucket_policy") as mock_gen:
                    mock_gen.return_value = {"Version": "2012-10-17", "Statement": []}
                    with mock.patch("block_s3.save_policy_to_file"):
                        block_s3.main()

                        # Verify bucket name was passed correctly
                        call_args = mock_gen.call_args[0]
                        assert call_args[1] == "my-special-bucket"

    def test_main_calls_save_policy_with_policy_object_and_filename(self, tmp_path, monkeypatch):
        """Test that main() calls save_policy_to_file() with correct arguments"""
        monkeypatch.chdir(tmp_path)
        expected_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowOnlyMeFullAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123:user/test"},
                    "Action": "s3:*",
                    "Resource": [
                        "arn:aws:s3:::test-bucket",
                        "arn:aws:s3:::test-bucket/*",
                    ],
                }
            ],
        }

        with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch(
                    "block_s3.generate_restrictive_bucket_policy",
                    return_value=expected_policy,
                ):
                    with mock.patch("block_s3.save_policy_to_file") as mock_save:
                        block_s3.main()

                        # Verify save was called with policy and filename
                        mock_save.assert_called_once()
                        saved_policy, saved_filename = mock_save.call_args[0]
                        assert saved_policy == expected_policy
                        assert saved_filename.endswith("test-bucket_policy.json")


class TestOutputMessages:
    """Tests for output messages and logging"""

    def test_main_prints_success_message_for_single_bucket(self, tmp_path, monkeypatch, capsys):
        """Test that main() prints success message when generating policy"""
        monkeypatch.chdir(tmp_path)

        with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch(
                    "block_s3.generate_restrictive_bucket_policy",
                    return_value={"Version": "2012-10-17", "Statement": []},
                ):
                    with mock.patch("block_s3.save_policy_to_file"):
                        block_s3.main()

                        captured = capsys.readouterr()
                        assert "Successfully generated 1 policy file(s)" in captured.out
                        assert "Saved" in captured.out

    def test_main_prints_success_message_for_multiple_buckets(self, tmp_path, monkeypatch, capsys):
        """Test that main() prints correct count for multiple buckets"""
        monkeypatch.chdir(tmp_path)

        with mock.patch("sys.argv", ["block_s3.py", "bucket1", "bucket2", "bucket3"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch(
                    "block_s3.generate_restrictive_bucket_policy",
                    return_value={"Version": "2012-10-17", "Statement": []},
                ):
                    with mock.patch("block_s3.save_policy_to_file"):
                        block_s3.main()

                        captured = capsys.readouterr()
                        assert "Successfully generated 3 policy file(s)" in captured.out

    def test_main_prints_status_for_each_saved_file(self, tmp_path, monkeypatch, capsys):
        """Test that main() prints message for each saved policy file"""
        monkeypatch.chdir(tmp_path)

        with mock.patch("sys.argv", ["block_s3.py", "bucket1", "bucket2"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch(
                    "block_s3.generate_restrictive_bucket_policy",
                    return_value={"Version": "2012-10-17", "Statement": []},
                ):
                    with mock.patch("block_s3.save_policy_to_file"):
                        block_s3.main()

                        captured = capsys.readouterr()
                        # Should print status for bucket1
                        assert "bucket1_policy.json" in captured.out
                        # Should print status for bucket2
                        assert "bucket2_policy.json" in captured.out
