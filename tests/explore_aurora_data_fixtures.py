"""Fixtures for explore_aurora_data tests."""

from __future__ import annotations

from typing import Callable
from unittest.mock import MagicMock, patch

import pytest

from cost_toolkit.scripts.rds.explore_aurora_data import explore_aurora_database, main


@pytest.fixture
def mock_psycopg2():
    """Create a mock psycopg2 module."""
    psycopg2_module = MagicMock()
    psycopg2_module.Error = Exception
    return psycopg2_module


def assert_main_invokes_explore():
    """Ensure the CLI entrypoint delegates to explore_aurora_database."""
    with patch("cost_toolkit.scripts.rds.explore_aurora_data.explore_aurora_database") as mock_explore:
        main()
        mock_explore.assert_called_once()


def run_basic_aurora_exploration(
    psycopg2_mock,
    list_tables_return=None,
    analyze_return=0,
    env_overrides=None,
    connect_side_effect=None,
    post_run: Callable | None = None,
):
    """Execute explore_aurora_database with standard connection mocks."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    psycopg2_mock.connect.return_value = mock_conn
    psycopg2_mock.connect.side_effect = connect_side_effect

    env_context = (
        patch.dict("os.environ", env_overrides, clear=True)
        if env_overrides is not None
        else patch("os.environ.get", return_value="dummy_password")
    )

    with patch("cost_toolkit.scripts.rds.explore_aurora_data.PSYCOPG2_AVAILABLE", True):
        with patch(
            "cost_toolkit.scripts.rds.explore_aurora_data.psycopg2",
            psycopg2_mock,
            create=True,
        ):
            with env_context:
                with patch("cost_toolkit.scripts.rds.explore_aurora_data.list_tables") as mock_tables:
                    mock_tables.return_value = list_tables_return or []
                    with patch("cost_toolkit.scripts.rds.explore_aurora_data.analyze_tables") as mock_analyze:
                        mock_analyze.return_value = analyze_return
                        explore_aurora_database()
                        if post_run is not None:
                            post_run(
                                {
                                    "tables": mock_tables,
                                    "analyze": mock_analyze,
                                    "cursor": mock_cursor,
                                    "connection": mock_conn,
                                }
                            )

    return mock_conn, mock_cursor
