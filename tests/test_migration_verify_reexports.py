"""Tests ensuring the migration_verify shim is removed and fails fast."""

from __future__ import annotations

import importlib

import pytest


def test_migration_verify_shim_removed():
    """Importing the old shim should fail fast with guidance."""
    with pytest.raises(ImportError, match="shim removed"):
        importlib.import_module("migration_verify")
