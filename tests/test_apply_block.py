"""
Comprehensive unit tests for apply_block.py

Tests cover:
- get_buckets_with_policy_files() function
- main() with specific bucket names
- main() with --all flag
- main() with --dry-run flag
- main() in interactive mode
- _determine_buckets() helper function
- _show_interactive_help() helper function
- _apply_policy_to_bucket() helper function
- Error handling (missing policy files, apply failures)
- sys.exit and argparse behavior
"""

import json
from unittest import mock

import pytest

import apply_block


class TestGetBucketsWithPolicyFiles:
    """Tests for get_buckets_with_policy_files() function"""

    def test_returns_empty_list_when_policies_dir_missing(self, tmp_path, monkeypatch):
        """Test that empty list is returned when policies directory doesn't exist"""
        monkeypatch.chdir(tmp_path)
        result = apply_block.get_buckets_with_policy_files()
        assert result == []

    def test_returns_empty_list_when_policies_dir_empty(self, tmp_path, monkeypatch):
        """Test that empty list is returned when policies directory is empty"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()
        result = apply_block.get_buckets_with_policy_files()
        assert result == []

    def test_returns_bucket_names_from_policy_files(self, tmp_path, monkeypatch):
        """Test that bucket names are extracted from policy files"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        # Create policy files
        (policies_dir / "bucket1_policy.json").write_text("{}")
        (policies_dir / "bucket2_policy.json").write_text("{}")
        (policies_dir / "bucket3_policy.json").write_text("{}")

        result = apply_block.get_buckets_with_policy_files()
        assert set(result) == {"bucket1", "bucket2", "bucket3"}

    def test_ignores_non_policy_files(self, tmp_path, monkeypatch):
        """Test that non-policy files are ignored"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        # Create policy files and other files
        (policies_dir / "bucket1_policy.json").write_text("{}")
        (policies_dir / "bucket2_policy.json").write_text("{}")
        (policies_dir / "readme.txt").write_text("readme")
        (policies_dir / "config.json").write_text("{}")

        result = apply_block.get_buckets_with_policy_files()
        assert set(result) == {"bucket1", "bucket2"}

    def test_handles_special_bucket_names(self, tmp_path, monkeypatch):
        """Test that bucket names with hyphens and dots are handled correctly"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        (policies_dir / "my-bucket-123_policy.json").write_text("{}")
        (policies_dir / "bucket.example.com_policy.json").write_text("{}")

        result = apply_block.get_buckets_with_policy_files()
        assert set(result) == {"my-bucket-123", "bucket.example.com"}


class TestDetermineBuckets:
    """Tests for _determine_buckets() helper function"""

    def test_returns_all_buckets_when_all_flag_set(self, tmp_path, monkeypatch, capsys):
        """Test that --all flag returns all available policy buckets"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()
        (policies_dir / "bucket1_policy.json").write_text("{}")
        (policies_dir / "bucket2_policy.json").write_text("{}")

        args = mock.Mock(all=True, buckets=[])
        result = apply_block._determine_buckets(args)

        assert set(result) == {"bucket1", "bucket2"}
        captured = capsys.readouterr()
        assert "Found 2 policy file(s)" in captured.out

    def test_exits_when_all_flag_but_no_policies(self, tmp_path, monkeypatch, capsys):
        """Test that sys.exit(1) is called when --all flag but no policy files exist"""
        monkeypatch.chdir(tmp_path)
        args = mock.Mock(all=True, buckets=[])

        with pytest.raises(SystemExit) as exc_info:
            apply_block._determine_buckets(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No policy files found" in captured.out

    def test_returns_specified_buckets(self, tmp_path, monkeypatch):
        """Test that specified bucket names are returned"""
        monkeypatch.chdir(tmp_path)
        args = mock.Mock(all=False, buckets=["bucket1", "bucket2", "bucket3"])
        result = apply_block._determine_buckets(args)

        assert result == ["bucket1", "bucket2", "bucket3"]

    def test_shows_interactive_help_when_no_args(self, tmp_path, monkeypatch, capsys):
        """Test that interactive help is shown when no args provided"""
        monkeypatch.chdir(tmp_path)
        args = mock.Mock(all=False, buckets=[])

        with pytest.raises(SystemExit) as exc_info:
            apply_block._determine_buckets(args)

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "No buckets specified" in captured.out


class TestShowInteractiveHelp:
    """Tests for _show_interactive_help() helper function"""

    def test_shows_usage_instructions(self, tmp_path, monkeypatch, capsys):
        """Test that usage instructions are displayed"""
        monkeypatch.chdir(tmp_path)
        apply_block._show_interactive_help()

        captured = capsys.readouterr()
        assert "No buckets specified" in captured.out
        assert "python apply_block.py bucket1 bucket2" in captured.out
        assert "python apply_block.py --all" in captured.out
        assert "Available policy files:" in captured.out

    def test_shows_available_policies(self, tmp_path, monkeypatch, capsys):
        """Test that available policy files are listed"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()
        (policies_dir / "bucket1_policy.json").write_text("{}")
        (policies_dir / "bucket2_policy.json").write_text("{}")

        apply_block._show_interactive_help()

        captured = capsys.readouterr()
        assert "bucket1" in captured.out
        assert "bucket2" in captured.out

    def test_shows_none_when_no_policies(self, tmp_path, monkeypatch, capsys):
        """Test that (none found) is shown when no policies exist"""
        monkeypatch.chdir(tmp_path)
        apply_block._show_interactive_help()

        captured = capsys.readouterr()
        assert "(none found)" in captured.out


class TestApplyPolicyToBucket:
    """Tests for _apply_policy_to_bucket() helper function"""

    def test_returns_false_when_policy_file_missing(self, tmp_path, monkeypatch, capsys):
        """Test that False is returned when policy file doesn't exist"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        result = apply_block._apply_policy_to_bucket("missing-bucket", dry_run=False)

        assert result is False
        captured = capsys.readouterr()
        assert "Policy file not found" in captured.out

    def test_applies_policy_when_file_exists(self, tmp_path, monkeypatch, capsys):
        """Test that policy is applied when file exists"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "test-bucket_policy.json").write_text(policy_content)

        with mock.patch("apply_block.apply_bucket_policy") as mock_apply:
            result = apply_block._apply_policy_to_bucket("test-bucket", dry_run=False)

        assert result is True
        assert mock_apply.called
        captured = capsys.readouterr()
        assert "Applied policy to test-bucket" in captured.out

    def test_dry_run_does_not_apply_policy(self, tmp_path, monkeypatch, capsys):
        """Test that --dry-run doesn't actually apply policy"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "test-bucket_policy.json").write_text(policy_content)

        with mock.patch("apply_block.apply_bucket_policy") as mock_apply:
            with mock.patch("apply_block.load_policy_from_file", return_value=policy_content):
                result = apply_block._apply_policy_to_bucket("test-bucket", dry_run=True)

        assert result is True
        assert not mock_apply.called
        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        assert "Would apply" in captured.out

    def test_handles_load_policy_file_error(self, tmp_path, monkeypatch, capsys):
        """Test that errors reading policy file are handled"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()
        (policies_dir / "bad-bucket_policy.json").write_text("{invalid json")

        with mock.patch("apply_block.load_policy_from_file") as mock_load:
            mock_load.side_effect = ValueError("Invalid JSON")
            result = apply_block._apply_policy_to_bucket("bad-bucket", dry_run=False)

        assert result is False
        captured = capsys.readouterr()
        assert "Failed to apply policy" in captured.out

    def test_handles_apply_policy_error(self, tmp_path, monkeypatch, capsys):
        """Test that errors applying policy are handled"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17"})
        (policies_dir / "test-bucket_policy.json").write_text(policy_content)

        with mock.patch("apply_block.apply_bucket_policy") as mock_apply:
            mock_apply.side_effect = IOError("S3 error")
            result = apply_block._apply_policy_to_bucket("test-bucket", dry_run=False)

        assert result is False
        captured = capsys.readouterr()
        assert "Failed to apply policy" in captured.out

    def test_handles_os_error(self, tmp_path, monkeypatch, capsys):
        """Test that OS errors are handled gracefully"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17"})
        (policies_dir / "test-bucket_policy.json").write_text(policy_content)

        with mock.patch("apply_block.load_policy_from_file") as mock_load:
            mock_load.side_effect = OSError("Permission denied")
            result = apply_block._apply_policy_to_bucket("test-bucket", dry_run=False)

        assert result is False
        captured = capsys.readouterr()
        assert "Failed to apply policy" in captured.out


class TestMainWithSpecificBuckets:
    """Tests for main() function with specific bucket names as arguments"""

    def test_main_with_single_bucket(self, tmp_path, monkeypatch, capsys):
        """Test main() with a single bucket name"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "test-bucket_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", "test-bucket"]):
            with mock.patch("apply_block.apply_bucket_policy"):
                apply_block.main()

        captured = capsys.readouterr()
        assert "Applied policy to test-bucket" in captured.out
        assert "Completed applying policies to 1 bucket(s)" in captured.out

    def test_main_with_multiple_buckets(self, tmp_path, monkeypatch, capsys):
        """Test main() with multiple bucket names"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "bucket1_policy.json").write_text(policy_content)
        (policies_dir / "bucket2_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", "bucket1", "bucket2"]):
            with mock.patch("apply_block.apply_bucket_policy"):
                apply_block.main()

        captured = capsys.readouterr()
        assert "Applied policy to bucket1" in captured.out
        assert "Applied policy to bucket2" in captured.out
        assert "Completed applying policies to 2 bucket(s)" in captured.out

    def test_main_with_nonexistent_policy_file(self, tmp_path, monkeypatch, capsys):
        """Test main() with bucket that has no policy file"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        with mock.patch("sys.argv", ["apply_block.py", "nonexistent"]):
            apply_block.main()

        captured = capsys.readouterr()
        assert "Policy file not found" in captured.out

    def test_main_continues_after_error(self, tmp_path, monkeypatch, capsys):
        """Test that main() continues processing after an error"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "bucket2_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", "bucket1", "bucket2"]):
            with mock.patch("apply_block.apply_bucket_policy"):
                apply_block.main()

        captured = capsys.readouterr()
        assert "Policy file not found" in captured.out  # bucket1 error
        assert "Applied policy to bucket2" in captured.out  # bucket2 succeeds


class TestMainWithAllFlag:
    """Tests for main() function with --all flag"""

    def test_main_with_all_flag(self, tmp_path, monkeypatch, capsys):
        """Test main() with --all flag processes all available policies"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "bucket1_policy.json").write_text(policy_content)
        (policies_dir / "bucket2_policy.json").write_text(policy_content)
        (policies_dir / "bucket3_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", "--all"]):
            with mock.patch("apply_block.apply_bucket_policy"):
                apply_block.main()

        captured = capsys.readouterr()
        assert "Found 3 policy file(s)" in captured.out
        assert "Applied policy to bucket1" in captured.out
        assert "Applied policy to bucket2" in captured.out
        assert "Applied policy to bucket3" in captured.out

    def test_main_all_flag_with_no_policies(self, tmp_path, monkeypatch, capsys):
        """Test main() with --all flag when no policies exist"""
        monkeypatch.chdir(tmp_path)

        with mock.patch("sys.argv", ["apply_block.py", "--all"]):
            with pytest.raises(SystemExit) as exc_info:
                apply_block.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No policy files found" in captured.out


class TestMainWithDryRunFlag:
    """Tests for main() function with --dry-run flag"""

    def test_main_dry_run_with_specific_buckets(self, tmp_path, monkeypatch, capsys):
        """Test main() with --dry-run flag doesn't apply policies"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "bucket1_policy.json").write_text(policy_content)
        (policies_dir / "bucket2_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", "--dry-run", "bucket1", "bucket2"]):
            with mock.patch("apply_block.apply_bucket_policy") as mock_apply:
                apply_block.main()

        assert not mock_apply.called
        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        assert "Would apply" in captured.out
        assert "Dry run completed" in captured.out

    def test_main_dry_run_with_all_flag(self, tmp_path, monkeypatch, capsys):
        """Test main() with --dry-run --all flags"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "bucket1_policy.json").write_text(policy_content)
        (policies_dir / "bucket2_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", "--dry-run", "--all"]):
            with mock.patch("apply_block.apply_bucket_policy") as mock_apply:
                apply_block.main()

        assert not mock_apply.called
        captured = capsys.readouterr()
        assert "Found 2 policy file(s)" in captured.out
        assert "[DRY RUN]" in captured.out
        assert "Dry run completed" in captured.out


class TestMainInteractiveMode:
    """Tests for main() function in interactive mode (no arguments)"""

    def test_main_interactive_mode_shows_help_and_exits(self, tmp_path, monkeypatch, capsys):
        """Test that running with no args shows help and exits"""
        monkeypatch.chdir(tmp_path)

        with mock.patch("sys.argv", ["apply_block.py"]):
            with pytest.raises(SystemExit) as exc_info:
                apply_block.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "No buckets specified" in captured.out
        assert "Available policy files:" in captured.out

    def test_main_interactive_mode_shows_available_policies(self, tmp_path, monkeypatch, capsys):
        """Test that interactive mode lists available policies"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "my-bucket_policy.json").write_text(policy_content)
        (policies_dir / "another-bucket_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py"]):
            with pytest.raises(SystemExit) as exc_info:
                apply_block.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "my-bucket" in captured.out
        assert "another-bucket" in captured.out


class TestMainErrorHandling:
    """Tests for error handling in main() function"""

    def test_main_handles_policy_load_errors_gracefully(self, tmp_path, monkeypatch, capsys):
        """Test that corrupted policy files don't crash the program"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        # Create a policy file with invalid JSON
        (policies_dir / "bucket1_policy.json").write_text("{invalid json")

        with mock.patch("sys.argv", ["apply_block.py", "bucket1"]):
            with mock.patch("apply_block.load_policy_from_file") as mock_load:
                mock_load.side_effect = ValueError("Invalid JSON")
                apply_block.main()

        captured = capsys.readouterr()
        assert "Failed to apply policy" in captured.out

    def test_main_handles_aws_api_errors_gracefully(self, tmp_path, monkeypatch, capsys):
        """Test that AWS API errors don't crash the program"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "bucket1_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", "bucket1"]):
            with mock.patch("apply_block.apply_bucket_policy") as mock_apply:
                mock_apply.side_effect = OSError("AccessDenied")
                apply_block.main()

        captured = capsys.readouterr()
        assert "Failed to apply policy" in captured.out

    def test_main_processes_multiple_buckets_despite_failures(self, tmp_path, monkeypatch, capsys):
        """Test that main() continues processing despite individual failures"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "bucket1_policy.json").write_text(policy_content)
        (policies_dir / "bucket2_policy.json").write_text(policy_content)
        (policies_dir / "bucket3_policy.json").write_text(policy_content)

        def apply_side_effect(bucket, policy):
            if bucket == "bucket2":
                raise IOError("S3 error")

        with mock.patch("sys.argv", ["apply_block.py", "bucket1", "bucket2", "bucket3"]):
            with mock.patch("apply_block.apply_bucket_policy") as mock_apply:
                mock_apply.side_effect = apply_side_effect
                apply_block.main()

        captured = capsys.readouterr()
        # bucket1 should succeed or be processed
        # bucket2 should fail
        assert "bucket2" in captured.out or "Failed to apply" in captured.out
        # bucket3 should still be attempted
        assert "3 bucket(s)" in captured.out


class TestMainOutputMessages:
    """Tests for output messages and formatting"""

    def test_main_shows_completion_message_for_single_bucket(self, tmp_path, monkeypatch, capsys):
        """Test that completion message shows correct bucket count"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "bucket1_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", "bucket1"]):
            with mock.patch("apply_block.apply_bucket_policy"):
                apply_block.main()

        captured = capsys.readouterr()
        assert "Completed applying policies to 1 bucket(s)" in captured.out

    def test_main_shows_completion_message_for_multiple_buckets(
        self, tmp_path, monkeypatch, capsys
    ):
        """Test that completion message shows correct bucket count"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "bucket1_policy.json").write_text(policy_content)
        (policies_dir / "bucket2_policy.json").write_text(policy_content)
        (policies_dir / "bucket3_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", "bucket1", "bucket2", "bucket3"]):
            with mock.patch("apply_block.apply_bucket_policy"):
                apply_block.main()

        captured = capsys.readouterr()
        assert "Completed applying policies to 3 bucket(s)" in captured.out

    def test_main_shows_dry_run_message(self, tmp_path, monkeypatch, capsys):
        """Test that dry run completion message is shown"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "bucket1_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", "--dry-run", "bucket1"]):
            apply_block.main()

        captured = capsys.readouterr()
        assert "Dry run completed. No changes were made." in captured.out


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_handles_bucket_names_with_numbers(self, tmp_path, monkeypatch, capsys):
        """Test that bucket names with numbers are handled correctly"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "bucket123_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", "bucket123"]):
            with mock.patch("apply_block.apply_bucket_policy"):
                apply_block.main()

        captured = capsys.readouterr()
        assert "Applied policy to bucket123" in captured.out

    def test_handles_long_bucket_names(self, tmp_path, monkeypatch, capsys):
        """Test that long bucket names are handled correctly"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        long_name = "very-long-bucket-name-with-many-hyphens-12345"
        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / f"{long_name}_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", long_name]):
            with mock.patch("apply_block.apply_bucket_policy"):
                apply_block.main()

        captured = capsys.readouterr()
        assert f"Applied policy to {long_name}" in captured.out

    def test_handles_empty_policy_file(self, tmp_path, monkeypatch, capsys):
        """Test handling of empty policy files"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        (policies_dir / "bucket1_policy.json").write_text("")

        with mock.patch("sys.argv", ["apply_block.py", "bucket1"]):
            with mock.patch("apply_block.load_policy_from_file", return_value=""):
                with mock.patch("apply_block.apply_bucket_policy"):
                    apply_block.main()

        captured = capsys.readouterr()
        assert "Applied policy" in captured.out

    def test_duplicate_buckets_in_arguments(self, tmp_path, monkeypatch, capsys):
        """Test that duplicate bucket names are processed"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "bucket1_policy.json").write_text(policy_content)

        with mock.patch("sys.argv", ["apply_block.py", "bucket1", "bucket1"]):
            with mock.patch("apply_block.apply_bucket_policy"):
                apply_block.main()

        captured = capsys.readouterr()
        # Both instances should be processed
        assert "Completed applying policies to 2 bucket(s)" in captured.out


class TestModuleExecution:
    """Tests for module-level execution"""

    def test_module_can_be_executed(self, tmp_path, monkeypatch):
        """Test that the module can be executed directly"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy_content = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]})
        (policies_dir / "test-bucket_policy.json").write_text(policy_content)

        # Test that main() is callable and works
        with mock.patch("sys.argv", ["apply_block.py", "test-bucket"]):
            with mock.patch("apply_block.apply_bucket_policy"):
                # This should not raise any exceptions
                apply_block.main()
