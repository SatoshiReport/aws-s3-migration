"""
Unit tests for config.py path-related configurations.

Tests verify:
- LOCAL_BASE_PATH configuration
- STATE_DB_PATH configuration
"""

import config


class TestLocalBasePath:
    """Tests for LOCAL_BASE_PATH configuration."""

    def test_local_base_path_exists(self):
        """Verify LOCAL_BASE_PATH constant exists."""
        assert hasattr(config, "LOCAL_BASE_PATH")

    def test_local_base_path_is_string(self):
        """Verify LOCAL_BASE_PATH is a string."""
        assert isinstance(config.LOCAL_BASE_PATH, str)

    def test_local_base_path_not_empty(self):
        """Verify LOCAL_BASE_PATH is not empty."""
        assert len(config.LOCAL_BASE_PATH) > 0

    def test_local_base_path_is_absolute(self):
        """Verify LOCAL_BASE_PATH looks like an absolute path."""
        # Should start with / on Unix-like systems or drive letter on Windows
        assert config.LOCAL_BASE_PATH.startswith("/") or config.LOCAL_BASE_PATH[1] == ":"


class TestStateDbPath:
    """Tests for STATE_DB_PATH configuration."""

    def test_state_db_path_exists(self):
        """Verify STATE_DB_PATH constant exists."""
        assert hasattr(config, "STATE_DB_PATH")

    def test_state_db_path_is_string(self):
        """Verify STATE_DB_PATH is a string."""
        assert isinstance(config.STATE_DB_PATH, str)

    def test_state_db_path_not_empty(self):
        """Verify STATE_DB_PATH is not empty."""
        assert len(config.STATE_DB_PATH) > 0

    def test_state_db_path_has_db_extension(self):
        """Verify STATE_DB_PATH ends with .db extension."""
        assert config.STATE_DB_PATH.endswith(".db")
