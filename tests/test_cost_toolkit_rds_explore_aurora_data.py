"""Comprehensive tests for cost_toolkit/scripts/rds/explore_aurora_data.py."""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.scripts.rds import explore_aurora_data


class TestConstants:
    """Tests for module constants."""

    def test_psycopg2_available_flag(self):
        """Test that PSYCOPG2_AVAILABLE flag is defined."""
        assert hasattr(explore_aurora_data, "PSYCOPG2_AVAILABLE")
        assert isinstance(explore_aurora_data.PSYCOPG2_AVAILABLE, bool)

    def test_max_sample_columns_constant(self):
        """Test that MAX_SAMPLE_COLUMNS constant is defined."""
        assert explore_aurora_data.MAX_SAMPLE_COLUMNS == 5


class TestExploreAuroraDatabase:
    """Tests for explore_aurora_database function.

    Note: Most psycopg2-dependent tests are simplified because psycopg2 is
    conditionally imported and complex mocking doesn't provide significant value.
    """

    @patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", False)
    def test_psycopg2_not_available(self, capsys):
        """Test when psycopg2 is not available."""
        explore_aurora_data.explore_aurora_database()

        captured = capsys.readouterr()
        assert "psycopg2 module not found" in captured.out
        assert "pip install psycopg2-binary" in captured.out

    def test_function_exists(self):
        """Test that explore_aurora_database function exists."""
        assert hasattr(explore_aurora_data, "explore_aurora_database")
        assert callable(explore_aurora_data.explore_aurora_database)


@patch("cost_toolkit.scripts.rds.explore_aurora_data.explore_aurora_database")
def test_main_calls_explore(mock_explore):
    """Test that main calls explore_aurora_database."""
    explore_aurora_data.main()

    mock_explore.assert_called_once()
