"""Tests for cleanup_temp_artifacts/config.py module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from cleanup_temp_artifacts import config  # pylint: disable=no-name-in-module
from cleanup_temp_artifacts.config import ConfigurationError  # pylint: disable=no-name-in-module

DEFAULT_BASE_PATH = config.DEFAULT_BASE_PATH
DEFAULT_DB_PATH = config.DEFAULT_DB_PATH
REPO_ROOT = config.REPO_ROOT
determine_default_base_path = config.determine_default_base_path
determine_default_db_path = config.determine_default_db_path
get_repo_root = config.get_repo_root


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


def test_determine_default_base_path_raises_without_config(monkeypatch):
    """Test determine_default_base_path raises ConfigurationError when no valid config exists."""
    # Clear environment variables
    monkeypatch.delenv("CLEANUP_TEMP_ROOT", raising=False)
    monkeypatch.delenv("CLEANUP_ROOT", raising=False)

    # Mock config module to return None (no config)
    with patch("cleanup_temp_artifacts.config.config_module", None):
        with pytest.raises(ConfigurationError) as exc_info:
            determine_default_base_path()
        assert "No valid base path found" in str(exc_info.value)


def test_determine_default_db_path_with_config():
    """Test determine_default_db_path uses config.STATE_DB_PATH."""
    result = determine_default_db_path()
    assert isinstance(result, Path)
    assert result.is_absolute()
    assert result.name.endswith(".db")


def test_determine_default_db_path_raises_without_config():
    """Test determine_default_db_path raises ConfigurationError without config module."""
    with patch("cleanup_temp_artifacts.config.config_module", None):
        with pytest.raises(ConfigurationError) as exc_info:
            determine_default_db_path()
        assert "STATE_DB_PATH must be set" in str(exc_info.value)


def test_default_constants_are_lazy():
    """Test that DEFAULT_BASE_PATH and DEFAULT_DB_PATH are lazy path objects."""
    from cleanup_temp_artifacts.config import _LazyPath  # pylint: disable=no-name-in-module

    # Both are now _LazyPath objects for deferred evaluation
    assert isinstance(DEFAULT_BASE_PATH, _LazyPath)
    assert isinstance(DEFAULT_DB_PATH, _LazyPath)
    # They resolve to Path when accessed - test this indirectly
    # (actual resolution is tested elsewhere)


def test_determine_default_base_path_raises_with_none_in_config(monkeypatch):
    """Test determine_default_base_path raises when config has None value."""
    # Clear environment variables
    monkeypatch.delenv("CLEANUP_TEMP_ROOT", raising=False)
    monkeypatch.delenv("CLEANUP_ROOT", raising=False)

    # Mock config module to return None for LOCAL_BASE_PATH
    mock_config = type("MockConfig", (), {"LOCAL_BASE_PATH": None})()

    with patch("cleanup_temp_artifacts.config.config_module", mock_config):
        with pytest.raises(ConfigurationError) as exc_info:
            determine_default_base_path()
        assert "No valid base path found" in str(exc_info.value)


def test_determine_default_base_path_raises_when_path_nonexistent(monkeypatch, tmp_path):
    """Test determine_default_base_path raises when configured path doesn't exist."""
    # Clear environment variables
    monkeypatch.delenv("CLEANUP_TEMP_ROOT", raising=False)
    monkeypatch.delenv("CLEANUP_ROOT", raising=False)

    # Create a non-existent path
    nonexistent = tmp_path / "nonexistent" / "path"

    # Mock config module to return non-existent path
    mock_config = type("MockConfig", (), {"LOCAL_BASE_PATH": str(nonexistent)})()

    with patch("cleanup_temp_artifacts.config.config_module", mock_config):
        with pytest.raises(ConfigurationError) as exc_info:
            determine_default_base_path()
        assert "No valid base path found" in str(exc_info.value)
