"""Comprehensive tests for cost_toolkit/scripts/rds/db_inspection_common.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cost_toolkit.scripts.rds.db_inspection_common import (
    analyze_tables,
    get_database_size,
    get_database_version_info,
    get_table_columns,
    list_databases,
    list_functions,
    list_schemas,
    list_tables,
    list_views,
    print_database_version_info,
    show_sample_data,
)


class TestListDatabases:
    """Tests for list_databases function."""

    def test_list_databases_with_results(self, capsys):
        """Test listing databases with multiple results."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("postgres",), ("mydb",), ("testdb",)]

        list_databases(mock_cursor)

        mock_cursor.execute.assert_called_once()
        assert "SELECT datname FROM pg_database" in mock_cursor.execute.call_args[0][0]
        captured = capsys.readouterr()
        assert "AVAILABLE DATABASES:" in captured.out
        assert "postgres" in captured.out
        assert "mydb" in captured.out
        assert "testdb" in captured.out

    def test_list_databases_empty(self, capsys):
        """Test listing databases with no results."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        list_databases(mock_cursor)

        captured = capsys.readouterr()
        assert "AVAILABLE DATABASES:" in captured.out


class TestListSchemas:
    """Tests for list_schemas function."""

    def test_list_schemas_with_results(self, capsys):
        """Test listing schemas with multiple results."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("public",), ("custom_schema",)]

        list_schemas(mock_cursor)

        mock_cursor.execute.assert_called_once()
        captured = capsys.readouterr()
        assert "USER SCHEMAS:" in captured.out
        assert "public" in captured.out
        assert "custom_schema" in captured.out

    def test_list_schemas_filters_system_schemas(self):
        """Test that system schemas are filtered in query."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("public",)]

        list_schemas(mock_cursor)

        query = mock_cursor.execute.call_args[0][0]
        assert "information_schema" in query
        assert "pg_catalog" in query
        assert "pg_toast" in query


class TestListTables:
    """Tests for list_tables function."""

    def test_list_tables_with_results(self, capsys):
        """Test listing tables with multiple results."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("public", "users", "postgres"),
            ("public", "orders", "admin"),
        ]

        result = list_tables(mock_cursor)

        assert result == [("public", "users", "postgres"), ("public", "orders", "admin")]
        captured = capsys.readouterr()
        assert "USER TABLES:" in captured.out
        assert "public.users (owner: postgres)" in captured.out
        assert "public.orders (owner: admin)" in captured.out

    def test_list_tables_empty(self, capsys):
        """Test listing tables with no results."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        result = list_tables(mock_cursor)

        assert result == []
        captured = capsys.readouterr()
        assert "No user tables found" in captured.out


class TestListViews:
    """Tests for list_views function."""

    def test_list_views_with_results(self, capsys):
        """Test listing views with multiple results."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("public", "user_summary", "postgres"),
            ("public", "order_stats", "admin"),
        ]

        list_views(mock_cursor)

        captured = capsys.readouterr()
        assert "USER VIEWS:" in captured.out
        assert "public.user_summary (owner: postgres)" in captured.out
        assert "public.order_stats (owner: admin)" in captured.out

    def test_list_views_empty(self, capsys):
        """Test listing views with no results."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        list_views(mock_cursor)

        captured = capsys.readouterr()
        assert "No user views found" in captured.out


class TestGetTableColumns:
    """Tests for get_table_columns function."""

    def test_get_table_columns_within_max_display(self, capsys):
        """Test getting columns when count is within max display."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("id", "integer", "NO", None),
            ("name", "varchar", "YES", None),
            ("created_at", "timestamp", "NO", "now()"),
        ]

        result = get_table_columns(mock_cursor, "public", "users", max_display=5)

        assert len(result) == 3
        captured = capsys.readouterr()
        assert "Columns (3):" in captured.out
        assert "id (integer) NOT NULL" in captured.out
        assert "name (varchar) NULL" in captured.out
        assert "created_at (timestamp) NOT NULL DEFAULT now()" in captured.out

    def test_get_table_columns_exceeds_max_display(self, capsys):
        """Test getting columns when count exceeds max display."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("col1", "integer", "NO", None),
            ("col2", "varchar", "YES", None),
            ("col3", "text", "YES", None),
            ("col4", "boolean", "NO", "false"),
            ("col5", "timestamp", "NO", None),
            ("col6", "json", "YES", None),
        ]

        result = get_table_columns(mock_cursor, "public", "big_table", max_display=3)

        assert len(result) == 6
        captured = capsys.readouterr()
        assert "Columns (6):" in captured.out
        assert "col1 (integer)" in captured.out
        assert "col2 (varchar)" in captured.out
        assert "col3 (text)" in captured.out
        assert "and 3 more columns" in captured.out


class TestShowSampleData:
    """Tests for show_sample_data function."""

    def test_show_sample_data_with_rows(self, capsys):
        """Test showing sample data with multiple rows."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (1, "Alice", "alice@example.com"),
            (2, "Bob", "bob@example.com"),
        ]
        mock_cursor.description = [
            ("id",),
            ("name",),
            ("email",),
        ]

        show_sample_data(mock_cursor, "public", "users", limit=2)

        mock_cursor.execute.assert_called_once()
        assert 'SELECT * FROM "public"."users" LIMIT 2' in mock_cursor.execute.call_args[0][0]
        captured = capsys.readouterr()
        assert "Sample data:" in captured.out
        assert "Row 1:" in captured.out
        assert "Row 2:" in captured.out
        assert "Alice" in captured.out
        assert "Bob" in captured.out

    def test_show_sample_data_empty(self, capsys):
        """Test showing sample data with no rows."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        show_sample_data(mock_cursor, "public", "empty_table", limit=2)

        captured = capsys.readouterr()
        assert "Sample data:" not in captured.out

    def test_show_sample_data_custom_limit(self):
        """Test showing sample data with custom limit."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        show_sample_data(mock_cursor, "public", "users", limit=10)

        assert "LIMIT 10" in mock_cursor.execute.call_args[0][0]


def test_get_database_version_info():
    """Test getting database version and name."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [
        ("PostgreSQL 14.5 on x86_64-pc-linux-gnu",),
        ("mydb",),
    ]

    version, db_name = get_database_version_info(mock_cursor)

    assert version == "PostgreSQL 14.5 on x86_64-pc-linux-gnu"
    assert db_name == "mydb"
    assert mock_cursor.execute.call_count == 2


def test_print_database_version_info(capsys):
    """Test printing database version information."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [
        ("PostgreSQL 14.5",),
        ("testdb",),
    ]

    print_database_version_info(mock_cursor)

    captured = capsys.readouterr()
    assert "DATABASE INFORMATION:" in captured.out
    assert "PostgreSQL Version: PostgreSQL 14.5" in captured.out
    assert "Current Database: testdb" in captured.out


class TestListFunctions:
    """Tests for list_functions function."""

    def test_list_functions_with_results(self, capsys):
        """Test listing functions with multiple results."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("public", "calculate_total", "FUNCTION"),
            ("public", "update_stats", "PROCEDURE"),
        ]

        list_functions(mock_cursor)

        captured = capsys.readouterr()
        assert "USER FUNCTIONS:" in captured.out
        assert "public.calculate_total (FUNCTION)" in captured.out
        assert "public.update_stats (PROCEDURE)" in captured.out

    def test_list_functions_empty(self, capsys):
        """Test listing functions with no results."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        list_functions(mock_cursor)

        captured = capsys.readouterr()
        assert "No user functions found" in captured.out


class TestGetDatabaseSize:
    """Tests for get_database_size function."""

    def test_get_database_size(self, capsys):
        """Test getting database size."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("42 MB",)

        result = get_database_size(mock_cursor)

        assert result == "42 MB"
        mock_cursor.execute.assert_called_once()
        assert "pg_size_pretty" in mock_cursor.execute.call_args[0][0]
        captured = capsys.readouterr()
        assert "DATABASE SIZE:" in captured.out
        assert "Database Size: 42 MB" in captured.out

    def test_get_database_size_large(self, capsys):
        """Test getting large database size."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("5.2 GB",)

        result = get_database_size(mock_cursor)

        assert result == "5.2 GB"
        captured = capsys.readouterr()
        assert "5.2 GB" in captured.out


class TestAnalyzeTables:
    """Tests for analyze_tables function."""

    def test_analyze_tables_with_data(self, capsys):
        """Test analyzing tables with data."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [(100,), (50,)]
        mock_cursor.fetchall.side_effect = [
            [("id", "integer", "NO", None)],
            [(1, "test")],
            [("id", "integer", "NO", None)],
            [(1, "test")],
        ]
        mock_cursor.description = [("id",), ("name",)]

        tables = [
            ("public", "users", "postgres"),
            ("public", "orders", "postgres"),
        ]

        total = analyze_tables(mock_cursor, tables, max_sample_columns=5)

        assert total == 150
        captured = capsys.readouterr()
        assert "TABLE DATA ANALYSIS:" in captured.out
        assert "public.users: 100 rows" in captured.out
        assert "public.orders: 50 rows" in captured.out
        assert "SUMMARY:" in captured.out
        assert "Total Tables: 2" in captured.out
        assert "Total Rows: 150" in captured.out

    def test_analyze_tables_empty_list(self):
        """Test analyzing empty table list."""
        mock_cursor = MagicMock()

        total = analyze_tables(mock_cursor, [], max_sample_columns=5)

        assert total == 0
        mock_cursor.execute.assert_not_called()

    def test_analyze_tables_with_errors(self):
        """Test analyzing tables with errors."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = Exception("Connection lost")

        tables = [("public", "users", "postgres")]

        with pytest.raises(Exception, match="Connection lost"):
            analyze_tables(mock_cursor, tables, max_sample_columns=5)

    def test_analyze_tables_empty_tables(self, capsys):
        """Test analyzing tables with no rows."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)

        tables = [("public", "empty_table", "postgres")]

        total = analyze_tables(mock_cursor, tables, max_sample_columns=5)

        assert total == 0
        captured = capsys.readouterr()
        assert "empty_table: 0 rows" in captured.out
        # Should not attempt to get columns or sample data for empty tables
        assert mock_cursor.fetchall.call_count == 0
