import json
from unittest import mock

import pytest

import aws_utils

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
