"""Cache management for migration state database."""

# ruff: noqa: TRY003 - CLI emits user-focused errors with contextual messages

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repository root is importable for state_db_admin import.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from cost_toolkit.common.cli_utils import handle_state_db_reset
    from state_db_admin import reseed_state_db_from_local_drive
except ImportError as exc:  # pragma: no cover - failure is fatal for this CLI
    raise SystemExit(f"Unable to import state_db_admin module: {exc}") from exc
