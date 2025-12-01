"""Comprehensive tests for cost_toolkit/scripts/rds/explore_aurora_data.py."""

from __future__ import annotations

from unittest import mock
from unittest.mock import Mock, patch

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


class TestRequireEnvVar:
    """Tests for _require_env_var function."""

    def test_require_env_var_present(self):
        """Test getting a required environment variable that exists."""
        with patch.dict("os.environ", {"TEST_VAR": "test_value"}):
            result = explore_aurora_data._require_env_var("TEST_VAR")
            assert result == "test_value"

    def test_require_env_var_missing(self):
        """Test getting a required environment variable that doesn't exist."""
        with patch.dict("os.environ", {}, clear=True):
            try:
                explore_aurora_data._require_env_var("MISSING_VAR")
                assert False, "Should have raised RuntimeError"
            except RuntimeError as exc:
                assert "MISSING_VAR is required" in str(exc)

    def test_require_env_var_empty_string(self):
        """Test getting a required environment variable that is empty."""
        with patch.dict("os.environ", {"EMPTY_VAR": ""}):
            try:
                explore_aurora_data._require_env_var("EMPTY_VAR")
                assert False, "Should have raised RuntimeError"
            except RuntimeError as exc:
                assert "EMPTY_VAR is required" in str(exc)

    def test_require_env_var_whitespace_only(self):
        """Test getting a required environment variable that contains only whitespace."""
        with patch.dict("os.environ", {"WHITESPACE_VAR": "   "}):
            try:
                explore_aurora_data._require_env_var("WHITESPACE_VAR")
                assert False, "Should have raised RuntimeError"
            except RuntimeError as exc:
                assert "WHITESPACE_VAR is required" in str(exc)

    def test_require_env_var_strips_whitespace(self):
        """Test that _require_env_var strips whitespace."""
        with patch.dict("os.environ", {"TRIMMED_VAR": "  value  "}):
            result = explore_aurora_data._require_env_var("TRIMMED_VAR")
            assert result == "value"


class TestParseRequiredPort:
    """Tests for _parse_required_port function."""

    def test_parse_required_port_valid(self):
        """Test parsing a valid port number."""
        with patch.dict("os.environ", {"TEST_PORT": "5432"}):
            result = explore_aurora_data._parse_required_port("TEST_PORT")
            assert result == 5432

    def test_parse_required_port_invalid(self):
        """Test parsing an invalid port number."""
        with patch.dict("os.environ", {"TEST_PORT": "not_a_number"}):
            try:
                explore_aurora_data._parse_required_port("TEST_PORT")
                assert False, "Should have raised RuntimeError"
            except RuntimeError as exc:
                assert "must be a valid integer" in str(exc)
                assert "not_a_number" in str(exc)

    def test_parse_required_port_missing(self):
        """Test parsing a missing port environment variable."""
        with patch.dict("os.environ", {}, clear=True):
            try:
                explore_aurora_data._parse_required_port("MISSING_PORT")
                assert False, "Should have raised RuntimeError"
            except RuntimeError as exc:
                assert "MISSING_PORT is required" in str(exc)


class TestLoadAuroraSettings:
    """Tests for _load_aurora_settings function."""

    def test_load_aurora_settings_complete(self):
        """Test loading complete Aurora settings."""
        env = {
            "AURORA_HOST": "aurora.example.com",
            "AURORA_PORT": "5432",
            "AURORA_DATABASE": "testdb",
            "AURORA_USERNAME": "admin",
            "AURORA_PASSWORD": "password123",
        }
        with patch.dict("os.environ", env):
            host, port, database, username, password = explore_aurora_data._load_aurora_settings()
            assert host == "aurora.example.com"
            assert port == 5432
            assert database == "testdb"
            assert username == "admin"
            assert password == "password123"

    def test_load_aurora_settings_missing_host(self):
        """Test loading Aurora settings with missing HOST."""
        env = {
            "AURORA_PORT": "5432",
            "AURORA_DATABASE": "testdb",
            "AURORA_USERNAME": "admin",
            "AURORA_PASSWORD": "password123",
        }
        with patch.dict("os.environ", env, clear=True):
            try:
                explore_aurora_data._load_aurora_settings()
                assert False, "Should have raised RuntimeError"
            except RuntimeError as exc:
                assert "AURORA_HOST is required" in str(exc)


class TestExploreAuroraReturnValues:
    """Tests for explore_aurora_database return values."""

    @patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", False)
    def test_explore_returns_false_when_psycopg2_unavailable(self):
        """Test that explore returns False when psycopg2 is unavailable."""
        result = explore_aurora_data.explore_aurora_database()
        assert result is False

    @patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True)
    @patch("cost_toolkit.scripts.rds.explore_aurora_data._load_aurora_settings")
    def test_explore_returns_false_when_password_missing(self, mock_load, capsys):
        """Test that explore returns False when password is empty."""
        mock_load.return_value = ("host", 5432, "db", "user", "")
        result = explore_aurora_data.explore_aurora_database()
        assert result is False
        captured = capsys.readouterr()
        assert "Aurora credentials not configured" in captured.out


class TestMainReturnCode:
    """Tests for main function return codes."""

    @patch("cost_toolkit.scripts.rds.explore_aurora_data.explore_aurora_database")
    def test_main_returns_zero_on_success(self, mock_explore):
        """Test that main returns 0 when explore succeeds."""
        mock_explore.return_value = True
        result = explore_aurora_data.main()
        assert result == 0

    @patch("cost_toolkit.scripts.rds.explore_aurora_data.explore_aurora_database")
    def test_main_returns_one_on_failure(self, mock_explore):
        """Test that main returns 1 when explore fails."""
        mock_explore.return_value = False
        result = explore_aurora_data.main()
        assert result == 1


class TestExploreWithSuccessfulConnection:
    """Tests for successful Aurora database connection."""

    @patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True)
    @patch("cost_toolkit.scripts.rds.explore_aurora_data._load_aurora_settings")
    def test_explore_with_successful_connection(self, mock_load, capsys):
        """Test explore_aurora_database with successful database connection."""
        import sys

        mock_psycopg2 = mock.Mock()
        mock_connection = mock.Mock()
        mock_cursor = mock.Mock()
        mock_psycopg2.connect.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        sys.modules["psycopg2"] = mock_psycopg2
        mock_load.return_value = ("localhost", 5432, "testdb", "admin", "password")

        with patch("cost_toolkit.scripts.rds.explore_aurora_data.print_database_version_info"):
            with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_databases"):
                with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_schemas"):
                    with patch(
                        "cost_toolkit.scripts.rds.explore_aurora_data.list_tables", return_value=[]
                    ):
                        with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_views"):
                            with patch(
                                "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables",
                                return_value=0,
                            ):
                                with patch(
                                    "cost_toolkit.scripts.rds.explore_aurora_data.get_database_size"
                                ):
                                    with patch(
                                        "cost_toolkit.scripts.rds.explore_aurora_data.list_functions"
                                    ):
                                        result = explore_aurora_data.explore_aurora_database()

        del sys.modules["psycopg2"]

        assert result is True
        mock_connection.close.assert_called_once()
        mock_cursor.close.assert_called_once()


class TestExploreWithConnectionError:
    """Tests for Aurora database connection failures."""

    @patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True)
    @patch("cost_toolkit.scripts.rds.explore_aurora_data._load_aurora_settings")
    def test_explore_connection_error(self, mock_load, capsys):
        """Test explore_aurora_database with connection error."""
        import sys

        mock_psycopg2 = mock.Mock()
        mock_psycopg2.Error = Exception
        mock_psycopg2.connect.side_effect = Exception("Connection failed")

        sys.modules["psycopg2"] = mock_psycopg2
        mock_load.return_value = ("localhost", 5432, "testdb", "admin", "password")

        result = explore_aurora_data.explore_aurora_database()

        del sys.modules["psycopg2"]

        assert result is False
        captured = capsys.readouterr()
        assert "Connection failed" in captured.out


class TestExploreEmptyDatabase:
    """Tests for Aurora database exploration with no data."""

    @patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True)
    @patch("cost_toolkit.scripts.rds.explore_aurora_data._load_aurora_settings")
    def test_explore_with_empty_database(self, mock_load, capsys):
        """Test explore_aurora_database when database has no tables."""
        import sys

        mock_psycopg2 = mock.Mock()
        mock_connection = mock.Mock()
        mock_cursor = mock.Mock()
        mock_psycopg2.connect.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        sys.modules["psycopg2"] = mock_psycopg2
        mock_load.return_value = ("localhost", 5432, "testdb", "admin", "password")

        with patch("cost_toolkit.scripts.rds.explore_aurora_data.print_database_version_info"):
            with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_databases"):
                with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_schemas"):
                    with patch(
                        "cost_toolkit.scripts.rds.explore_aurora_data.list_tables", return_value=[]
                    ):
                        with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_views"):
                            with patch(
                                "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables",
                                return_value=0,
                            ):
                                with patch(
                                    "cost_toolkit.scripts.rds.explore_aurora_data.get_database_size"
                                ):
                                    with patch(
                                        "cost_toolkit.scripts.rds.explore_aurora_data.list_functions"
                                    ):
                                        result = explore_aurora_data.explore_aurora_database()

        del sys.modules["psycopg2"]

        assert result is True
        captured = capsys.readouterr()
        assert "empty" in captured.out.lower() or "no user data" in captured.out.lower()


class TestExploreWithData:
    """Tests for Aurora database exploration with populated data."""

    @patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True)
    @patch("cost_toolkit.scripts.rds.explore_aurora_data._load_aurora_settings")
    def test_explore_with_data_in_database(self, mock_load, capsys):
        """Test explore_aurora_database when database contains data."""
        import sys

        mock_psycopg2 = mock.Mock()
        mock_connection = mock.Mock()
        mock_cursor = mock.Mock()
        mock_psycopg2.connect.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        sys.modules["psycopg2"] = mock_psycopg2
        mock_load.return_value = ("localhost", 5432, "testdb", "admin", "password")

        with patch("cost_toolkit.scripts.rds.explore_aurora_data.print_database_version_info"):
            with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_databases"):
                with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_schemas"):
                    with patch(
                        "cost_toolkit.scripts.rds.explore_aurora_data.list_tables",
                        return_value=[{"name": "test_table"}],
                    ):
                        with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_views"):
                            with patch(
                                "cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables",
                                return_value=100,
                            ):
                                with patch(
                                    "cost_toolkit.scripts.rds.explore_aurora_data.get_database_size"
                                ):
                                    with patch(
                                        "cost_toolkit.scripts.rds.explore_aurora_data.list_functions"
                                    ):
                                        result = explore_aurora_data.explore_aurora_database()

        del sys.modules["psycopg2"]

        assert result is True
        captured = capsys.readouterr()
        assert "completed" in captured.out.lower()
