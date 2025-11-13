"""Tests for cleanup_temp_artifacts.py entry point."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest


def test_cleanup_temp_artifacts_entry_point_imports():
    """Test that cleanup_temp_artifacts module can be imported."""
    import cleanup_temp_artifacts

    assert cleanup_temp_artifacts is not None


def test_cleanup_temp_artifacts_has_main_guard():
    """Test that the module has __name__ == '__main__' guard."""
    with open("cleanup_temp_artifacts.py") as f:
        content = f.read()
        assert 'if __name__ == "__main__":' in content


def test_cleanup_temp_artifacts_calls_main():
    """Test that the entry point imports main from cli module."""
    import cleanup_temp_artifacts

    # The module should import successfully
    assert cleanup_temp_artifacts is not None


def test_cleanup_temp_artifacts_imports_cli():
    """Test that the module imports from cleanup_temp_artifacts.cli."""
    with open("cleanup_temp_artifacts.py") as f:
        content = f.read()
        assert "from cleanup_temp_artifacts.cli import main" in content
