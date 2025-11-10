"""CLI workflow for duplicate tree analysis.

This module serves as a compatibility wrapper around the duplicate_tree package.
All functionality has been refactored into modular components:
  - duplicate_tree.analysis: Duplicate detection and clustering logic
  - duplicate_tree.cache: Cache management for analysis results
  - duplicate_tree.deletion: Directory deletion operations
  - duplicate_tree.cli: Command-line interface and main entry point
"""

from __future__ import annotations

import sys

try:  # Prefer package-relative imports when packaged
    from .duplicate_tree.cli import main
except ImportError:  # pragma: no cover - execution as standalone script
    from duplicate_tree.cli import main  # type: ignore


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except KeyboardInterrupt as exc:
        print("\n✗ Duplicate tree analysis interrupted by user.", file=sys.stderr)
        raise SystemExit(130) from exc
