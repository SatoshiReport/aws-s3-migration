"""Tests for cleanup_temp_artifacts/config.py module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from cleanup_temp_artifacts.config import (
    DEFAULT_BASE_PATH,
    DEFAULT_DB_PATH,
    REPO_ROOT,
    determine_default_base_path,
    determine_default_db_path,
    get_repo_root,
)


def test_get_repo_root():
    """Test get_repo_root returns correct path."""
    root = get_repo_root()
    assert isinstance(root, Path)
    assert root.is_dir()
    # Should point to the repo root (parent of cleanup_temp_artifacts)
    assert (root / "cleanup_temp_artifacts").is_dir()


def test_repo_root_constant():
    """Test REPO_ROOT constant is set."""
    assert isinstance(REPO_ROOT, Path)
    assert REPO_ROOT.is_dir()


def test_determine_default_base_path_from_env(tmp_path: Path, monkeypatch):
    """Test determine_default_base_path uses environment variable."""
    test_dir = tmp_path / "cleanup"
    test_dir.mkdir()

    monkeypatch.setenv("CLEANUP_TEMP_ROOT", str(test_dir))

    result = determine_default_base_path()
    # Should find our test dir since it exists
    assert result == test_dir


def test_determine_default_base_path_fallback(monkeypatch):
    """Test determine_default_base_path falls back when paths don't exist."""
    # Clear environment variables
    monkeypatch.delenv("CLEANUP_TEMP_ROOT", raising=False)
    monkeypatch.delenv("CLEANUP_ROOT", raising=False)

    # Mock config module to return non-existent path
    with patch("cleanup_temp_artifacts.config.config_module", None):
        result = determine_default_base_path()
        # Should return something (either cwd or first candidate)
        assert result is not None
        assert isinstance(result, Path)


def test_determine_default_db_path_with_config():
    """Test determine_default_db_path uses config.STATE_DB_PATH."""
    result = determine_default_db_path()
    assert isinstance(result, Path)
    assert result.is_absolute()
    assert result.name.endswith(".db")


def test_determine_default_db_path_without_config():
    """Test determine_default_db_path fallback without config module."""
    with patch("cleanup_temp_artifacts.config.config_module", None):
        result = determine_default_db_path()
        assert isinstance(result, Path)
        assert result.is_absolute()
        assert result.name == "s3_migration_state.db"


def test_default_constants_are_set():
    """Test that DEFAULT_BASE_PATH and DEFAULT_DB_PATH are set."""
    # DEFAULT_BASE_PATH might be None if no valid paths exist
    assert DEFAULT_BASE_PATH is None or isinstance(DEFAULT_BASE_PATH, Path)
    assert isinstance(DEFAULT_DB_PATH, Path)
    assert DEFAULT_DB_PATH.is_absolute()


def test_determine_default_base_path_with_none_in_config(monkeypatch):
    """Test determine_default_base_path when config has None value."""
    # Clear environment variables
    monkeypatch.delenv("CLEANUP_TEMP_ROOT", raising=False)
    monkeypatch.delenv("CLEANUP_ROOT", raising=False)

    # Mock config module to return None for LOCAL_BASE_PATH
    mock_config = type("MockConfig", (), {"LOCAL_BASE_PATH": None})()

    with patch("cleanup_temp_artifacts.config.config_module", mock_config):
        result = determine_default_base_path()
        # Should skip None and return an existing path
        assert result is not None
        assert isinstance(result, Path)


def test_determine_default_base_path_no_existing_paths(monkeypatch, tmp_path):
    """Test determine_default_base_path when no candidates exist."""
    # Clear environment variables
    monkeypatch.delenv("CLEANUP_TEMP_ROOT", raising=False)
    monkeypatch.delenv("CLEANUP_ROOT", raising=False)

    # Create a non-existent path
    nonexistent = tmp_path / "nonexistent" / "path"

    # Mock config module to return non-existent path
    mock_config = type("MockConfig", (), {"LOCAL_BASE_PATH": str(nonexistent)})()

    # Change cwd to a temp location
    monkeypatch.chdir(tmp_path)

    with patch("cleanup_temp_artifacts.config.config_module", mock_config):
        with patch("cleanup_temp_artifacts.config.Path.cwd", return_value=nonexistent):
            # Mock all Path.exists() to return False
            original_exists = Path.exists

            def mock_exists(self):
                if str(self).startswith(str(tmp_path)):
                    return False
                return original_exists(self)

            with patch.object(Path, "exists", mock_exists):
                result = determine_default_base_path()
                # Should return first candidate even if it doesn't exist
                assert result == nonexistent
