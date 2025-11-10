#!/usr/bin/env python3
"""
Scan backup trees for disposable cache/temp artifacts and optionally delete them.

The script focuses on developer tooling residue (Python caches, VS Code remote
downloads, language package caches, etc.) and intentionally ignores macOS system
metadata (.Spotlight-V100, .DS_Store, ...).

This is a thin wrapper around the cleanup_temp_artifacts package.
"""
from __future__ import annotations

from cleanup_temp_artifacts.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
