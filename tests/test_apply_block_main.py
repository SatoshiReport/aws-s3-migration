"""
Unit tests for apply_block.py main() function behavior

Tests cover:
- main() with specific bucket names
- main() with --all flag
- main() with --dry-run flag
- main() in interactive mode
"""

import json
from unittest import mock

import pytest

import apply_block


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
