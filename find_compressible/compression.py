"""Compression operations using built-in lzma (XZ) support."""

from __future__ import annotations

import lzma
from pathlib import Path


def compress_with_xz(path: Path) -> Path:
    """Compress `path` using XZ with a high compression preset."""
    target = Path(str(path) + ".xz")
    try:
        with path.open("rb") as src, lzma.open(target, "wb", preset=9) as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                dst.write(chunk)
    except FileNotFoundError as exc:
        raise SystemExit("Source file not found for compression.") from exc
    return target


def verify_compressed_file(path: Path) -> None:
    """Verify the compressed output by attempting to decompress it."""
    try:
        with lzma.open(path, "rb") as src:
            for _ in iter(lambda: src.read(1024 * 1024), b""):
                continue
    except FileNotFoundError as exc:  # pragma: no cover - path missing
        raise SystemExit("Compressed file not found for verification.") from exc
    except lzma.LZMAError as exc:
        raise RuntimeError(f"XZ verification failed for {path}: {exc}") from exc
