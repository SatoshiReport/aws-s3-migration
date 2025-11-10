"""
Configuration and path resolution for cleanup_temp_artifacts.

Handles default path determination and repository root location.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    import config as config_module  # type: ignore
except ImportError:  # pragma: no cover - best-effort fallback
    config_module = None


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).resolve().parent.parent


REPO_ROOT = get_repo_root()


def determine_default_base_path() -> Path | None:
    """Return the most likely local base path for migrated objects."""

    candidates: list[Path] = []
    if config_module and getattr(config_module, "LOCAL_BASE_PATH", None):
        candidates.append(Path(config_module.LOCAL_BASE_PATH).expanduser())
    for name in ("CLEANUP_TEMP_ROOT", "CLEANUP_ROOT"):
        if os.environ.get(name):
            candidates.append(Path(os.environ[name]).expanduser())
    candidates.extend(
        [
            Path("/Volumes/Extreme SSD/s3_backup"),
            Path("/Volumes/Extreme SSD"),
            Path.cwd(),
        ]
    )
    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def determine_default_db_path() -> Path:
    """Return the default SQLite DB path shared with migrate_v2."""

    if config_module and getattr(config_module, "STATE_DB_PATH", None):
        candidate = Path(config_module.STATE_DB_PATH)
    else:
        candidate = Path("s3_migration_state.db")
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    return candidate


DEFAULT_BASE_PATH = determine_default_base_path()
DEFAULT_DB_PATH = determine_default_db_path()
