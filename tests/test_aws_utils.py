import json
from pathlib import Path
from unittest import mock

import pytest

import aws_utils

# ============================================================================
# Tests for generate_restrictive_bucket_policy
# ============================================================================


def test_generate_restrictive_bucket_policy_structure():
    """Test that generated policy has correct structure and values."""
    policy = aws_utils.generate_restrictive_bucket_policy(
        "arn:aws:iam::123456789012:user/test-user", "example-bucket"
    )
    statement = policy["Statement"][0]

    assert policy["Version"] == "2012-10-17"
    assert statement["Principal"]["AWS"] == "arn:aws:iam::123456789012:user/test-user"
    assert statement["Resource"] == [
        "arn:aws:s3:::example-bucket",
        "arn:aws:s3:::example-bucket/*",
    ]


def test_generate_restrictive_bucket_policy_with_different_arn():
    """Test policy generation with different IAM user ARN."""
    policy = aws_utils.generate_restrictive_bucket_policy(
        "arn:aws:iam::987654321098:user/another-user", "my-bucket"
    )
    statement = policy["Statement"][0]

    assert statement["Principal"]["AWS"] == "arn:aws:iam::987654321098:user/another-user"
    assert "arn:aws:s3:::my-bucket" in statement["Resource"]


def test_generate_restrictive_bucket_policy_with_special_bucket_name():
    """Test policy generation with bucket name containing hyphens and numbers."""
    policy = aws_utils.generate_restrictive_bucket_policy(
        "arn:aws:iam::123456789012:user/test", "my-bucket-2024-prod"
    )
    statement = policy["Statement"][0]

    assert statement["Resource"] == [
        "arn:aws:s3:::my-bucket-2024-prod",
        "arn:aws:s3:::my-bucket-2024-prod/*",
    ]


def test_generate_restrictive_bucket_policy_action_is_wildcard():
    """Test that generated policy grants all S3 actions."""
    policy = aws_utils.generate_restrictive_bucket_policy(
        "arn:aws:iam::123456789012:user/test-user", "bucket"
    )
    statement = policy["Statement"][0]

    assert statement["Action"] == "s3:*"
    assert statement["Effect"] == "Allow"


def test_generate_restrictive_bucket_policy_includes_sid():
    """Test that generated policy includes Sid for identification."""
    policy = aws_utils.generate_restrictive_bucket_policy(
        "arn:aws:iam::123456789012:user/test-user", "bucket"
    )
    statement = policy["Statement"][0]

    assert statement["Sid"] == "AllowOnlyMeFullAccess"


def test_generate_restrictive_bucket_policy_returns_dict():
    """Test that function returns a dictionary object."""
    policy = aws_utils.generate_restrictive_bucket_policy(
        "arn:aws:iam::123456789012:user/test-user", "bucket"
    )

    assert isinstance(policy, dict)
    assert isinstance(policy["Statement"], list)
    assert len(policy["Statement"]) == 1


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


# ============================================================================
# Tests for get_boto3_clients
# ============================================================================


def test_get_boto3_clients_returns_three_clients():
    """Test that get_boto3_clients returns three clients."""
    with mock.patch("aws_utils.boto3.client") as mock_client:
        mock_client.side_effect = [mock.Mock(), mock.Mock(), mock.Mock()]

        s3, sts, iam = aws_utils.get_boto3_clients()

        assert s3 is not None
        assert sts is not None
        assert iam is not None


def test_get_boto3_clients_creates_s3_sts_iam():
    """Test that get_boto3_clients creates clients in correct order."""
    with mock.patch("aws_utils.boto3.client") as mock_client:
        mock_s3, mock_sts, mock_iam = mock.Mock(), mock.Mock(), mock.Mock()
        mock_client.side_effect = [mock_s3, mock_sts, mock_iam]

        s3, sts, iam = aws_utils.get_boto3_clients()

        assert mock_client.call_count == 3
        calls = mock_client.call_args_list
        assert calls[0] == mock.call("s3")
        assert calls[1] == mock.call("sts")
        assert calls[2] == mock.call("iam")


def test_get_boto3_clients_returns_tuple():
    """Test that get_boto3_clients returns a tuple."""
    with mock.patch("aws_utils.boto3.client") as mock_client:
        mock_client.side_effect = [mock.Mock(), mock.Mock(), mock.Mock()]

        result = aws_utils.get_boto3_clients()

        assert isinstance(result, tuple)
        assert len(result) == 3


# ============================================================================
# Tests for list_s3_buckets
# ============================================================================


def test_list_s3_buckets_returns_bucket_names():
    """Test that list_s3_buckets returns bucket names as list."""
    fake_s3 = mock.Mock()
    fake_s3.list_buckets.return_value = {"Buckets": [{"Name": "a"}, {"Name": "b"}]}

    with mock.patch(
        "aws_utils.get_boto3_clients", return_value=(fake_s3, mock.Mock(), mock.Mock())
    ):
        buckets = aws_utils.list_s3_buckets()

    assert buckets == ["a", "b"]
    fake_s3.list_buckets.assert_called_once()


def test_list_s3_buckets_returns_empty_list_when_no_buckets():
    """Test that list_s3_buckets returns empty list when no buckets exist."""
    fake_s3 = mock.Mock()
    fake_s3.list_buckets.return_value = {"Buckets": []}

    with mock.patch(
        "aws_utils.get_boto3_clients", return_value=(fake_s3, mock.Mock(), mock.Mock())
    ):
        buckets = aws_utils.list_s3_buckets()

    assert buckets == []


def test_list_s3_buckets_returns_list_type():
    """Test that list_s3_buckets always returns a list."""
    fake_s3 = mock.Mock()
    fake_s3.list_buckets.return_value = {"Buckets": [{"Name": "bucket1"}]}

    with mock.patch(
        "aws_utils.get_boto3_clients", return_value=(fake_s3, mock.Mock(), mock.Mock())
    ):
        buckets = aws_utils.list_s3_buckets()

    assert isinstance(buckets, list)


def test_list_s3_buckets_with_many_buckets():
    """Test list_s3_buckets with large number of buckets."""
    bucket_list = [{"Name": f"bucket-{i}"} for i in range(100)]
    fake_s3 = mock.Mock()
    fake_s3.list_buckets.return_value = {"Buckets": bucket_list}

    with mock.patch(
        "aws_utils.get_boto3_clients", return_value=(fake_s3, mock.Mock(), mock.Mock())
    ):
        buckets = aws_utils.list_s3_buckets()

    assert len(buckets) == 100
    assert buckets[0] == "bucket-0"
    assert buckets[99] == "bucket-99"


def test_list_s3_buckets_with_special_names():
    """Test list_s3_buckets with bucket names containing special characters."""
    bucket_list = [
        {"Name": "bucket-with-dash"},
        {"Name": "bucket.with.dot"},
        {"Name": "bucket123"},
    ]
    fake_s3 = mock.Mock()
    fake_s3.list_buckets.return_value = {"Buckets": bucket_list}

    with mock.patch(
        "aws_utils.get_boto3_clients", return_value=(fake_s3, mock.Mock(), mock.Mock())
    ):
        buckets = aws_utils.list_s3_buckets()

    assert "bucket-with-dash" in buckets
    assert "bucket.with.dot" in buckets
    assert "bucket123" in buckets


def test_list_s3_buckets_error_handling():
    """Test that list_s3_buckets propagates boto3 exceptions."""
    fake_s3 = mock.Mock()
    fake_s3.list_buckets.side_effect = Exception("AWS Error")

    with mock.patch(
        "aws_utils.get_boto3_clients", return_value=(fake_s3, mock.Mock(), mock.Mock())
    ):
        with pytest.raises(Exception, match="AWS Error"):
            aws_utils.list_s3_buckets()


# ============================================================================
# Tests for get_aws_identity
# ============================================================================


def test_get_aws_identity_fetches_identity_details():
    """Test that get_aws_identity returns all required identity details."""
    fake_s3 = mock.Mock()
    fake_sts = mock.Mock()
    fake_sts.get_caller_identity.return_value = {"Account": "123456789012"}

    fake_iam = mock.Mock()
    fake_iam.get_user.return_value = {
        "User": {"UserName": "tester", "Arn": "arn:aws:iam::123:user/tester"}
    }

    with mock.patch("aws_utils.get_boto3_clients", return_value=(fake_s3, fake_sts, fake_iam)):
        identity = aws_utils.get_aws_identity()

    assert identity == {
        "account_id": "123456789012",
        "username": "tester",
        "user_arn": "arn:aws:iam::123:user/tester",
    }


def test_get_aws_identity_calls_correct_apis():
    """Test that get_aws_identity calls the correct AWS APIs."""
    fake_s3 = mock.Mock()
    fake_sts = mock.Mock()
    fake_sts.get_caller_identity.return_value = {"Account": "111111111111"}

    fake_iam = mock.Mock()
    fake_iam.get_user.return_value = {
        "User": {"UserName": "myuser", "Arn": "arn:aws:iam::111111111111:user/myuser"}
    }

    with mock.patch("aws_utils.get_boto3_clients", return_value=(fake_s3, fake_sts, fake_iam)):
        aws_utils.get_aws_identity()

    fake_sts.get_caller_identity.assert_called_once()
    fake_iam.get_user.assert_called_once()


def test_get_aws_identity_returns_dict():
    """Test that get_aws_identity returns a dictionary."""
    fake_s3 = mock.Mock()
    fake_sts = mock.Mock()
    fake_sts.get_caller_identity.return_value = {"Account": "123456789012"}

    fake_iam = mock.Mock()
    fake_iam.get_user.return_value = {
        "User": {"UserName": "user", "Arn": "arn:aws:iam::123456789012:user/user"}
    }

    with mock.patch("aws_utils.get_boto3_clients", return_value=(fake_s3, fake_sts, fake_iam)):
        result = aws_utils.get_aws_identity()

    assert isinstance(result, dict)
    assert set(result.keys()) == {"account_id", "username", "user_arn"}


def test_get_aws_identity_with_different_user_arn_formats():
    """Test get_aws_identity with different IAM user ARN formats."""
    fake_s3 = mock.Mock()
    fake_sts = mock.Mock()
    fake_sts.get_caller_identity.return_value = {"Account": "123456789012"}

    fake_iam = mock.Mock()
    fake_iam.get_user.return_value = {
        "User": {
            "UserName": "assumed-role-user",
            "Arn": "arn:aws:iam::123456789012:user/path/to/assumed-role-user",
        }
    }

    with mock.patch("aws_utils.get_boto3_clients", return_value=(fake_s3, fake_sts, fake_iam)):
        identity = aws_utils.get_aws_identity()

    assert identity["username"] == "assumed-role-user"
    assert "assumed-role-user" in identity["user_arn"]


def test_get_aws_identity_error_sts_failure():
    """Test that get_aws_identity raises exception if STS call fails."""
    fake_s3 = mock.Mock()
    fake_sts = mock.Mock()
    fake_sts.get_caller_identity.side_effect = Exception("STS Error")

    fake_iam = mock.Mock()

    with mock.patch("aws_utils.get_boto3_clients", return_value=(fake_s3, fake_sts, fake_iam)):
        with pytest.raises(Exception, match="STS Error"):
            aws_utils.get_aws_identity()


def test_get_aws_identity_error_iam_failure():
    """Test that get_aws_identity raises exception if IAM call fails."""
    fake_s3 = mock.Mock()
    fake_sts = mock.Mock()
    fake_sts.get_caller_identity.return_value = {"Account": "123456789012"}

    fake_iam = mock.Mock()
    fake_iam.get_user.side_effect = Exception("IAM Error")

    with mock.patch("aws_utils.get_boto3_clients", return_value=(fake_s3, fake_sts, fake_iam)):
        with pytest.raises(Exception, match="IAM Error"):
            aws_utils.get_aws_identity()


def test_get_aws_identity_error_missing_account_in_response():
    """Test that get_aws_identity handles missing Account in STS response."""
    fake_s3 = mock.Mock()
    fake_sts = mock.Mock()
    fake_sts.get_caller_identity.return_value = {}  # Missing Account

    fake_iam = mock.Mock()

    with mock.patch("aws_utils.get_boto3_clients", return_value=(fake_s3, fake_sts, fake_iam)):
        with pytest.raises(KeyError):
            aws_utils.get_aws_identity()


def test_get_aws_identity_error_missing_user_in_response():
    """Test that get_aws_identity handles missing User in IAM response."""
    fake_s3 = mock.Mock()
    fake_sts = mock.Mock()
    fake_sts.get_caller_identity.return_value = {"Account": "123456789012"}

    fake_iam = mock.Mock()
    fake_iam.get_user.return_value = {}  # Missing User

    with mock.patch("aws_utils.get_boto3_clients", return_value=(fake_s3, fake_sts, fake_iam)):
        with pytest.raises(KeyError):
            aws_utils.get_aws_identity()


# ============================================================================
# Tests for apply_bucket_policy
# ============================================================================


def test_apply_bucket_policy_invokes_s3_update():
    """Test that apply_bucket_policy calls put_bucket_policy."""
    fake_s3 = mock.Mock()
    fake_sts = mock.Mock()
    fake_iam = mock.Mock()

    with mock.patch("aws_utils.get_boto3_clients", return_value=(fake_s3, fake_sts, fake_iam)):
        aws_utils.apply_bucket_policy("bucket", "{}")

    fake_s3.put_bucket_policy.assert_called_once_with(Bucket="bucket", Policy="{}")


def test_apply_bucket_policy_with_complex_policy_json():
    """Test apply_bucket_policy with complex policy JSON."""
    policy_json = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123456789012:user/test"},
                    "Action": "s3:*",
                    "Resource": ["arn:aws:s3:::bucket", "arn:aws:s3:::bucket/*"],
                }
            ],
        }
    )

    fake_s3 = mock.Mock()
    fake_sts = mock.Mock()
    fake_iam = mock.Mock()

    with mock.patch("aws_utils.get_boto3_clients", return_value=(fake_s3, fake_sts, fake_iam)):
        aws_utils.apply_bucket_policy("my-bucket", policy_json)

    fake_s3.put_bucket_policy.assert_called_once_with(Bucket="my-bucket", Policy=policy_json)


def test_apply_bucket_policy_with_different_bucket_names():
    """Test apply_bucket_policy with various bucket names."""
    bucket_names = ["bucket1", "my-bucket", "bucket-prod-2024"]

    for bucket_name in bucket_names:
        fake_s3 = mock.Mock()
        fake_sts = mock.Mock()
        fake_iam = mock.Mock()

        with mock.patch("aws_utils.get_boto3_clients", return_value=(fake_s3, fake_sts, fake_iam)):
            aws_utils.apply_bucket_policy(bucket_name, "{}")

        fake_s3.put_bucket_policy.assert_called_once_with(Bucket=bucket_name, Policy="{}")


def test_apply_bucket_policy_error_handling():
    """Test that apply_bucket_policy propagates boto3 exceptions."""
    fake_s3 = mock.Mock()
    fake_s3.put_bucket_policy.side_effect = Exception("Access Denied")
    fake_sts = mock.Mock()
    fake_iam = mock.Mock()

    with mock.patch("aws_utils.get_boto3_clients", return_value=(fake_s3, fake_sts, fake_iam)):
        with pytest.raises(Exception, match="Access Denied"):
            aws_utils.apply_bucket_policy("bucket", "{}")
