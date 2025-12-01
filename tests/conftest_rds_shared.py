"""Shared RDS test utilities for explore_aurora_data and explore_user_data tests."""

from __future__ import annotations

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
        from unittest.mock import patch

        with patch.dict("os.environ", {"TEST_VAR": "test_value"}):
            result = rds_module._require_env_var("TEST_VAR")  # pylint: disable=protected-access
            assert result == "test_value"

    def test_require_env_var_missing(self, rds_module):
        """Test getting a required environment variable that doesn't exist."""
        from unittest.mock import patch

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="MISSING_VAR is required"):
                rds_module._require_env_var("MISSING_VAR")  # pylint: disable=protected-access

    def test_require_env_var_empty_string(self, rds_module):
        """Test getting a required environment variable that is empty."""
        from unittest.mock import patch

        with patch.dict("os.environ", {"EMPTY_VAR": ""}):
            with pytest.raises(RuntimeError, match="EMPTY_VAR is required"):
                rds_module._require_env_var("EMPTY_VAR")  # pylint: disable=protected-access

    def test_require_env_var_whitespace_only(self, rds_module):
        """Test getting a required environment variable that contains only whitespace."""
        from unittest.mock import patch

        with patch.dict("os.environ", {"WHITESPACE_VAR": "   "}):
            with pytest.raises(RuntimeError, match="WHITESPACE_VAR is required"):
                rds_module._require_env_var("WHITESPACE_VAR")  # pylint: disable=protected-access

    def test_require_env_var_strips_whitespace(self, rds_module):
        """Test that _require_env_var strips whitespace."""
        from unittest.mock import patch

        with patch.dict("os.environ", {"TRIMMED_VAR": "  value  "}):
            result = rds_module._require_env_var("TRIMMED_VAR")  # pylint: disable=protected-access
            assert result == "value"


class TestParseRequiredPortShared:
    """Shared tests for _parse_required_port function."""

    def test_parse_required_port_valid(self, rds_module):
        """Test parsing a valid port number."""
        from unittest.mock import patch

        with patch.dict("os.environ", {"TEST_PORT": "5432"}):
            result = rds_module._parse_required_port("TEST_PORT")  # pylint: disable=protected-access
            assert result == 5432

    def test_parse_required_port_invalid(self, rds_module):
        """Test parsing an invalid port number."""
        from unittest.mock import patch

        with patch.dict("os.environ", {"TEST_PORT": "not_a_number"}):
            with pytest.raises(RuntimeError, match="must be a valid integer"):
                rds_module._parse_required_port("TEST_PORT")  # pylint: disable=protected-access

    def test_parse_required_port_missing(self, rds_module):
        """Test parsing a missing port environment variable."""
        from unittest.mock import patch

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="MISSING_PORT is required"):
                rds_module._parse_required_port("MISSING_PORT")  # pylint: disable=protected-access
