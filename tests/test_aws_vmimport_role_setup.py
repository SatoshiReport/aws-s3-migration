"""Tests for cost_toolkit/scripts/setup/aws_vmimport_role_setup.py module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.common.credential_utils import setup_aws_credentials
from cost_toolkit.scripts.setup.aws_vmimport_role_setup import (
    create_new_role_with_policy,
    create_vmimport_role,
    get_trust_policy,
    get_vmimport_policy,
    main,
    print_alternative_setup_instructions,
)


def test_load_aws_credentials_success(tmp_path, monkeypatch):
    """Test successful loading of AWS credentials from .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("AWS_ACCESS_KEY_ID=TESTKEY123\nAWS_SECRET_ACCESS_KEY=TESTSECRET456\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    with patch("cost_toolkit.scripts.setup.aws_vmimport_role_setup.os.path.expanduser") as mock_expand:
        mock_expand.return_value = str(env_file)
        key_id, secret_key = setup_aws_credentials()

    assert key_id == "TESTKEY123"
    assert secret_key == "TESTSECRET456"


def test_load_aws_credentials_missing_key_id(tmp_path, monkeypatch):
    """Test error when AWS_ACCESS_KEY_ID is missing."""
    env_file = tmp_path / ".env"
    env_file.write_text("AWS_SECRET_ACCESS_KEY=TESTSECRET456\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    with patch("cost_toolkit.scripts.setup.aws_vmimport_role_setup.os.path.expanduser") as mock_expand:
        mock_expand.return_value = str(env_file)
        with pytest.raises(ValueError, match="AWS credentials not found"):
            setup_aws_credentials()


def test_load_aws_credentials_missing_secret_key(tmp_path, monkeypatch):
    """Test error when AWS_SECRET_ACCESS_KEY is missing."""
    env_file = tmp_path / ".env"
    env_file.write_text("AWS_ACCESS_KEY_ID=TESTKEY123\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    with patch("cost_toolkit.scripts.setup.aws_vmimport_role_setup.os.path.expanduser") as mock_expand:
        mock_expand.return_value = str(env_file)
        with pytest.raises(ValueError, match="AWS credentials not found"):
            setup_aws_credentials()


def test_get_trust_policy():
    """Test get_trust_policy returns correct policy structure."""
    policy = get_trust_policy()

    assert policy["Version"] == "2012-10-17"
    assert len(policy["Statement"]) == 1
    assert policy["Statement"][0]["Effect"] == "Allow"
    assert policy["Statement"][0]["Principal"]["Service"] == "vmie.amazonaws.com"
    assert policy["Statement"][0]["Action"] == "sts:AssumeRole"
    assert policy["Statement"][0]["Condition"]["StringEquals"]["sts:Externalid"] == "vmimport"


def test_get_vmimport_policy():
    """Test get_vmimport_policy returns correct policy structure."""
    policy = get_vmimport_policy()

    assert policy["Version"] == "2012-10-17"
    assert len(policy["Statement"]) == 2


def test_get_vmimport_policy_s3_permissions():
    """Test get_vmimport_policy returns correct S3 permissions."""
    policy = get_vmimport_policy()
    s3_statement = policy["Statement"][0]

    assert s3_statement["Effect"] == "Allow"
    assert "s3:GetBucketLocation" in s3_statement["Action"]
    assert "s3:GetObject" in s3_statement["Action"]
    assert "s3:ListBucket" in s3_statement["Action"]
    assert "s3:PutObject" in s3_statement["Action"]
    assert "s3:GetBucketAcl" in s3_statement["Action"]


def test_get_vmimport_policy_ec2_permissions():
    """Test get_vmimport_policy returns correct EC2 permissions."""
    policy = get_vmimport_policy()
    ec2_statement = policy["Statement"][1]

    assert ec2_statement["Effect"] == "Allow"
    assert "ec2:ModifySnapshotAttribute" in ec2_statement["Action"]
    assert "ec2:CopySnapshot" in ec2_statement["Action"]
    assert "ec2:RegisterImage" in ec2_statement["Action"]
    assert "ec2:Describe*" in ec2_statement["Action"]


def test_create_new_role_with_policy_success(capsys):
    """Test successful creation of vmimport role and policy."""
    mock_iam = MagicMock()
    mock_iam.create_role.return_value = {"Role": {"Arn": "arn:aws:iam::123456789012:role/vmimport"}}
    mock_iam.create_policy.return_value = {"Policy": {"Arn": "arn:aws:iam::123456789012:policy/vmimport-policy"}}

    trust_policy = get_trust_policy()
    vmimport_policy = get_vmimport_policy()

    create_new_role_with_policy(mock_iam, trust_policy, vmimport_policy)

    # Verify role creation
    mock_iam.create_role.assert_called_once_with(
        RoleName="vmimport",
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description="Service role for VM Import/Export operations",
    )

    # Verify policy creation
    mock_iam.create_policy.assert_called_once_with(
        PolicyName="vmimport-policy",
        PolicyDocument=json.dumps(vmimport_policy),
        Description="Policy for VM Import/Export operations",
    )

    # Verify policy attachment
    mock_iam.attach_role_policy.assert_called_once_with(RoleName="vmimport", PolicyArn="arn:aws:iam::123456789012:policy/vmimport-policy")

    captured = capsys.readouterr()
    assert "Created vmimport role" in captured.out
    assert "Created vmimport policy" in captured.out
    assert "Successfully attached policy" in captured.out


def test_print_alternative_setup_instructions(capsys):
    """Test print_alternative_setup_instructions outputs correct format."""
    print_alternative_setup_instructions()

    captured = capsys.readouterr()
    assert "Alternative setup using AWS CLI:" in captured.out
    assert "trust-policy.json" in captured.out
    assert "aws iam create-role" in captured.out
    assert "role-policy.json" in captured.out
    assert "aws iam put-role-policy" in captured.out


def test_create_vmimport_role_already_exists(capsys):
    """Test create_vmimport_role when role already exists."""
    mock_iam = MagicMock()
    mock_iam.get_role.return_value = {
        "Role": {
            "Arn": "arn:aws:iam::123456789012:role/vmimport",
            "CreateDate": "2024-01-01T00:00:00Z",
        }
    }

    with patch("cost_toolkit.scripts.setup.aws_vmimport_role_setup.setup_aws_credentials") as mock_load:
        mock_load.return_value = ("TESTKEY", "TESTSECRET")
        with patch("cost_toolkit.scripts.setup.aws_vmimport_role_setup.boto3.client") as mock_boto:
            mock_boto.return_value = mock_iam
            result = create_vmimport_role()

    assert result is True
    mock_iam.get_role.assert_called_once_with(RoleName="vmimport")
    captured = capsys.readouterr()
    assert "vmimport role already exists" in captured.out


def test_create_vmimport_role_creates_new_role():
    """Test create_vmimport_role creates new role when it doesn't exist."""
    mock_iam = MagicMock()
    mock_iam.exceptions.NoSuchEntityException = type("NoSuchEntityException", (Exception,), {})
    mock_iam.get_role.side_effect = mock_iam.exceptions.NoSuchEntityException()
    mock_iam.create_role.return_value = {"Role": {"Arn": "arn:aws:iam::123456789012:role/vmimport"}}
    mock_iam.create_policy.return_value = {"Policy": {"Arn": "arn:aws:iam::123456789012:policy/vmimport-policy"}}

    with patch("cost_toolkit.scripts.setup.aws_vmimport_role_setup.setup_aws_credentials") as mock_load:
        mock_load.return_value = ("TESTKEY", "TESTSECRET")
        with patch("cost_toolkit.scripts.setup.aws_vmimport_role_setup.boto3.client") as mock_boto:
            mock_boto.return_value = mock_iam
            result = create_vmimport_role()

    assert result is True
    mock_iam.create_role.assert_called_once()
    mock_iam.create_policy.assert_called_once()
    mock_iam.attach_role_policy.assert_called_once()


def test_create_vmimport_role_client_error(capsys):
    """Test create_vmimport_role handles ClientError."""
    mock_iam = MagicMock()

    # Make sure the exception is a proper subclass
    mock_iam.exceptions = MagicMock()
    mock_iam.exceptions.NoSuchEntityException = type("NoSuchEntityException", (Exception,), {})

    # First get_role call raises ClientError (not NoSuchEntity)
    mock_iam.get_role.side_effect = ClientError({"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "GetRole")

    with patch("cost_toolkit.scripts.setup.aws_vmimport_role_setup.setup_aws_credentials") as mock_load:
        mock_load.return_value = ("TESTKEY", "TESTSECRET")
        with patch("cost_toolkit.scripts.setup.aws_vmimport_role_setup.boto3.client") as mock_boto:
            mock_boto.return_value = mock_iam
            result = create_vmimport_role()

    assert result is False
    captured = capsys.readouterr()
    assert "Error setting up vmimport role" in captured.out
    assert "Alternative setup using AWS CLI:" in captured.out


def test_main_success():
    """Test main function succeeds."""
    with patch("cost_toolkit.scripts.setup.aws_vmimport_role_setup.create_vmimport_role") as mock_create:
        mock_create.return_value = True
        main()

    mock_create.assert_called_once()


def test_main_client_error_exit():
    """Test main function exits on ClientError."""
    with patch("cost_toolkit.scripts.setup.aws_vmimport_role_setup.create_vmimport_role") as mock_create:
        mock_create.side_effect = ClientError({"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "GetRole")
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1


def test_load_aws_credentials_prints_success_message(tmp_path, monkeypatch, capsys):
    """Test setup_aws_credentials prints success message."""
    env_file = tmp_path / ".env"
    env_file.write_text("AWS_ACCESS_KEY_ID=TESTKEY\nAWS_SECRET_ACCESS_KEY=TESTSECRET\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    with patch("cost_toolkit.scripts.setup.aws_vmimport_role_setup.os.path.expanduser") as mock_expand:
        mock_expand.return_value = str(env_file)
        setup_aws_credentials()

    captured = capsys.readouterr()
    assert "AWS credentials loaded" in captured.out
