import json
from pathlib import Path

import pytest

import aws_utils

# ============================================================================
# Tests for save_policy_to_file and load_policy_from_file
# ============================================================================


def test_save_and_load_policy_round_trip(tmp_path: Path):
    """Test that policy can be saved and loaded without data loss."""
    policy = {"name": "example"}
    path = tmp_path / "policy.json"

    aws_utils.save_policy_to_file(policy, path)
    raw = aws_utils.load_policy_from_file(path)

    assert json.loads(raw) == policy


def test_save_policy_to_file_creates_file(tmp_path: Path):
    """Test that save_policy_to_file creates a file."""
    policy = {"Version": "2012-10-17", "Statement": []}
    path = tmp_path / "new_policy.json"

    assert not path.exists()
    aws_utils.save_policy_to_file(policy, path)
    assert path.exists()


def test_save_policy_to_file_with_complex_policy(tmp_path: Path):
    """Test saving a complex realistic policy structure."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowOnlyMeFullAccess",
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::123456789012:user/test"},
                "Action": "s3:*",
                "Resource": ["arn:aws:s3:::bucket", "arn:aws:s3:::bucket/*"],
            }
        ],
    }
    path = tmp_path / "complex_policy.json"

    aws_utils.save_policy_to_file(policy, path)
    raw = aws_utils.load_policy_from_file(path)
    loaded = json.loads(raw)

    assert loaded == policy
    assert loaded["Statement"][0]["Sid"] == "AllowOnlyMeFullAccess"


def test_load_policy_from_file_returns_string(tmp_path: Path):
    """Test that load_policy_from_file returns a string."""
    policy = {"key": "value"}
    path = tmp_path / "policy.json"

    aws_utils.save_policy_to_file(policy, path)
    result = aws_utils.load_policy_from_file(path)

    assert isinstance(result, str)


def test_save_policy_to_file_uses_utf8_encoding(tmp_path: Path):
    """Test that save_policy_to_file uses UTF-8 encoding."""
    policy = {"description": "Test with special chars: é, ñ, 中文"}
    path = tmp_path / "unicode_policy.json"

    aws_utils.save_policy_to_file(policy, path)

    # Read raw bytes to verify encoding
    with open(path, "rb") as f:
        content = f.read()
    # Should be valid UTF-8
    content.decode("utf-8")


def test_save_policy_to_file_overwrites_existing(tmp_path: Path):
    """Test that save_policy_to_file overwrites existing files."""
    path = tmp_path / "policy.json"

    # First save
    policy1 = {"version": 1}
    aws_utils.save_policy_to_file(policy1, path)

    # Second save
    policy2 = {"version": 2, "updated": True}
    aws_utils.save_policy_to_file(policy2, path)

    # Verify second policy is in file
    raw = aws_utils.load_policy_from_file(path)
    loaded = json.loads(raw)

    assert loaded["version"] == 2
    assert "updated" in loaded


def test_load_policy_from_file_error_nonexistent(tmp_path: Path):
    """Test that load_policy_from_file raises error for nonexistent file."""
    path = tmp_path / "nonexistent.json"

    with pytest.raises(FileNotFoundError):
        aws_utils.load_policy_from_file(path)


def test_save_policy_to_file_with_empty_dict(tmp_path: Path):
    """Test saving empty policy dictionary."""
    policy = {}
    path = tmp_path / "empty_policy.json"

    aws_utils.save_policy_to_file(policy, path)
    raw = aws_utils.load_policy_from_file(path)

    assert json.loads(raw) == {}
