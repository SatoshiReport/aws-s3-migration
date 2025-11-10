"""Compression operations using xz."""

# ruff: noqa: TRY003 - CLI emits user-focused errors with contextual messages

from __future__ import annotations

import subprocess
from pathlib import Path


def compress_with_xz(path: Path) -> Path:
    """Compress `path` using xz -9e while keeping the original for verification."""
    cmd = ["xz", "--keep", "-9e", str(path)]
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("xz binary not found. Install xz-utils to enable compression.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"xz failed for {path} (exit {exc.returncode}). stderr: {exc.stderr.strip()}"
        ) from exc
    return Path(str(path) + ".xz")


def verify_compressed_file(path: Path) -> None:
    """Run `xz -t` to verify the compressed output."""
    cmd = ["xz", "-t", str(path)]
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - same binary as compress
        raise SystemExit("xz binary not found. Install xz-utils to enable compression.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"xz verification failed for {path} (exit {exc.returncode}). "
            f"stderr: {exc.stderr.strip()}"
        ) from exc
