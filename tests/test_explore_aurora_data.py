"""Tests for cost_toolkit/scripts/rds/explore_aurora_data.py module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.rds.explore_aurora_data import (
    MAX_SAMPLE_COLUMNS,
    PSYCOPG2_AVAILABLE,
    explore_aurora_database,
)
from tests.explore_aurora_data_fixtures import (
    assert_main_invokes_explore,
    run_basic_aurora_exploration,
)

pytest_plugins = ["tests.explore_aurora_data_fixtures"]


def test_psycopg2_available_constant():
    """Test PSYCOPG2_AVAILABLE constant is boolean."""
    assert isinstance(PSYCOPG2_AVAILABLE, bool)


def test_max_sample_columns_constant():
    """Test MAX_SAMPLE_COLUMNS has expected value."""
    assert MAX_SAMPLE_COLUMNS == 5


def test_explore_aurora_database_no_psycopg2(capsys):
    """Test explore_aurora_database handles missing psycopg2."""
    # Temporarily patch PSYCOPG2_AVAILABLE to False
    with patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", False):
        explore_aurora_database()

    captured = capsys.readouterr()
    assert "psycopg2 module not found" in captured.out
    assert "pip install psycopg2-binary" in captured.out


def test_main_function():
    """Test main function calls explore_aurora_database."""
    assert_main_invokes_explore()


def test_explore_aurora_database_connection_failed(capsys, mock_psycopg2):  # pylint: disable=redefined-outer-name
    """Test explore_aurora_database handles connection failure."""

    run_basic_aurora_exploration(
        mock_psycopg2,
        env_overrides={"AURORA_PORT": "5432", "AURORA_PASSWORD": "dummy_password"},
        connect_side_effect=Exception("Connection refused"),
    )

    captured = capsys.readouterr()
    assert "Connection failed" in captured.out


def test_explore_aurora_database_successful_connection_empty(capsys, mock_psycopg2):  # pylint: disable=redefined-outer-name
    """Test explore_aurora_database with successful connection but no tables."""
    run_basic_aurora_exploration(
        mock_psycopg2,
        list_tables_return=[],
        analyze_return=0,
        env_overrides={"AURORA_PORT": "5432", "AURORA_PASSWORD": "dummy_password"},
    )

    captured = capsys.readouterr()
    assert "Connected successfully to Aurora Serverless v2!" in captured.out
    assert "Aurora Serverless v2 exploration completed!" in captured.out
    assert "Aurora Serverless v2 cluster is EMPTY" in captured.out


def test_explore_aurora_database_successful_with_data(capsys, mock_psycopg2):
    """Test explore_aurora_database with successful connection and data."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_psycopg2.connect.return_value = mock_conn

    mock_tables = [("public", "users", "postgres"), ("public", "orders", "postgres")]

    with patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True):
        with patch(
            "cost_toolkit.scripts.rds.explore_aurora_data.psycopg2",
            mock_psycopg2,
            create=True,
        ):
            with patch.dict(
                "os.environ",
                {"AURORA_PORT": "5432", "AURORA_PASSWORD": "dummy_password"},
                clear=True,
            ):
                with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_tables") as mock_list_tables:
                    mock_list_tables.return_value = mock_tables
                    with patch("cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables") as mock_analyze:
                        mock_analyze.return_value = 1500  # Non-zero rows
                        explore_aurora_database()

    captured = capsys.readouterr()
    assert "Connected successfully to Aurora Serverless v2!" in captured.out
    assert "Aurora Serverless v2 exploration completed!" in captured.out
    # Should not show empty cluster message since total_rows > 0
    assert "Aurora Serverless v2 cluster is EMPTY" not in captured.out


def test_explore_aurora_database_calls_all_inspection_functions(mock_psycopg2):
    """Test explore_aurora_database calls all database inspection functions."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_psycopg2.connect.return_value = mock_conn

    with patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True):
        with patch(
            "cost_toolkit.scripts.rds.explore_aurora_data.psycopg2",
            mock_psycopg2,
            create=True,
        ):
            with patch.dict(
                "os.environ",
                {"AURORA_PORT": "5432", "AURORA_PASSWORD": "dummy_password"},
                clear=True,
            ):
                with (
                    patch("cost_toolkit.scripts.rds.explore_aurora_data.print_database_version_info") as mock_version,
                    patch("cost_toolkit.scripts.rds.explore_aurora_data.list_databases") as mock_dbs,
                    patch("cost_toolkit.scripts.rds.explore_aurora_data.list_schemas") as mock_schemas,
                    patch("cost_toolkit.scripts.rds.explore_aurora_data.list_tables") as mock_tables,
                    patch("cost_toolkit.scripts.rds.explore_aurora_data.list_views") as mock_views,
                    patch("cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables") as mock_analyze,
                    patch("cost_toolkit.scripts.rds.explore_aurora_data.get_database_size") as mock_size,
                    patch("cost_toolkit.scripts.rds.explore_aurora_data.list_functions") as mock_funcs,
                ):
                    mock_tables.return_value = []
                    mock_analyze.return_value = 0
                    explore_aurora_database()

                    # Verify all inspection functions were called
                    mock_version.assert_called_once()
                    mock_dbs.assert_called_once()
                    mock_schemas.assert_called_once()
                    mock_tables.assert_called_once()
                    mock_views.assert_called_once()
                    mock_analyze.assert_called_once()
                    mock_size.assert_called_once()
                    mock_funcs.assert_called_once()


def test_explore_aurora_database_closes_connection(mock_psycopg2):
    """Test explore_aurora_database properly closes connection."""
    mock_conn, mock_cursor = run_basic_aurora_exploration(mock_psycopg2)

    # Verify cursor and connection were closed
    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()


def test_explore_aurora_database_passes_max_sample_columns(mock_psycopg2):
    """Test explore_aurora_database passes MAX_SAMPLE_COLUMNS to analyze_tables."""
    mock_tables = [("public", "test_table", "postgres")]

    def _assert_calls(mocks):
        mocks["analyze"].assert_called_once_with(mocks["cursor"], mock_tables, MAX_SAMPLE_COLUMNS)

    run_basic_aurora_exploration(
        mock_psycopg2,
        list_tables_return=mock_tables,
        analyze_return=100,
        post_run=_assert_calls,
    )


def test_explore_aurora_database_empty_cluster_shows_next_steps(capsys, mock_psycopg2):
    """Test explore_aurora_database shows next steps when cluster is empty."""
    run_basic_aurora_exploration(
        mock_psycopg2,
        list_tables_return=[],
        analyze_return=0,
    )

    captured = capsys.readouterr()
    assert "NEXT STEPS:" in captured.out
    assert "Your Aurora Serverless v2 cluster is empty" in captured.out
    assert "Your original data is in the restored RDS instance" in captured.out
    assert "We need the original password" in captured.out
    assert "you can delete the expensive RDS instance" in captured.out
