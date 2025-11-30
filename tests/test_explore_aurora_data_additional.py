"""Additional explore_aurora_data tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.rds.explore_aurora_data import explore_aurora_database, main

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
                with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_tables"):
                    with patch(
                        "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables"
                    ) as mock_analyze:
                        mock_analyze.return_value = 0  # Tables exist but have 0 rows
                        explore_aurora_database()

    captured = capsys.readouterr()
    # Should still show empty cluster message even if tables exist
    assert "Aurora Serverless v2 cluster is EMPTY" in captured.out

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
            with patch("os.environ.get", return_value="dummy_password"):
                with patch(
                    "cost_toolkit.scripts.rds.explore_aurora_data.list_tables"
                ) as mock_tables:
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
            with patch.dict(
                "os.environ",
                {"AURORA_PORT": "5432", "AURORA_PASSWORD": "dummy_password"},
                clear=True,
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
