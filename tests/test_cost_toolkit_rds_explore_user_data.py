"""Comprehensive tests for cost_toolkit/scripts/rds/explore_user_data.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cost_toolkit.scripts.rds import explore_user_data
from tests.conftest_rds_shared import (
    TestConstantsShared,
    TestParseRequiredPortShared,
    TestRequireEnvVarShared,
)

EXPLORE_USER_MODULE = explore_user_data

# Re-export shared test classes for user data module
TestConstants = TestConstantsShared
TestRequireEnvVar = TestRequireEnvVarShared
TestParseRequiredPort = TestParseRequiredPortShared


class TestSplitRequiredList:
    """Tests for _split_required_list function."""

    def test_split_required_list_single_value(self):
        """Test splitting a list with single value."""
        split_required_list = getattr(EXPLORE_USER_MODULE, "_split_required_list")
        with patch.dict("os.environ", {"TEST_LIST": "db1"}):
            result = split_required_list("TEST_LIST")
            assert result == ["db1"]

    def test_split_required_list_multiple_values(self):
        """Test splitting a list with multiple values."""
        split_required_list = getattr(EXPLORE_USER_MODULE, "_split_required_list")
        with patch.dict("os.environ", {"TEST_LIST": "db1,db2,db3"}):
            result = split_required_list("TEST_LIST")
            assert result == ["db1", "db2", "db3"]

    def test_split_required_list_with_whitespace(self):
        """Test splitting a list with whitespace around values."""
        split_required_list = getattr(EXPLORE_USER_MODULE, "_split_required_list")
        with patch.dict("os.environ", {"TEST_LIST": " db1 , db2 , db3 "}):
            result = split_required_list("TEST_LIST")
            assert result == ["db1", "db2", "db3"]

    def test_split_required_list_empty_values(self):
        """Test splitting a list with only commas (empty values)."""
        split_required_list = getattr(EXPLORE_USER_MODULE, "_split_required_list")
        with patch.dict("os.environ", {"TEST_LIST": ",,"}):
            with pytest.raises(RuntimeError, match="TEST_LIST must contain at least one value"):
                split_required_list("TEST_LIST")

    def test_split_required_list_missing(self):
        """Test splitting a missing environment variable."""
        split_required_list = getattr(EXPLORE_USER_MODULE, "_split_required_list")
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="MISSING_LIST is required"):
                split_required_list("MISSING_LIST")


class TestLoadRestoredDbSettings:
    """Tests for _load_restored_db_settings function."""

    def test_load_restored_db_settings_complete(self):
        """Test loading complete restored DB settings."""
        load_restored_db_settings = getattr(EXPLORE_USER_MODULE, "_load_restored_db_settings")
        env = {
            "RESTORED_DB_HOST": "localhost",
            "RESTORED_DB_PORT": "5432",
            "RESTORED_DB_USERNAME": "admin",
            "RESTORED_DB_NAMES": "postgres,testdb",
            "RESTORED_DB_PASSWORDS": "pass1,pass2",
        }
        with patch.dict("os.environ", env):
            host, port, databases, username, passwords = load_restored_db_settings()
            assert host == "localhost"
            assert port == 5432
            assert databases == ["postgres", "testdb"]
            assert username == "admin"
            assert passwords == ["pass1", "pass2"]

    def test_load_restored_db_settings_missing_host(self):
        """Test loading restored DB settings with missing HOST."""
        load_restored_db_settings = getattr(EXPLORE_USER_MODULE, "_load_restored_db_settings")
        env = {
            "RESTORED_DB_PORT": "5432",
            "RESTORED_DB_USERNAME": "admin",
            "RESTORED_DB_NAMES": "postgres",
            "RESTORED_DB_PASSWORDS": "pass1",
        }
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(RuntimeError, match="RESTORED_DB_HOST is required"):
                load_restored_db_settings()


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

    def test_connection_failure_returns_none(self, capsys):
        """Test connection failure returns None."""
        mock_psycopg2 = MagicMock()
        mock_psycopg2.Error = Exception
        mock_psycopg2.connect.side_effect = Exception("Connection refused")

        # Inject psycopg2 into the module's globals
        original_global = explore_user_data.__dict__.get("psycopg2")
        explore_user_data.__dict__["psycopg2"] = mock_psycopg2

        try:
            result_conn, result_db = (
                explore_user_data._try_database_connection(  # pylint: disable=protected-access
                    "localhost", 5432, ["testdb"], "testuser", ["testpass"]
                )
            )

            assert result_conn is None
            assert result_db is None
            captured = capsys.readouterr()
            assert "Failed:" in captured.out
        finally:
            if original_global is not None:
                explore_user_data.__dict__["psycopg2"] = original_global
            else:
                explore_user_data.__dict__.pop("psycopg2", None)

    def test_connection_retries_with_multiple_db_and_passwords(self):
        """Test connection retries with multiple database and password combinations."""
        mock_conn = MagicMock()
        mock_psycopg2 = MagicMock()
        mock_psycopg2.Error = Exception
        # Fail first 2 times, succeed on 3rd
        mock_psycopg2.connect.side_effect = [
            Exception("Failed 1"),
            Exception("Failed 2"),
            mock_conn,
        ]

        # Inject psycopg2 into the module's globals
        original_global = explore_user_data.__dict__.get("psycopg2")
        explore_user_data.__dict__["psycopg2"] = mock_psycopg2

        try:
            result_conn, result_db = (
                explore_user_data._try_database_connection(  # pylint: disable=protected-access
                    "localhost", 5432, ["db1", "db2"], "testuser", ["pass1", "pass2"]
                )
            )

            assert result_conn == mock_conn
            assert result_db == "db2"
            assert mock_psycopg2.connect.call_count == 3
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
    @patch("cost_toolkit.scripts.rds.explore_user_data._load_restored_db_settings")
    @patch("cost_toolkit.scripts.rds.explore_user_data._try_database_connection")
    def test_connection_fails(self, mock_try_conn, mock_load, capsys):
        """Test when connection fails."""
        mock_load.return_value = ("localhost", 5432, ["postgres"], "admin", ["password"])
        mock_try_conn.return_value = (None, None)

        explore_user_data.explore_restored_database()

        captured = capsys.readouterr()
        assert "Could not connect with any combination" in captured.out
        assert "Please check the database configuration" in captured.out

    @patch("cost_toolkit.scripts.rds.explore_user_data.PSYCOPG2_AVAILABLE", True)
    @patch("cost_toolkit.scripts.rds.explore_user_data._load_restored_db_settings")
    def test_successful_exploration(self, mock_load, capsys):
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
            mock_load.return_value = ("localhost", 5432, ["postgres"], "admin", ["password"])
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


class TestMainReturnCode:
    """Tests for main function return codes."""

    @patch("cost_toolkit.scripts.rds.explore_user_data.explore_restored_database")
    def test_main_returns_zero_on_success(self, mock_explore):
        """Test that main returns 0 when explore succeeds."""
        mock_explore.return_value = True
        result = explore_user_data.main()
        assert result == 0

    @patch("cost_toolkit.scripts.rds.explore_user_data.explore_restored_database")
    def test_main_returns_one_on_failure(self, mock_explore):
        """Test that main returns 1 when explore fails."""
        mock_explore.return_value = False
        result = explore_user_data.main()
        assert result == 1
