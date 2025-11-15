"""Tests for cost_toolkit/scripts/rds/explore_aurora_data.py module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cost_toolkit.scripts.rds.explore_aurora_data import (
    MAX_SAMPLE_COLUMNS,
    PSYCOPG2_AVAILABLE,
    explore_aurora_database,
    main,
)


@pytest.fixture(name="mock_psycopg2")
def _mock_psycopg2():
    """Create a mock psycopg2 module."""
    psycopg2_module = MagicMock()
    psycopg2_module.Error = Exception
    return psycopg2_module


@pytest.fixture
def mock_psycopg2_connection():
    """Create a mock psycopg2 connection and cursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


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
    with patch(
        "cost_toolkit.scripts.rds.explore_aurora_data.explore_aurora_database"
    ) as mock_explore:
        main()
        mock_explore.assert_called_once()


def test_explore_aurora_database_connection_failed(
    capsys, mock_psycopg2
):  # pylint: disable=redefined-outer-name
    """Test explore_aurora_database handles connection failure."""
    mock_psycopg2.connect.side_effect = Exception("Connection refused")

    module = "cost_toolkit.scripts.rds.explore_aurora_data"
    with patch(f"{module}.PSYCOPG2_AVAILABLE", True):
        with patch(f"{module}.psycopg2", mock_psycopg2, create=True):
            explore_aurora_database()

    captured = capsys.readouterr()
    assert "Connection failed" in captured.out


def test_explore_aurora_database_successful_connection_empty(
    capsys, mock_psycopg2
):  # pylint: disable=redefined-outer-name
    """Test explore_aurora_database with successful connection but no tables."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_psycopg2.connect.return_value = mock_conn

    # Mock database inspection functions to return no tables
    module = "cost_toolkit.scripts.rds.explore_aurora_data"
    with patch(f"{module}.PSYCOPG2_AVAILABLE", True):
        with patch(f"{module}.psycopg2", mock_psycopg2, create=True):
            with patch(
                "cost_toolkit.scripts.rds.explore_aurora_data.list_tables"
            ) as mock_list_tables:
                mock_list_tables.return_value = []
                with patch(
                    "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables"
                ) as mock_analyze:
                    mock_analyze.return_value = 0
                    explore_aurora_database()

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
            with patch(
                "cost_toolkit.scripts.rds.explore_aurora_data.list_tables"
            ) as mock_list_tables:
                mock_list_tables.return_value = mock_tables
                with patch(
                    "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables"
                ) as mock_analyze:
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
            with (
                patch(
                    "cost_toolkit.scripts.rds.explore_aurora_data.print_database_version_info"
                ) as mock_version,
                patch("cost_toolkit.scripts.rds.explore_aurora_data.list_databases") as mock_dbs,
                patch("cost_toolkit.scripts.rds.explore_aurora_data.list_schemas") as mock_schemas,
                patch("cost_toolkit.scripts.rds.explore_aurora_data.list_tables") as mock_tables,
                patch("cost_toolkit.scripts.rds.explore_aurora_data.list_views") as mock_views,
                patch(
                    "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables"
                ) as mock_analyze,
                patch(
                    "cost_toolkit.scripts.rds.explore_aurora_data.get_database_size"
                ) as mock_size,
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
            with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_tables") as mock_tables:
                mock_tables.return_value = []
                with patch(
                    "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables"
                ) as mock_analyze:
                    mock_analyze.return_value = 0
                    explore_aurora_database()

    # Verify cursor and connection were closed
    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()


def test_explore_aurora_database_passes_max_sample_columns(mock_psycopg2):
    """Test explore_aurora_database passes MAX_SAMPLE_COLUMNS to analyze_tables."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_psycopg2.connect.return_value = mock_conn
    mock_tables = [("public", "test_table", "postgres")]

    with patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True):
        with patch(
            "cost_toolkit.scripts.rds.explore_aurora_data.psycopg2",
            mock_psycopg2,
            create=True,
        ):
            with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_tables") as mock_list:
                mock_list.return_value = mock_tables
                with patch(
                    "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables"
                ) as mock_analyze:
                    mock_analyze.return_value = 100
                    explore_aurora_database()

                    # Verify analyze_tables was called with correct parameters
                    mock_analyze.assert_called_once_with(
                        mock_cursor, mock_tables, MAX_SAMPLE_COLUMNS
                    )


def test_explore_aurora_database_empty_cluster_shows_next_steps(capsys, mock_psycopg2):
    """Test explore_aurora_database shows next steps when cluster is empty."""
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
            with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_tables") as mock_tables:
                mock_tables.return_value = []
                with patch(
                    "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables"
                ) as mock_analyze:
                    mock_analyze.return_value = 0
                    explore_aurora_database()

    captured = capsys.readouterr()
    assert "NEXT STEPS:" in captured.out
    assert "Your Aurora Serverless v2 cluster is empty" in captured.out
    assert "Your original data is in the restored RDS instance" in captured.out
    assert "We need the original password" in captured.out
    assert "you can delete the expensive RDS instance" in captured.out


def test_explore_aurora_database_connection_timeout_parameter(mock_psycopg2):
    """Test explore_aurora_database uses correct connection timeout."""
    mock_psycopg2.connect.side_effect = Exception("Connection failed")

    with patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True):
        with patch(
            "cost_toolkit.scripts.rds.explore_aurora_data.psycopg2",
            mock_psycopg2,
            create=True,
        ):
            explore_aurora_database()

            # Verify connect was called with timeout parameter
            mock_psycopg2.connect.assert_called_once()
            call_kwargs = mock_psycopg2.connect.call_args[1]
            assert "connect_timeout" in call_kwargs
            assert call_kwargs["connect_timeout"] == 30


def test_main_calls_explore_aurora_database():
    """Test main function calls explore_aurora_database."""
    with patch(
        "cost_toolkit.scripts.rds.explore_aurora_data.explore_aurora_database"
    ) as mock_explore:
        main()
        mock_explore.assert_called_once()


def test_explore_aurora_database_with_tables_but_no_rows(capsys, mock_psycopg2):
    """Test explore_aurora_database with tables that have no rows."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_psycopg2.connect.return_value = mock_conn
    mock_tables = [("public", "empty_table", "postgres")]

    with patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True):
        with patch(
            "cost_toolkit.scripts.rds.explore_aurora_data.psycopg2",
            mock_psycopg2,
            create=True,
        ):
            with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_tables") as mock_list:
                mock_list.return_value = mock_tables
                with patch(
                    "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables"
                ) as mock_analyze:
                    mock_analyze.return_value = 0  # Tables exist but have 0 rows
                    explore_aurora_database()

    captured = capsys.readouterr()
    # Should still show empty cluster message even if tables exist
    assert "Aurora Serverless v2 cluster is EMPTY" in captured.out


def test_explore_aurora_database_prints_connecting_message(capsys, mock_psycopg2):
    """Test explore_aurora_database prints connecting message."""
    mock_psycopg2.connect.side_effect = Exception("Connection failed")

    with patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True):
        with patch(
            "cost_toolkit.scripts.rds.explore_aurora_data.psycopg2",
            mock_psycopg2,
            create=True,
        ):
            explore_aurora_database()

    captured = capsys.readouterr()
    assert "Connecting to Aurora Serverless v2 cluster..." in captured.out


def test_explore_aurora_database_prints_database_info_header(capsys, mock_psycopg2):
    """Test explore_aurora_database prints database info header."""
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
            with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_tables") as mock_tables:
                mock_tables.return_value = []
                with patch(
                    "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables"
                ) as mock_analyze:
                    mock_analyze.return_value = 0
                    explore_aurora_database()

    captured = capsys.readouterr()
    assert "AURORA SERVERLESS V2 DATABASE INFORMATION:" in captured.out


def test_explore_aurora_database_no_user_tables_message(capsys, mock_psycopg2):
    """Test explore_aurora_database shows message when no user tables found."""
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
            with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_tables") as mock_list:
                mock_list.return_value = []
                with patch(
                    "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables"
                ) as mock_analyze:
                    mock_analyze.return_value = 0
                    explore_aurora_database()

    captured = capsys.readouterr()
    assert "No user tables found - Aurora cluster appears to be empty" in captured.out
