"""
Unit tests for apply_block.py helper functions

Tests cover:
- get_buckets_with_policy_files() function
- determine_buckets() helper function
- show_interactive_help() helper function
- apply_policy_to_bucket() helper function
"""

import json
from unittest import mock

import pytest

import apply_block


class TestGetBucketsWithPolicyFiles:
    """Tests for get_buckets_with_policy_files() function"""

    def test_returns_empty_list_when_policies_dir_missing(self, setup_test_env):
        """Test that empty list is returned when policies directory doesn't exist"""
        result = apply_block.get_buckets_with_policy_files()
        assert result == []

    def test_returns_empty_list_when_policies_dir_empty(self, policies_dir):
        """Test that empty list is returned when policies directory is empty"""
        result = apply_block.get_buckets_with_policy_files()
        assert result == []

    def test_returns_bucket_names_from_policy_files(self, policies_dir):
        """Test that bucket names are extracted from policy files"""
        # Create policy files
        (policies_dir / "bucket1_policy.json").write_text("{}")
        (policies_dir / "bucket2_policy.json").write_text("{}")
        (policies_dir / "bucket3_policy.json").write_text("{}")

        result = apply_block.get_buckets_with_policy_files()
        assert set(result) == {"bucket1", "bucket2", "bucket3"}

    def test_ignores_non_policy_files(self, policies_dir):
        """Test that non-policy files are ignored"""
        # Create policy files and other files
        (policies_dir / "bucket1_policy.json").write_text("{}")
        (policies_dir / "bucket2_policy.json").write_text("{}")
        (policies_dir / "readme.txt").write_text("readme")
        (policies_dir / "config.json").write_text("{}")

        result = apply_block.get_buckets_with_policy_files()
        assert set(result) == {"bucket1", "bucket2"}

    def test_handles_special_bucket_names(self, policies_dir):
        """Test that bucket names with hyphens and dots are handled correctly"""
        (policies_dir / "my-bucket-123_policy.json").write_text("{}")
        (policies_dir / "bucket.example.com_policy.json").write_text("{}")

        result = apply_block.get_buckets_with_policy_files()
        assert set(result) == {"my-bucket-123", "bucket.example.com"}


class TestDetermineBuckets:
    """Tests for determine_buckets() helper function"""

    def test_returns_all_buckets_when_all_flag_set(self, create_policy_file, capsys):
        """Test that --all flag returns all available policy buckets"""
        create_policy_file("bucket1")
        create_policy_file("bucket2")

        args = mock.Mock(all=True, buckets=[])
        result = apply_block.determine_buckets(args)

        assert set(result) == {"bucket1", "bucket2"}
        captured = capsys.readouterr()
        assert "Found 2 policy file(s)" in captured.out

    def test_exits_when_all_flag_but_no_policies(self, setup_test_env, capsys):
        """Test that sys.exit(1) is called when --all flag but no policy files exist"""
        args = mock.Mock(all=True, buckets=[])

        with pytest.raises(SystemExit) as exc_info:
            apply_block.determine_buckets(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No policy files found" in captured.out

    def test_returns_specified_buckets(self, setup_test_env):
        """Test that specified bucket names are returned"""
        args = mock.Mock(all=False, buckets=["bucket1", "bucket2", "bucket3"])
        result = apply_block.determine_buckets(args)

        assert result == ["bucket1", "bucket2", "bucket3"]

    def test_shows_interactive_help_when_no_args(self, setup_test_env, capsys):
        """Test that interactive help is shown when no args provided"""
        args = mock.Mock(all=False, buckets=[])

        with pytest.raises(SystemExit) as exc_info:
            apply_block.determine_buckets(args)

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "No buckets specified" in captured.out


class TestShowInteractiveHelp:
    """Tests for show_interactive_help() helper function"""

    def test_shows_usage_instructions(self, setup_test_env, capsys):
        """Test that usage instructions are displayed"""
        apply_block.show_interactive_help()

        captured = capsys.readouterr()
        assert "No buckets specified" in captured.out
        assert "python apply_block.py bucket1 bucket2" in captured.out
        assert "python apply_block.py --all" in captured.out
        assert "Available policy files:" in captured.out

    def test_shows_available_policies(self, create_policy_file, capsys):
        """Test that available policy files are listed"""
        create_policy_file("bucket1")
        create_policy_file("bucket2")

        apply_block.show_interactive_help()

        captured = capsys.readouterr()
        assert "bucket1" in captured.out
        assert "bucket2" in captured.out

    def test_shows_none_when_no_policies(self, setup_test_env, capsys):
        """Test that (none found) is shown when no policies exist"""
        apply_block.show_interactive_help()

        captured = capsys.readouterr()
        assert "(none found)" in captured.out


def test_apply_policy_returns_false_when_policy_file_missing(policies_dir, capsys):
    """Test that False is returned when policy file doesn't exist"""
    result = apply_block.apply_policy_to_bucket("missing-bucket", dry_run=False)

    assert result is False
    captured = capsys.readouterr()
    assert "Policy file not found" in captured.out


def test_apply_policy_when_file_exists(create_policy_file, capsys):
    """Test that policy is applied when file exists"""
    create_policy_file("test-bucket")

    with mock.patch("apply_block.apply_bucket_policy") as mock_apply:
        result = apply_block.apply_policy_to_bucket("test-bucket", dry_run=False)

    assert result is True
    assert mock_apply.called
    captured = capsys.readouterr()
    assert "Applied policy to test-bucket" in captured.out


def test_apply_policy_dry_run(create_policy_file, capsys):
    """Test that --dry-run doesn't actually apply policy"""
    policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
    create_policy_file("test-bucket")

    with mock.patch("apply_block.apply_bucket_policy") as mock_apply:
        with mock.patch("apply_block.load_policy_from_file", return_value=policy_content):
            result = apply_block.apply_policy_to_bucket("test-bucket", dry_run=True)

    assert result is True
    assert not mock_apply.called
    captured = capsys.readouterr()
    assert "[DRY RUN]" in captured.out
    assert "Would apply" in captured.out


def test_apply_policy_handles_load_error(policies_dir, capsys):
    """Test that errors reading policy file are handled"""
    (policies_dir / "bad-bucket_policy.json").write_text("{invalid json")

    with mock.patch("apply_block.load_policy_from_file") as mock_load:
        mock_load.side_effect = ValueError("Invalid JSON")
        result = apply_block.apply_policy_to_bucket("bad-bucket", dry_run=False)

    assert result is False
    captured = capsys.readouterr()
    assert "Failed to apply policy" in captured.out


def test_apply_policy_handles_apply_error(create_policy_file, capsys):
    """Test that errors applying policy are handled"""
    create_policy_file("test-bucket", {"Version": "2012-10-17"})

    with mock.patch("apply_block.apply_bucket_policy") as mock_apply:
        mock_apply.side_effect = IOError("S3 error")
        result = apply_block.apply_policy_to_bucket("test-bucket", dry_run=False)

    assert result is False
    captured = capsys.readouterr()
    assert "Failed to apply policy" in captured.out


def test_apply_policy_handles_os_error(create_policy_file, capsys):
    """Test that OS errors are handled gracefully"""
    create_policy_file("test-bucket", {"Version": "2012-10-17"})

    with mock.patch("apply_block.load_policy_from_file") as mock_load:
        mock_load.side_effect = OSError("Permission denied")
        result = apply_block.apply_policy_to_bucket("test-bucket", dry_run=False)

    assert result is False
    captured = capsys.readouterr()
    assert "Failed to apply policy" in captured.out
