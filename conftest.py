"""Pytest configuration and shared fixtures for the AWS S3 toolkit."""

# pylint: disable=wrong-import-position

import sys
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from migrate_v2 import MigrationComponents, S3MigrationV2
from migration_state_v2 import DatabaseConnection


@pytest.fixture(autouse=True)
def mock_aws_env_file(tmp_path, monkeypatch):
    """Auto-use fixture that provides a mock .env file for tests requiring AWS credentials.

    This creates a temporary .env file with mock credentials and sets AWS_ENV_FILE
    to point to it. Tests that mock load_credentials_from_env won't need this,
    but tests that don't mock it will get valid mock credentials.
    """
    env_file = tmp_path / ".env"
    env_file.write_text("AWS_ACCESS_KEY_ID=test_key\nAWS_SECRET_ACCESS_KEY=test_secret\n")
    monkeypatch.setenv("AWS_ENV_FILE", str(env_file))
    yield str(env_file)


@pytest.fixture(name="temp_db")
def fixture_temp_db(tmp_path):
    """Provide a temporary SQLite path for stateful tests."""
    db_path = tmp_path / "migration_state.db"
    yield str(db_path)
    db_path.unlink(missing_ok=True)


@pytest.fixture(name="mock_print")
def fixture_mock_print(monkeypatch):
    """Patch builtins.print and return the mock for assertions."""
    patched = mock.Mock()
    monkeypatch.setattr("builtins.print", patched)
    return patched


@pytest.fixture
def db_conn(temp_db):
    """Return a DatabaseConnection bound to the temporary path."""
    return DatabaseConnection(temp_db)


@pytest.fixture(name="mock_dependencies")
def fixture_mock_dependencies():
    """Common dependency graph used across migrate_v2 tests."""
    dependencies = {
        "state": mock.Mock(),
        "drive_checker": mock.Mock(),
        "scanner": mock.Mock(),
        "glacier_restorer": mock.Mock(),
        "glacier_waiter": mock.Mock(),
        "migration_orchestrator": mock.Mock(),
        "bucket_migrator": mock.Mock(),
        "status_reporter": mock.Mock(),
    }
    bucket_syncer = mock.Mock()
    bucket_syncer.interrupted = False
    dependencies["bucket_migrator"].syncer = bucket_syncer
    return dependencies


@pytest.fixture(name="migrator")
def fixture_migrator(mock_dependencies):
    """Instantiate S3MigrationV2 with shared mock dependencies."""
    components = MigrationComponents(
        drive_checker=mock_dependencies["drive_checker"],
        scanner=mock_dependencies["scanner"],
        glacier_restorer=mock_dependencies["glacier_restorer"],
        glacier_waiter=mock_dependencies["glacier_waiter"],
        migration_orchestrator=mock_dependencies["migration_orchestrator"],
        bucket_migrator=mock_dependencies["bucket_migrator"],
        status_reporter=mock_dependencies["status_reporter"],
    )
    for key in (
        "scanner",
        "glacier_restorer",
        "glacier_waiter",
        "bucket_migrator",
        "migration_orchestrator",
    ):
        mock_dependencies[key].interrupted = False
    return S3MigrationV2(mock_dependencies["state"], components)
