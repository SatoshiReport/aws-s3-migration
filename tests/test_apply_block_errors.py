"""
Unit tests for apply_block.py error handling and edge cases

Tests cover:
- Error handling (missing policy files, apply failures)
- Edge cases and boundary conditions
- Module execution tests
"""

import json
from unittest import mock

import apply_block


class TestMainErrorHandling:
    """Tests for error handling in main() function"""

    def test_main_handles_policy_load_errors_gracefully(self, tmp_path, monkeypatch, capsys):
        """Test that corrupted policy files don't crash the program"""
        monkeypatch.chdir(tmp_path)
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        # Create a policy file with invalid JSON
        (policies_dir / "bucket1_policy.json").write_text("{invalid json")

        error_message = "Invalid JSON"

        with mock.patch("sys.argv", ["apply_block.py", "bucket1"]):
            with mock.patch("apply_block.load_policy_from_file") as mock_load:
                mock_load.side_effect = ValueError(error_message)
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

        error_message = "AccessDenied"

        with mock.patch("sys.argv", ["apply_block.py", "bucket1"]):
            with mock.patch("apply_block.apply_bucket_policy") as mock_apply:
                mock_apply.side_effect = OSError(error_message)
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

        failure_message = "S3 error"

        def apply_side_effect(bucket, policy):
            if bucket == "bucket2":
                raise IOError(failure_message)

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
