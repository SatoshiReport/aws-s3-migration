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
    from cost_toolkit.common.cli_utils import confirm_reset_state_db
    from state_db_admin import reseed_state_db_from_local_drive
except ImportError as exc:  # pragma: no cover - failure is fatal for this CLI
    raise SystemExit(f"Unable to import state_db_admin module: {exc}") from exc


BYTES_PER_UNIT = 1024


def format_size(num: int) -> str:
    """Return a human-friendly size string."""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if num < BYTES_PER_UNIT or unit == "TiB":
            return f"{num:,.2f} {unit}"
        num /= BYTES_PER_UNIT
    return f"{num:,.2f} PiB"


def _confirm_state_db_reset(db_path: Path, skip_prompt: bool) -> bool:
    """Prompt user to confirm state DB reset unless skip_prompt is True."""
    return confirm_reset_state_db(str(db_path), skip_prompt)


def handle_state_db_reset(
    base_path: Path, db_path: Path, should_reset: bool, skip_prompt: bool
) -> Path:
    """Reset state DB if requested and confirmed."""
    if not should_reset:
        return db_path
    if not _confirm_state_db_reset(db_path, skip_prompt):
        print("State database reset cancelled; continuing without reset.")
        return db_path
    db_path, file_count, total_bytes = reseed_state_db_from_local_drive(base_path, db_path)
    print(
        f"✓ Recreated migrate_v2 state database at {db_path} "
        f"({file_count:,} files, {format_size(total_bytes)}). Continuing."
    )
    return db_path
