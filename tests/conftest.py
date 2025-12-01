"""Shared pytest fixtures for test files."""

from __future__ import annotations

import copy

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.common import aws_client_factory, credential_utils

pytest_plugins = ["tests.conftest_helpers"]


class _DefaultResponse(dict):
    """Dict returning empty list for missing keys."""

    def __missing__(self, key):
        return []


_DEFAULT_RESPONSES: dict[str, dict] = {
    "describe_regions": _DefaultResponse(Regions=[{"RegionName": "us-east-1"}]),
    "list_regions": _DefaultResponse(Regions=[{"RegionName": "us-east-1"}]),
    "describe_instances": _DefaultResponse(Reservations=[]),
    "describe_volumes": _DefaultResponse(Volumes=[]),
    "describe_snapshots": _DefaultResponse(Snapshots=[]),
    "list_backup_jobs": _DefaultResponse(BackupJobs=[]),
    "list_backup_plans": _DefaultResponse(BackupPlans=[]),
    "describe_addresses": _DefaultResponse(Addresses=[]),
    "list_buckets": _DefaultResponse(Buckets=[]),
    "list_objects_v2": _DefaultResponse(Contents=[]),
    "get_bucket_tagging": _DefaultResponse(TagSet=[]),
    "list_targets_by_rule": _DefaultResponse(Targets=[]),
    "list_rules": _DefaultResponse(Rules=[]),
    "describe_trails": _DefaultResponse(TrailList=[]),
    "describe_db_clusters": _DefaultResponse(DBClusters=[]),
    "describe_db_instances": _DefaultResponse(DBInstances=[]),
}


class _StubBotoClient:
    """Minimal stub for boto3 clients used in tests."""

    def __init__(self, service_name: str, **kwargs):
        self.service_name = service_name
        self.region_name = kwargs.get("region_name")
        self.exceptions = ClientError

    def __getattr__(self, name: str):
        def _method(*args, **kwargs):
            del args, kwargs
            response = _DEFAULT_RESPONSES.get(name)
            if response is None:
                return _DefaultResponse()
            return copy.deepcopy(response)

        return _method


@pytest.fixture(autouse=True)
def stub_boto3_client(monkeypatch):
    """Replace boto3.client with a stub so tests don't call real AWS."""

    def fake_client(service_name, **kwargs):
        return _StubBotoClient(service_name, **kwargs)

    monkeypatch.setattr("boto3.client", fake_client)


@pytest.fixture(autouse=True)
def stub_credentials(monkeypatch):
    """Provide fake AWS credentials so create_client doesn't fail."""

    original_factory_loader = aws_client_factory.load_credentials_from_env

    def _load_credentials(env_path=None):
        credentials = original_factory_loader(env_path)
        print("AWS credentials loaded")
        return credentials

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "stub-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "stub-secret")
    monkeypatch.setattr(
        aws_client_factory,
        "load_credentials_from_env",
        _load_credentials,
    )
    monkeypatch.setattr(
        credential_utils,
        "load_credentials_from_env",
        _load_credentials,
    )


@pytest.fixture
def mock_aws_identity():
    """Mock AWS identity return value"""
    return {"user_arn": "arn:aws:iam::123:user/test"}


@pytest.fixture
def mock_aws_info_identity():
    """Complete AWS identity for aws_info tests"""
    return {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }


@pytest.fixture
def sample_policy():
    """Sample S3 bucket policy structure"""
    return {
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


@pytest.fixture
def policies_dir(tmp_path, monkeypatch):
    """Sets up policies directory in tmp_path and changes to it."""
    monkeypatch.chdir(tmp_path)
    policies_dir = tmp_path / "policies"  # pylint: disable=redefined-outer-name
    policies_dir.mkdir()
    return policies_dir


@pytest.fixture
def setup_test_env(tmp_path, monkeypatch):
    """Changes to tmp_path (tests can verify directory creation)."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def mock_boto3_ec2_client(monkeypatch):
    """Create a mock EC2 client for testing (replaces boto3.client call)."""
    from unittest.mock import MagicMock, patch

    with patch("boto3.client") as mock_boto3:
        mock_ec2 = MagicMock()
        mock_boto3.return_value = mock_ec2
        yield mock_ec2, mock_boto3


@pytest.fixture
def assert_raises_error():
    """Helper fixture for testing exception raising patterns."""

    def _assert_raises(exception_class, exception_message_substring, callable_fn):
        """Assert that calling callable_fn raises exception_class with message."""
        try:
            callable_fn()
            raise AssertionError(f"Should have raised {exception_class.__name__}")
        except exception_class as e:
            if exception_message_substring not in str(e):
                raise AssertionError(
                    f"Expected '{exception_message_substring}' in {str(e)}"
                )

    return _assert_raises


@pytest.fixture(params=["aurora", "user"])
def rds_module(request):
    """Parametrized fixture for testing both aurora and user RDS modules.

    Parametrizes across explore_aurora_data and explore_user_data modules.
    """
    if request.param == "aurora":
        from cost_toolkit.scripts.rds import explore_aurora_data
        return explore_aurora_data
    else:
        from cost_toolkit.scripts.rds import explore_user_data
        return explore_user_data
