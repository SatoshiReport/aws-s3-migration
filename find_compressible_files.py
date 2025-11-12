#!/usr/bin/env python3
"""CLI tool to locate and compress large locally downloaded objects."""
# ruff: noqa: TRY003 - CLI emits user-focused errors with contextual messages
# pylint: disable=line-too-long  # module docstrings and CLI messages prioritize clarity

from __future__ import annotations

import sys
from pathlib import Path

from find_compressible.cli import main

# Ensure the repository root is importable even when this script is run via an absolute path.
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:  # pragma: no cover - import context dependent
    sys.path.insert(0, str(REPO_ROOT))

if __name__ == "__main__":  # pragma: no cover - script entry point
    try:
        main()
    except KeyboardInterrupt as exc:
        raise SystemExit("\nAborted by user.") from exc
