"""Tests for aws_utils policy generation functions."""

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
