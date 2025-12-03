"""Shared RDS test utilities for explore_aurora_data and explore_user_data tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestConstantsShared:
    """Shared tests for module constants (PSYCOPG2_AVAILABLE and MAX_SAMPLE_COLUMNS)."""

    def test_psycopg2_available_flag(self, rds_module):
        """Test that PSYCOPG2_AVAILABLE flag is defined."""
        assert hasattr(rds_module, "PSYCOPG2_AVAILABLE")
        assert isinstance(rds_module.PSYCOPG2_AVAILABLE, bool)

    def test_max_sample_columns_constant(self, rds_module):
        """Test that MAX_SAMPLE_COLUMNS constant is defined."""
        assert rds_module.MAX_SAMPLE_COLUMNS == 5


class TestRequireEnvVarShared:
    """Shared tests for _require_env_var function."""

    def test_require_env_var_present(self, rds_module):
        """Test getting a required environment variable that exists."""
        require_env_var = getattr(rds_module, "_require_env_var")
        with patch.dict("os.environ", {"TEST_VAR": "test_value"}):
            result = require_env_var("TEST_VAR")
            assert result == "test_value"

    def test_require_env_var_missing(self, rds_module):
        """Test getting a required environment variable that doesn't exist."""
        require_env_var = getattr(rds_module, "_require_env_var")
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="MISSING_VAR is required"):
                require_env_var("MISSING_VAR")

    def test_require_env_var_empty_string(self, rds_module):
        """Test getting a required environment variable that is empty."""
        require_env_var = getattr(rds_module, "_require_env_var")
        with patch.dict("os.environ", {"EMPTY_VAR": ""}):
            with pytest.raises(RuntimeError, match="EMPTY_VAR is required"):
                require_env_var("EMPTY_VAR")

    def test_require_env_var_whitespace_only(self, rds_module):
        """Test getting a required environment variable that contains only whitespace."""
        require_env_var = getattr(rds_module, "_require_env_var")
        with patch.dict("os.environ", {"WHITESPACE_VAR": "   "}):
            with pytest.raises(RuntimeError, match="WHITESPACE_VAR is required"):
                require_env_var("WHITESPACE_VAR")

    def test_require_env_var_strips_whitespace(self, rds_module):
        """Test that _require_env_var strips whitespace."""
        require_env_var = getattr(rds_module, "_require_env_var")
        with patch.dict("os.environ", {"TRIMMED_VAR": "  value  "}):
            result = require_env_var("TRIMMED_VAR")
            assert result == "value"


class TestParseRequiredPortShared:
    """Shared tests for _parse_required_port function."""

    def test_parse_required_port_valid(self, rds_module):
        """Test parsing a valid port number."""
        parse_required_port = getattr(rds_module, "_parse_required_port")
        with patch.dict("os.environ", {"TEST_PORT": "5432"}):
            result = parse_required_port("TEST_PORT")
            assert result == 5432

    def test_parse_required_port_invalid(self, rds_module):
        """Test parsing an invalid port number."""
        parse_required_port = getattr(rds_module, "_parse_required_port")
        with patch.dict("os.environ", {"TEST_PORT": "not_a_number"}):
            with pytest.raises(RuntimeError, match="must be a valid integer"):
                parse_required_port("TEST_PORT")

    def test_parse_required_port_missing(self, rds_module):
        """Test parsing a missing port environment variable."""
        parse_required_port = getattr(rds_module, "_parse_required_port")
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="MISSING_PORT is required"):
                parse_required_port("MISSING_PORT")
