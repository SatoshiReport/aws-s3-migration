"""Tests for find_compressible/compression.py module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from find_compressible.compression import compress_with_xz, verify_compressed_file


def test_compress_with_xz_success(tmp_path):
    """Test compress_with_xz with successful compression."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content for compression")

    compressed_path = compress_with_xz(test_file)

    assert compressed_path == Path(str(test_file) + ".xz")
    assert compressed_path.exists()


def test_compress_with_xz_failure(tmp_path):
    """Test compress_with_xz with compression failure."""
    with pytest.raises(SystemExit):
        compress_with_xz(Path("nonexistent.txt"))


def test_verify_compressed_file_success(tmp_path):
    """Test verify_compressed_file with valid compressed file."""
    original = tmp_path / "data.bin"
    original.write_bytes(b"a" * 1024)
    compressed_file = compress_with_xz(original)

    verify_compressed_file(compressed_file)  # Should not raise


def test_verify_compressed_file_failure(tmp_path):
    """Test verify_compressed_file with invalid compressed file."""
    compressed_file = tmp_path / "test.txt.xz"
    compressed_file.write_bytes(b"invalid xz content")

    with pytest.raises(RuntimeError):
        verify_compressed_file(compressed_file)
