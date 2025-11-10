"""
Comprehensive unit tests for block_s3.py - Part 1: Basic Functionality

Tests cover:
- main() with specific bucket names
- main() with --all flag
"""

from unittest import mock

import block_s3
from tests.assertions import assert_equal


def test_main_with_single_bucket(tmp_path, monkeypatch):
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
                return_value=mock_policy,
            ):
                with mock.patch("block_s3.save_policy_to_file") as mock_save:
                    block_s3.main()

                    # Verify save was called with correct parameters
                    mock_save.assert_called_once()
                    args, _kwargs = mock_save.call_args
                    assert args[0] == mock_policy
                    assert "test-bucket_policy.json" in args[1]


def test_main_with_multiple_buckets(tmp_path, monkeypatch, capsys):
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
                "block_s3.generate_restrictive_bucket_policy",
                return_value=mock_policy,
            ):
                with mock.patch("block_s3.save_policy_to_file") as mock_save:
                    block_s3.main()

                    # Verify save was called twice (once for each bucket)
                    assert_equal(mock_save.call_count, 2)

                    # Verify output mentions both buckets
                    captured = capsys.readouterr()
                    assert "Generating policies for 2 specified bucket(s)" in captured.out


def test_main_creates_policies_directory(tmp_path, monkeypatch, capsys):
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
                "Resource": [
                    "arn:aws:s3:::test-bucket",
                    "arn:aws:s3:::test-bucket/*",
                ],
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
                "block_s3.generate_restrictive_bucket_policy",
                return_value=mock_policy,
            ):
                with mock.patch("block_s3.save_policy_to_file"):
                    block_s3.main()

                    # Verify policies directory was created
                    assert policies_dir.exists()
                    assert policies_dir.is_dir()


def test_main_saves_policy_with_correct_filename(tmp_path, monkeypatch):
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
                "block_s3.generate_restrictive_bucket_policy",
                return_value=mock_policy,
            ):
                with mock.patch("block_s3.save_policy_to_file") as mock_save:
                    block_s3.main()

                    # Verify filename format
                    call_args = mock_save.call_args[0]
                    filename = call_args[1]
                    assert filename.endswith("my-bucket_policy.json")
                    assert filename.startswith("policies/")


def test_main_with_all_flag(tmp_path, monkeypatch, capsys):
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
                    "block_s3.generate_restrictive_bucket_policy",
                    return_value=mock_policy,
                ):
                    with mock.patch("block_s3.save_policy_to_file") as mock_save:
                        block_s3.main()

                        # Verify save was called for each bucket
                        assert_equal(mock_save.call_count, 3)

                        # Verify output message
                        captured = capsys.readouterr()
                        assert (
                            f"Generating policies for all {len(all_buckets)} buckets"
                            in captured.out
                        )


def test_main_with_all_flag_empty_account(tmp_path, monkeypatch, capsys):
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


def test_main_with_all_flag_retrieves_buckets_from_aws(tmp_path, monkeypatch):
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
