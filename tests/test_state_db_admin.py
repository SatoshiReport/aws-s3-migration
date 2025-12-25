"""Tests for the shared state_db_admin helpers."""

from __future__ import annotations

import sqlite3

import pytest

from state_db_admin import reseed_state_db_from_local_drive


def test_reseed_state_db_populates_files(tmp_path):
    """Test reseed_state_db populates database from local directory."""
    base_path = tmp_path / "drive"
    bucket = base_path / "bucket-alpha"
    file_path = bucket / "folder" / "example.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("hello world")

    db_file, file_count, total_bytes = reseed_state_db_from_local_drive(base_path, tmp_path / "state.db")

    assert db_file.exists()
    assert file_count == 1
    assert total_bytes == len("hello world")
    conn = sqlite3.connect(db_file)
    try:
        row = conn.execute("SELECT bucket, key, size, state FROM files").fetchone()
        assert row == ("bucket-alpha", "folder/example.txt", len("hello world"), "synced")
    finally:
        conn.close()


def test_reseed_state_db_requires_base_path(tmp_path):
    """Test reseed_state_db raises FileNotFoundError when base path missing."""
    missing_path = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        reseed_state_db_from_local_drive(missing_path, tmp_path / "state.db")
