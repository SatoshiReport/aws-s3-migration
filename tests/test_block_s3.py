"""
Comprehensive unit tests for block_s3.py

Tests cover:
- main() with specific bucket names
- main() with --all flag
- main() in interactive mode
- Policies directory creation
- Policy file saving
- AWS utils mocking
- sys.exit and argparse behavior
"""

import os
from unittest import mock

import pytest

import block_s3


class TestMainWithSpecificBuckets:
    """Tests for main() function with specific bucket names as arguments"""

    def test_main_with_single_bucket(self, tmp_path, monkeypatch):
        """Test main() with a single bucket name"""
        monkeypatch.chdir(tmp_path)
        mock_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowOnlyMeFullAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123:user/test"},
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"],
                }
            ],
        }

        with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch(
                    "block_s3.generate_restrictive_bucket_policy", return_value=mock_policy
                ):
                    with mock.patch("block_s3.save_policy_to_file") as mock_save:
                        block_s3.main()

                        # Verify save was called with correct parameters
                        mock_save.assert_called_once()
                        args, kwargs = mock_save.call_args
                        assert args[0] == mock_policy
                        assert "test-bucket_policy.json" in args[1]

    def test_main_with_multiple_buckets(self, tmp_path, monkeypatch, capsys):
        """Test main() with multiple bucket names"""
        monkeypatch.chdir(tmp_path)
        mock_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowOnlyMeFullAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123:user/test"},
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::bucket1", "arn:aws:s3:::bucket1/*"],
                }
            ],
        }

        with mock.patch("sys.argv", ["block_s3.py", "bucket1", "bucket2"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch(
                    "block_s3.generate_restrictive_bucket_policy", return_value=mock_policy
                ):
                    with mock.patch("block_s3.save_policy_to_file") as mock_save:
                        block_s3.main()

                        # Verify save was called twice (once for each bucket)
                        assert mock_save.call_count == 2  # noqa: PLR2004

                        # Verify output mentions both buckets
                        captured = capsys.readouterr()
                        assert "Generating policies for 2 specified bucket(s)" in captured.out

    def test_main_creates_policies_directory(self, tmp_path, monkeypatch, capsys):
        """Test that main() creates the policies directory"""
        monkeypatch.chdir(tmp_path)
        mock_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowOnlyMeFullAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123:user/test"},
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"],
                }
            ],
        }

        # Verify policies directory doesn't exist yet
        policies_dir = tmp_path / "policies"
        assert not policies_dir.exists()

        with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch(
                    "block_s3.generate_restrictive_bucket_policy", return_value=mock_policy
                ):
                    with mock.patch("block_s3.save_policy_to_file"):
                        block_s3.main()

                        # Verify policies directory was created
                        assert policies_dir.exists()
                        assert policies_dir.is_dir()

    def test_main_saves_policy_with_correct_filename(self, tmp_path, monkeypatch):
        """Test that policy files are saved with correct bucket names"""
        monkeypatch.chdir(tmp_path)
        mock_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowOnlyMeFullAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123:user/test"},
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::my-bucket", "arn:aws:s3:::my-bucket/*"],
                }
            ],
        }

        with mock.patch("sys.argv", ["block_s3.py", "my-bucket"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch(
                    "block_s3.generate_restrictive_bucket_policy", return_value=mock_policy
                ):
                    with mock.patch("block_s3.save_policy_to_file") as mock_save:
                        block_s3.main()

                        # Verify filename format
                        call_args = mock_save.call_args[0]
                        filename = call_args[1]
                        assert filename.endswith("my-bucket_policy.json")
                        assert filename.startswith("policies/")


class TestMainWithAllFlag:
    """Tests for main() function with --all flag"""

    def test_main_with_all_flag(self, tmp_path, monkeypatch, capsys):
        """Test main() with --all flag processes all buckets"""
        monkeypatch.chdir(tmp_path)
        all_buckets = ["bucket1", "bucket2", "bucket3"]
        mock_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowOnlyMeFullAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123:user/test"},
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::bucket1", "arn:aws:s3:::bucket1/*"],
                }
            ],
        }

        with mock.patch("sys.argv", ["block_s3.py", "--all"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch("block_s3.list_s3_buckets", return_value=all_buckets):
                    with mock.patch(
                        "block_s3.generate_restrictive_bucket_policy", return_value=mock_policy
                    ):
                        with mock.patch("block_s3.save_policy_to_file") as mock_save:
                            block_s3.main()

                            # Verify save was called for each bucket
                            assert mock_save.call_count == 3  # noqa: PLR2004

                            # Verify output message
                            captured = capsys.readouterr()
                            assert (
                                f"Generating policies for all {len(all_buckets)} buckets"
                                in captured.out
                            )

    def test_main_with_all_flag_empty_account(self, tmp_path, monkeypatch, capsys):
        """Test main() with --all flag when account has no buckets"""
        monkeypatch.chdir(tmp_path)

        with mock.patch("sys.argv", ["block_s3.py", "--all"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch("block_s3.list_s3_buckets", return_value=[]):
                    with mock.patch("block_s3.generate_restrictive_bucket_policy") as mock_gen:
                        with mock.patch("block_s3.save_policy_to_file") as mock_save:
                            block_s3.main()

                            # Verify no policies were generated
                            mock_gen.assert_not_called()
                            mock_save.assert_not_called()

                            # Verify output message
                            captured = capsys.readouterr()
                            assert "Generating policies for all 0 buckets" in captured.out

    def test_main_with_all_flag_retrieves_buckets_from_aws(self, tmp_path, monkeypatch):
        """Test that --all flag calls list_s3_buckets() to get all buckets"""
        monkeypatch.chdir(tmp_path)

        with mock.patch("sys.argv", ["block_s3.py", "--all"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch("block_s3.list_s3_buckets", return_value=[]) as mock_list:
                    with mock.patch("block_s3.generate_restrictive_bucket_policy"):
                        with mock.patch("block_s3.save_policy_to_file"):
                            block_s3.main()

                            # Verify list_s3_buckets was called
                            mock_list.assert_called_once()


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
                    "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"],
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


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_main_with_bucket_names_and_all_flag_prefers_all(self, tmp_path, monkeypatch, capsys):
        """Test that --all flag takes precedence over specific bucket names"""
        monkeypatch.chdir(tmp_path)
        all_buckets = ["bucket-from-all-flag"]

        with mock.patch("sys.argv", ["block_s3.py", "ignored-bucket", "--all"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch("block_s3.list_s3_buckets", return_value=all_buckets):
                    with mock.patch(
                        "block_s3.generate_restrictive_bucket_policy",
                        return_value={"Version": "2012-10-17", "Statement": []},
                    ):
                        with mock.patch("block_s3.save_policy_to_file") as mock_save:
                            block_s3.main()

                            # Verify list_s3_buckets was called (--all flag was used)
                            captured = capsys.readouterr()
                            assert "Generating policies for all" in captured.out
                            # Verify only 1 bucket processed (from all flag, not from args)
                            assert mock_save.call_count == 1

    def test_main_policies_directory_with_existing_directory(self, tmp_path, monkeypatch):
        """Test main() when policies directory already exists"""
        monkeypatch.chdir(tmp_path)
        # Pre-create the policies directory
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

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
                        # Should not raise an error
                        block_s3.main()

                        # Directory should still exist
                        assert policies_dir.exists()

    def test_main_with_bucket_name_containing_special_characters(self, tmp_path, monkeypatch):
        """Test main() with bucket names containing hyphens and numbers"""
        monkeypatch.chdir(tmp_path)
        special_bucket_name = "my-test-bucket-123"

        with mock.patch("sys.argv", ["block_s3.py", special_bucket_name]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch(
                    "block_s3.generate_restrictive_bucket_policy",
                    return_value={"Version": "2012-10-17", "Statement": []},
                ):
                    with mock.patch("block_s3.save_policy_to_file") as mock_save:
                        block_s3.main()

                        # Verify filename contains the bucket name
                        call_args = mock_save.call_args[0]
                        filename = call_args[1]
                        assert special_bucket_name in filename


class TestArgparseBehavior:
    """Tests for argparse behavior and command-line parsing"""

    def test_argparse_accepts_multiple_positional_arguments(self, tmp_path, monkeypatch):
        """Test that argparse correctly handles multiple positional bucket arguments"""
        monkeypatch.chdir(tmp_path)

        # This should work without raising any argparse errors
        with mock.patch("sys.argv", ["block_s3.py", "bucket1", "bucket2", "bucket3"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch(
                    "block_s3.generate_restrictive_bucket_policy",
                    return_value={"Version": "2012-10-17", "Statement": []},
                ):
                    with mock.patch("block_s3.save_policy_to_file") as mock_save:
                        block_s3.main()
                        # Should process all three buckets without error
                        assert mock_save.call_count == 3  # noqa: PLR2004

    def test_argparse_recognizes_all_flag(self, tmp_path, monkeypatch):
        """Test that argparse correctly recognizes --all flag"""
        monkeypatch.chdir(tmp_path)

        with mock.patch("sys.argv", ["block_s3.py", "--all"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch("block_s3.list_s3_buckets", return_value=["bucket1"]):
                    with mock.patch(
                        "block_s3.generate_restrictive_bucket_policy",
                        return_value={"Version": "2012-10-17", "Statement": []},
                    ):
                        with mock.patch("block_s3.save_policy_to_file") as mock_save:
                            block_s3.main()
                            # list_s3_buckets should be called when --all is used
                            assert mock_save.call_count == 1


class TestRealFileOperations:
    """Tests with actual file I/O to verify file operations work correctly"""

    def test_policies_directory_actually_created(self, tmp_path, monkeypatch):
        """Integration test: verify policies directory is actually created on disk"""
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

                        # Check on actual filesystem
                        policies_path = tmp_path / "policies"
                        assert os.path.isdir(str(policies_path))

    def test_policy_file_path_constructed_correctly(self, tmp_path, monkeypatch):
        """Test that policy file paths are constructed with correct directory"""
        monkeypatch.chdir(tmp_path)
        captured_filename = None

        def capture_filename(policy, filename):
            nonlocal captured_filename
            captured_filename = filename

        with mock.patch("sys.argv", ["block_s3.py", "test-bucket"]):
            with mock.patch(
                "block_s3.get_aws_identity",
                return_value={"user_arn": "arn:aws:iam::123:user/test"},
            ):
                with mock.patch(
                    "block_s3.generate_restrictive_bucket_policy",
                    return_value={"Version": "2012-10-17", "Statement": []},
                ):
                    with mock.patch("block_s3.save_policy_to_file", side_effect=capture_filename):
                        block_s3.main()

                        # Verify filename format
                        assert captured_filename is not None
                        assert captured_filename.startswith("policies")
                        assert captured_filename.endswith("test-bucket_policy.json")
                        # Verify path uses OS separator
                        assert os.sep in captured_filename


class TestMultipleConsecutiveCalls:
    """Tests for multiple consecutive calls to main()"""

    def test_main_can_be_called_multiple_times(self, tmp_path, monkeypatch):
        """Test that main() can be called multiple times without state issues"""
        monkeypatch.chdir(tmp_path)

        with mock.patch(
            "block_s3.get_aws_identity",
            return_value={"user_arn": "arn:aws:iam::123:user/test"},
        ):
            with mock.patch(
                "block_s3.generate_restrictive_bucket_policy",
                return_value={"Version": "2012-10-17", "Statement": []},
            ):
                with mock.patch("block_s3.save_policy_to_file"):
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
