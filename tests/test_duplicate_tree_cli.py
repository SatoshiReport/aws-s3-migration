"""Tests for the duplicate_tree_cli helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import duplicate_tree_cli as cli


def _write_sample_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE files (
            bucket TEXT NOT NULL,
            key TEXT NOT NULL,
            size INTEGER NOT NULL,
            local_checksum TEXT,
            etag TEXT
        )
        """
    )
    rows = [
        ("bucket", "dirA/file1.txt", 100, "aaa", None),
        ("bucket", "dirA/sub/file2.txt", 200, "bbb", None),
        ("bucket", "dirB/file1.txt", 100, "aaa", None),
        ("bucket", "dirB/sub/file2.txt", 200, "bbb", None),
    ]
    conn.executemany(
        "INSERT INTO files (bucket, key, size, local_checksum, etag) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db_path


def test_build_directory_index_from_db(tmp_path):
    db_path = _write_sample_db(tmp_path)
    index, fingerprint = cli.build_directory_index_from_db(str(db_path))
    assert fingerprint.total_files == 4
    assert len(index.nodes) >= 2


def test_cache_round_trip(tmp_path):
    db_path = tmp_path / "cache.db"
    fingerprint = cli.ScanFingerprint(total_files=4, checksum="abc123")
    cli.store_cached_report(
        str(db_path),
        fingerprint,
        tolerance=0.99,
        base_path="/drive",
        report_text="cached report",
    )
    cached = cli.load_cached_report(str(db_path), fingerprint, 0.99, "/drive")
    assert cached is not None
    assert "cached report" in cached["report"]


def test_cli_main_end_to_end(tmp_path, capsys):
    db_path = _write_sample_db(tmp_path)
    base_path = tmp_path / "drive"
    base_path.mkdir()
    exit_code = cli.main(
        [
            "--db-path",
            str(db_path),
            "--base-path",
            str(base_path),
            "--refresh-cache",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "EXACT DUPLICATE TREES" in captured
    assert (
        "NEAR DUPLICATES" in captured
        or "No near-duplicate directories within tolerance." in captured
    )

    exit_code_cached = cli.main(
        [
            "--db-path",
            str(db_path),
            "--base-path",
            str(base_path),
        ]
    )
    cached_output = capsys.readouterr().out
    assert exit_code_cached == 0
    assert "cached duplicate analysis" in cached_output
