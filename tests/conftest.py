"""
Shared pytest fixtures for test files

Provides common test fixtures to eliminate duplication across test files.
"""

import json
from pathlib import Path
from unittest import mock

import pytest

# ============================================================================
# AWS Identity Fixtures
# ============================================================================


@pytest.fixture
def mock_aws_identity():
    """Fixture that provides a mock AWS identity return value"""
    return {"user_arn": "arn:aws:iam::123:user/test"}


@pytest.fixture
def mock_aws_info_identity():
    """Fixture that provides a complete AWS identity for aws_info tests"""
    return {
        "account_id": "123456789012",
        "username": "test-user",
        "user_arn": "arn:aws:iam::123456789012:user/test-user",
    }


@pytest.fixture
def sample_policy():
    """Fixture that provides a sample S3 bucket policy structure"""
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
    """Fixture that sets up a policies directory in tmp_path and changes to tmp_path.

    Returns the policies directory Path object.
    """
    monkeypatch.chdir(tmp_path)
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    return policies_dir


@pytest.fixture
def setup_test_env(tmp_path, monkeypatch):
    """Fixture that changes to tmp_path but doesn't create policies directory.

    Useful for tests that need to verify directory creation.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def mock_block_s3_dependencies(mock_aws_identity, sample_policy):
    """Fixture that provides common mocks for block_s3.py tests.

    Returns a context manager that can be used with 'with' statement.
    """

    class MockContext:
        def __enter__(self):
            self.identity_patch = mock.patch(
                "block_s3.get_aws_identity", return_value=mock_aws_identity
            )
            self.policy_patch = mock.patch(
                "block_s3.generate_restrictive_bucket_policy", return_value=sample_policy
            )
            self.save_patch = mock.patch("block_s3.save_policy_to_file")

            self.identity_mock = self.identity_patch.__enter__()
            self.policy_mock = self.policy_patch.__enter__()
            self.save_mock = self.save_patch.__enter__()

            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.save_patch.__exit__(exc_type, exc_val, exc_tb)
            self.policy_patch.__exit__(exc_type, exc_val, exc_tb)
            self.identity_patch.__exit__(exc_type, exc_val, exc_tb)

    return MockContext()


@pytest.fixture
def create_policy_file(policies_dir):
    """Fixture that provides a helper function to create policy files.

    Returns a callable that creates a policy file with the given bucket name and policy content.
    """

    def _create_policy_file(bucket_name, policy_content=None):
        if policy_content is None:
            policy_content = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow"}]}
        policy_file = policies_dir / f"{bucket_name}_policy.json"
        policy_file.write_text(json.dumps(policy_content))
        return policy_file

    return _create_policy_file


@pytest.fixture
def mock_apply_block_dependencies():
    """Fixture that provides common mocks for apply_block.py tests.

    Returns a context manager with mocked apply_bucket_policy.
    """

    class MockContext:
        def __enter__(self):
            self.apply_patch = mock.patch("apply_block.apply_bucket_policy")
            self.apply_mock = self.apply_patch.__enter__()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.apply_patch.__exit__(exc_type, exc_val, exc_tb)

    return MockContext()


# ============================================================================
# AWS Info Test Fixtures
# ============================================================================


@pytest.fixture
def mock_aws_info_context(mock_aws_info_identity):
    """Fixture that provides a context manager for aws_info tests.

    Returns a context manager that mocks get_aws_identity, list_s3_buckets,
    and print. Allows custom bucket lists to be passed.
    """

    class MockContext:
        def __init__(self, identity):
            self.identity = identity
            self.buckets = []

        def with_buckets(self, buckets):
            """Set the buckets list for this context"""
            self.buckets = buckets
            return self

        def __enter__(self):
            self.identity_patch = mock.patch(
                "aws_info.get_aws_identity", return_value=self.identity
            )
            self.buckets_patch = mock.patch("aws_info.list_s3_buckets", return_value=self.buckets)
            self.print_patch = mock.patch("builtins.print")

            self.identity_mock = self.identity_patch.__enter__()
            self.buckets_mock = self.buckets_patch.__enter__()
            self.print_mock = self.print_patch.__enter__()

            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.print_patch.__exit__(exc_type, exc_val, exc_tb)
            self.buckets_patch.__exit__(exc_type, exc_val, exc_tb)
            self.identity_patch.__exit__(exc_type, exc_val, exc_tb)

    return MockContext(mock_aws_info_identity)


# ============================================================================
# Block S3 Test Fixtures
# ============================================================================


@pytest.fixture
def empty_policy():
    """Fixture that provides an empty S3 bucket policy"""
    return {"Version": "2012-10-17", "Statement": []}


@pytest.fixture
def mock_block_s3_context(mock_aws_identity):
    """Fixture that provides a context manager for block_s3 tests.

    Returns a context manager that can be configured with custom policies
    and supports multiple nested patch contexts.
    """

    class MockContext:
        def __init__(self, identity):
            self.identity = identity
            self.policy = {"Version": "2012-10-17", "Statement": []}
            self.buckets = []

        def with_policy(self, policy):
            """Set the policy for this context"""
            self.policy = policy
            return self

        def with_buckets(self, buckets):
            """Set the buckets list for this context"""
            self.buckets = buckets
            return self

        def __enter__(self):
            self.identity_patch = mock.patch(
                "block_s3.get_aws_identity", return_value=self.identity
            )
            self.policy_patch = mock.patch(
                "block_s3.generate_restrictive_bucket_policy", return_value=self.policy
            )

            self.identity_mock = self.identity_patch.__enter__()
            self.policy_mock = self.policy_patch.__enter__()

            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.policy_patch.__exit__(exc_type, exc_val, exc_tb)
            self.identity_patch.__exit__(exc_type, exc_val, exc_tb)

    return MockContext(mock_aws_identity)


# ============================================================================
# Migration Verify Test Fixtures
# ============================================================================


@pytest.fixture
def mock_db_connection():
    """Fixture that provides a mock database connection context manager.

    Returns a function that takes rows and returns a configured mock
    connection context manager ready for use with MigrationStateV2.
    """

    def _create_mock_connection(rows):
        """Create a mock connection that returns the given rows"""
        mock_conn = mock.Mock()
        mock_conn.execute.return_value = rows

        mock_cm = mock.MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = False

        return mock_cm

    return _create_mock_connection


# ============================================================================
# Migration Scanner Test Fixtures
# ============================================================================


@pytest.fixture
def mock_migration_scanner_deps():
    """Fixture that provides mock dependencies for migration scanner tests.

    Returns a dict with mock_s3 and mock_state instances.
    """
    from migration_state_v2 import MigrationStateV2

    mock_s3 = mock.Mock()
    mock_state = mock.Mock(spec=MigrationStateV2)

    return {"s3": mock_s3, "state": mock_state}


@pytest.fixture
def s3_paginator_response():
    """Fixture that provides a factory for S3 paginator responses.

    Returns a function that creates S3 paginator response with given contents.
    """

    def _create_response(contents):
        """Create a paginator response with the given contents"""
        return [{"Contents": contents}]

    return _create_response


# ============================================================================
# Migration Orchestrator Test Fixtures
# ============================================================================


@pytest.fixture
def mock_orchestrator_deps(tmp_path):
    """Fixture that provides mock dependencies for migration orchestrator tests.

    Returns a dict with all necessary mocks and paths configured.
    """
    base_path = tmp_path / "migration"
    base_path.mkdir()

    return {
        "s3": mock.Mock(),
        "state": mock.Mock(),
        "base_path": base_path,
        "drive_checker": mock.Mock(),
    }


@pytest.fixture
def mock_bucket_info():
    """Fixture that provides a factory for bucket info dicts.

    Returns a function that creates bucket info with custom values.
    """

    def _create_bucket_info(
        sync_complete=False,
        verify_complete=False,
        delete_complete=False,
        file_count=100,
        total_size=1000,
    ):
        """Create a bucket info dict with the given values"""
        return {
            "sync_complete": sync_complete,
            "verify_complete": verify_complete,
            "delete_complete": delete_complete,
            "file_count": file_count,
            "total_size": total_size,
        }

    return _create_bucket_info


# ============================================================================
# Phase and State Management Fixtures
# ============================================================================


@pytest.fixture
def all_phases():
    """Fixture that provides a list of all migration phases in order"""
    from migration_state_v2 import Phase

    return [
        Phase.SCANNING,
        Phase.GLACIER_RESTORE,
        Phase.GLACIER_WAIT,
        Phase.SYNCING,
        Phase.VERIFYING,
        Phase.DELETING,
        Phase.COMPLETE,
    ]


@pytest.fixture
def common_phases():
    """Fixture that provides a list of common migration phases (without VERIFYING and DELETING)"""
    from migration_state_v2 import Phase

    return [
        Phase.SCANNING,
        Phase.GLACIER_RESTORE,
        Phase.GLACIER_WAIT,
        Phase.SYNCING,
        Phase.COMPLETE,
    ]


# ============================================================================
# Migration Verify Test Fixtures - Specific Helpers
# ============================================================================


@pytest.fixture
def setup_verify_test(tmp_path, mock_db_connection):
    """Fixture that sets up a complete verification test environment.

    Returns a function that creates test files, mock state, and db connection.
    """

    def _setup(file_data_map):
        """
        Setup verification test with given file data.

        Args:
            file_data_map: Dict mapping filenames to their content bytes

        Returns:
            Dict with bucket_path, mock_state, and file metadata
        """
        import hashlib

        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()

        # Create files and generate metadata
        file_metadata = []
        for filename, content in file_data_map.items():
            (bucket_path / filename).write_bytes(content)
            md5 = hashlib.md5(content, usedforsecurity=False).hexdigest()
            file_metadata.append({"key": filename, "size": len(content), "etag": md5})

        # Setup mock state
        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {
            "file_count": len(file_data_map),
            "total_size": sum(len(c) for c in file_data_map.values()),
        }

        # Setup db connection
        mock_cm = mock_db_connection(file_metadata)
        mock_state.db_conn.get_connection.return_value = mock_cm

        return {
            "bucket_path": bucket_path,
            "mock_state": mock_state,
            "file_metadata": file_metadata,
            "tmp_path": tmp_path,
        }

    return _setup


# ============================================================================
# Verification Stats Fixtures
# ============================================================================


@pytest.fixture
def empty_verify_stats():
    """Fixture that provides an empty verification stats dict"""
    return {
        "verified_count": 0,
        "size_verified": 0,
        "checksum_verified": 0,
        "total_bytes_verified": 0,
        "verification_errors": [],
    }


# ============================================================================
# Migration Sync Test Fixtures
# ============================================================================


@pytest.fixture
def create_mock_process():
    """Fixture that provides a factory for creating mock subprocess.Popen processes"""

    def _create_process(stdout_lines, returncodes):
        """
        Create a mock process with specified output and return codes.

        Args:
            stdout_lines: List of strings to return from stdout.readline()
            returncodes: List of return codes (None while running, 0 when complete)

        Returns:
            Mock process object configured with the given behavior
        """
        mock_process = mock.Mock()
        mock_process.stdout.readline.side_effect = [
            line.encode() if line else b"" for line in stdout_lines
        ]
        mock_process.poll.side_effect = returncodes
        return mock_process

    return _create_process
