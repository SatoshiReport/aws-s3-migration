"""Tests for find_compressible/compression.py module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from find_compressible.compression import compress_with_xz, verify_compressed_file


def test_compress_with_xz_success(tmp_path):
    """Test compress_with_xz with successful compression."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content for compression")

    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        compressed_path = compress_with_xz(test_file)

    assert compressed_path == Path(str(test_file) + ".xz")


def test_compress_with_xz_failure(tmp_path):
    """Test compress_with_xz with compression failure."""
    import subprocess  # pylint: disable=import-outside-toplevel

    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    # CalledProcessError is raised when check=True and command fails
    error = subprocess.CalledProcessError(1, ["xz"], stderr="compression error")

    with patch("subprocess.run", side_effect=error):
        with pytest.raises(RuntimeError) as exc_info:
            compress_with_xz(test_file)

    assert "xz" in str(exc_info.value).lower()


def test_verify_compressed_file_success(tmp_path):
    """Test verify_compressed_file with valid compressed file."""
    compressed_file = tmp_path / "test.txt.xz"
    compressed_file.write_bytes(b"fake xz content")

    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        verify_compressed_file(compressed_file)  # Should not raise


def test_verify_compressed_file_failure(tmp_path):
    """Test verify_compressed_file with invalid compressed file."""
    import subprocess  # pylint: disable=import-outside-toplevel

    compressed_file = tmp_path / "test.txt.xz"
    compressed_file.write_bytes(b"invalid xz content")

    # CalledProcessError is raised when check=True and command fails
    error = subprocess.CalledProcessError(1, ["xz", "-t"], stderr="verification error")

    with patch("subprocess.run", side_effect=error):
        with pytest.raises(RuntimeError) as exc_info:
            verify_compressed_file(compressed_file)

    assert "xz" in str(exc_info.value).lower()
