"""Additional explore_aurora_data tests."""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.scripts.rds.explore_aurora_data import explore_aurora_database
from tests.explore_aurora_data_fixtures import (
    assert_main_invokes_explore,
    run_basic_aurora_exploration,
)

pytest_plugins = ["tests.explore_aurora_data_fixtures"]


def test_explore_aurora_database_connection_timeout_parameter(mock_psycopg2):
    """Test explore_aurora_database uses correct connection timeout."""
    mock_psycopg2.connect.side_effect = Exception("Connection failed")

    def getenv_side_effect(key, _default=None):
        if key == "AURORA_PORT":
            return "5432"
        return "dummy_password"

    with patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True):
        with patch(
            "cost_toolkit.scripts.rds.explore_aurora_data.psycopg2",
            mock_psycopg2,
            create=True,
        ):
            with patch("os.environ.get", side_effect=getenv_side_effect):
                explore_aurora_database()

                # Verify connect was called with timeout parameter
                mock_psycopg2.connect.assert_called_once()
                call_kwargs = mock_psycopg2.connect.call_args[1]
                assert "connect_timeout" in call_kwargs
                assert call_kwargs["connect_timeout"] == 30


def test_main_calls_explore_aurora_database():
    """Test main function calls explore_aurora_database."""
    assert_main_invokes_explore()


def test_explore_aurora_database_with_tables_but_no_rows(capsys, mock_psycopg2):
    """Test explore_aurora_database with tables that have no rows."""
    run_basic_aurora_exploration(
        mock_psycopg2,
        env_overrides={"AURORA_PORT": "5432", "AURORA_PASSWORD": "dummy_password"},
        list_tables_return=[],
        analyze_return=0,
    )

    captured = capsys.readouterr()
    # Should still show empty cluster message even if tables exist
    assert "Aurora Serverless v2 cluster is EMPTY" in captured.out

    run_basic_aurora_exploration(
        mock_psycopg2,
        env_overrides={"AURORA_PORT": "5432", "AURORA_PASSWORD": "dummy_password"},
    )

    captured = capsys.readouterr()
    assert "Connecting to Aurora Serverless v2 cluster..." in captured.out


def test_explore_aurora_database_prints_database_info_header(capsys, mock_psycopg2):
    """Test explore_aurora_database prints database info header."""
    run_basic_aurora_exploration(mock_psycopg2)

    captured = capsys.readouterr()
    assert "AURORA SERVERLESS V2 DATABASE INFORMATION:" in captured.out


def test_explore_aurora_database_no_user_tables_message(capsys, mock_psycopg2):
    """Test explore_aurora_database shows message when no user tables found."""
    run_basic_aurora_exploration(mock_psycopg2)

    captured = capsys.readouterr()
    assert "No user tables found - Aurora cluster appears to be empty" in captured.out
