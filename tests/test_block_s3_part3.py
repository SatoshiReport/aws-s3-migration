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


def test_main_with_bucket_names_and_all_flag_prefers_all(tmp_path, monkeypatch, capsys):
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


def test_main_policies_directory_with_existing_directory(tmp_path, monkeypatch):
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


def test_main_with_bucket_name_containing_special_characters(tmp_path, monkeypatch):
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


def test_argparse_accepts_multiple_positional_arguments(tmp_path, monkeypatch):
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
                    assert_equal(mock_save.call_count, 3)


def test_argparse_recognizes_all_flag(tmp_path, monkeypatch):
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


def test_policies_directory_actually_created(tmp_path, monkeypatch):
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


def test_policy_file_path_constructed_correctly(tmp_path, monkeypatch):
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
                    filename_str = str(captured_filename)  # Convert to str for pylint
                    assert filename_str.startswith("policies")
                    assert filename_str.endswith("test-bucket_policy.json")
                    # Verify path uses OS separator
                    assert os.sep in filename_str


def test_main_can_be_called_multiple_times(tmp_path, monkeypatch):
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
