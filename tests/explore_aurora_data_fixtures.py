"""Fixtures for explore_aurora_data tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_psycopg2():
    """Create a mock psycopg2 module."""
    psycopg2_module = MagicMock()
    psycopg2_module.Error = Exception
    return psycopg2_module
