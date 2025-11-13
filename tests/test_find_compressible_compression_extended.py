"""Extended tests for find_compressible/compression.py to increase coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from find_compressible.compression import compress_with_xz, verify_compressed_file


def test_compress_with_xz_success(tmp_path):
    """Test compress_with_xz successfully compresses a file."""
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"test data" * 1000)

    compressed_file = compress_with_xz(test_file)

    assert compressed_file.exists()
    assert compressed_file.name == "test.txt.xz"
    assert test_file.exists()  # Original should still exist (--keep flag)


def test_compress_with_xz_subprocess_error(tmp_path):
    """Test compress_with_xz handles subprocess errors."""
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"test data")

    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "Error message"

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        with pytest.raises(SystemExit, match="xz binary not found"):
            compress_with_xz(test_file)


def test_compress_with_xz_called_process_error(tmp_path):
    """Test compress_with_xz handles CalledProcessError."""
    import subprocess

    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"test data")

    mock_error = subprocess.CalledProcessError(1, "xz", stderr="Error")
    with patch("subprocess.run", side_effect=mock_error):
        with pytest.raises(RuntimeError, match="xz failed"):
            compress_with_xz(test_file)


def test_verify_compressed_file_success(tmp_path):
    """Test verify_compressed_file successfully verifies a file."""
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"test data" * 1000)

    compressed_file = compress_with_xz(test_file)
    verify_compressed_file(compressed_file)  # Should not raise


def test_verify_compressed_file_subprocess_error(tmp_path):
    """Test verify_compressed_file handles CalledProcessError."""
    import subprocess

    test_file = tmp_path / "test.txt.xz"
    test_file.write_bytes(b"invalid xz data")

    mock_error = subprocess.CalledProcessError(1, "xz", stderr="Verification error")
    with patch("subprocess.run", side_effect=mock_error):
        with pytest.raises(RuntimeError, match="xz verification failed"):
            verify_compressed_file(test_file)
