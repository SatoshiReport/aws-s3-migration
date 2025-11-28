"""Comprehensive tests for cost_toolkit/scripts/rds/explore_user_data.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.rds import explore_user_data


class TestPsycopg2Availability:
    """Tests for psycopg2 availability check."""

    def test_psycopg2_available_flag_true(self):
        """Test that PSYCOPG2_AVAILABLE flag is set when module is available."""
        # Module imports at top, so if tests run, psycopg2 is mocked or available
        assert hasattr(explore_user_data, "PSYCOPG2_AVAILABLE")
        assert isinstance(explore_user_data.PSYCOPG2_AVAILABLE, bool)

    def test_max_sample_columns_constant(self):
        """Test that MAX_SAMPLE_COLUMNS constant is defined."""
        assert explore_user_data.MAX_SAMPLE_COLUMNS == 5


def test_function_exists():
    """Test that _try_database_connection function exists.

    Note: This test exists because psycopg2 is conditionally imported
    and testing these functions requires complex mocking that doesn't provide
    significant value. The function behavior is covered by integration testing.
    """
    assert hasattr(explore_user_data, "_try_database_connection")
    # pylint: disable=protected-access
    assert callable(explore_user_data._try_database_connection)


class TestTryDatabaseConnection:
    """Tests for _try_database_connection function."""

    def test_module_psycopg2_availability_flag(self):
        """Test that PSYCOPG2_AVAILABLE flag is correctly set."""
        assert hasattr(explore_user_data, "PSYCOPG2_AVAILABLE")
        assert isinstance(explore_user_data.PSYCOPG2_AVAILABLE, bool)

    def test_successful_connection_first_attempt(self, capsys):
        """Test successful connection on first attempt."""
        mock_conn = MagicMock()
        mock_psycopg2 = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn

        # Inject psycopg2 into the module's globals
        original_global = explore_user_data.__dict__.get("psycopg2")
        explore_user_data.__dict__["psycopg2"] = mock_psycopg2

        try:
            result_conn, result_db = (
                explore_user_data._try_database_connection(  # pylint: disable=protected-access
                    "localhost", 5432, ["testdb"], "testuser", ["testpass"]
                )
            )

            assert result_conn == mock_conn
            assert result_db == "testdb"
            captured = capsys.readouterr()
            assert "Trying database='testdb'" in captured.out
            assert "Connected successfully!" in captured.out
        finally:
            if original_global is not None:
                explore_user_data.__dict__["psycopg2"] = original_global
            else:
                explore_user_data.__dict__.pop("psycopg2", None)


class TestExploreRestoredDatabase:
    """Tests for explore_restored_database function."""

    @patch("cost_toolkit.scripts.rds.explore_user_data.PSYCOPG2_AVAILABLE", False)
    def test_psycopg2_not_available(self, capsys):
        """Test when psycopg2 is not available."""
        explore_user_data.explore_restored_database()

        captured = capsys.readouterr()
        assert "psycopg2 module not found" in captured.out
        assert "pip install psycopg2-binary" in captured.out

    @patch("cost_toolkit.scripts.rds.explore_user_data.PSYCOPG2_AVAILABLE", True)
    @patch("cost_toolkit.scripts.rds.explore_user_data._try_database_connection")
    def test_connection_fails(self, mock_try_conn, capsys):
        """Test when connection fails."""
        mock_try_conn.return_value = (None, None)

        explore_user_data.explore_restored_database()

        captured = capsys.readouterr()
        assert "Could not connect with any combination" in captured.out
        assert "Please check the database configuration" in captured.out

    @patch("cost_toolkit.scripts.rds.explore_user_data.PSYCOPG2_AVAILABLE", True)
    def test_successful_exploration(self, capsys):
        """Test successful database exploration."""
        with (
            patch(
                "cost_toolkit.scripts.rds.explore_user_data._try_database_connection"
            ) as mock_try_conn,
            patch(
                "cost_toolkit.scripts.rds.explore_user_data.print_database_version_info"
            ) as mock_print_version,
            patch(
                "cost_toolkit.scripts.rds.explore_user_data.list_databases"
            ) as mock_list_databases,
            patch("cost_toolkit.scripts.rds.explore_user_data.list_schemas") as mock_list_schemas,
            patch("cost_toolkit.scripts.rds.explore_user_data.list_tables") as mock_list_tables,
            patch("cost_toolkit.scripts.rds.explore_user_data.list_views") as mock_list_views,
            patch("cost_toolkit.scripts.rds.explore_user_data.analyze_tables") as mock_analyze,
            patch(
                "cost_toolkit.scripts.rds.explore_user_data.get_database_size"
            ) as mock_get_db_size,
            patch(
                "cost_toolkit.scripts.rds.explore_user_data.list_functions"
            ) as mock_list_functions,
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_try_conn.return_value = (mock_conn, "postgres")
            mock_list_tables.return_value = [("public", "users", "postgres")]

            explore_user_data.explore_restored_database()

            # Verify all inspection functions were called
            mock_print_version.assert_called_once_with(mock_cursor)
            mock_list_databases.assert_called_once_with(mock_cursor)
            mock_list_schemas.assert_called_once_with(mock_cursor)
            mock_list_tables.assert_called_once_with(mock_cursor)
            mock_list_views.assert_called_once_with(mock_cursor)
            mock_analyze.assert_called_once_with(
                mock_cursor, [("public", "users", "postgres")], explore_user_data.MAX_SAMPLE_COLUMNS
            )
            mock_get_db_size.assert_called_once_with(mock_cursor)
            mock_list_functions.assert_called_once_with(mock_cursor)

            # Verify connection cleanup
            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()

            captured = capsys.readouterr()
            assert "Database exploration completed!" in captured.out

    @patch("cost_toolkit.scripts.rds.explore_user_data.PSYCOPG2_AVAILABLE", True)
    @patch("cost_toolkit.scripts.rds.explore_user_data._try_database_connection")
    def test_connection_parameters(self, mock_try_conn):
        """Test that correct connection parameters are used."""
        mock_try_conn.return_value = (None, None)

        explore_user_data.explore_restored_database()

        # Verify connection was attempted with correct parameters
        call_args = mock_try_conn.call_args[0]
        assert call_args[0] == explore_user_data.DEFAULT_RESTORED_HOST
        assert call_args[1] == explore_user_data.DEFAULT_RESTORED_PORT
        assert "postgres" in call_args[2]
        assert call_args[3] == explore_user_data.DEFAULT_RESTORED_USERNAME
        assert len(call_args[4]) > 0  # Has passwords


@patch("cost_toolkit.scripts.rds.explore_user_data.explore_restored_database")
def test_main_calls_explore(mock_explore):
    """Test that main calls explore_restored_database."""
    explore_user_data.main()

    mock_explore.assert_called_once()
