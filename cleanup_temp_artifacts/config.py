"""
Configuration and path resolution for cleanup_temp_artifacts.

Handles default path determination and repository root location.
"""

from __future__ import annotations

import os
from pathlib import Path

import config as config_module


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing."""


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).resolve().parent.parent


REPO_ROOT = get_repo_root()


def _load_env_base_paths() -> list[Path]:
    """Collect base path candidates from supported environment variables."""
    paths: list[Path] = []
    for name in ("CLEANUP_TEMP_ROOT", "CLEANUP_ROOT"):
        env_val = os.environ.get(name)
        if env_val:
            paths.append(Path(env_val).expanduser())
    return paths


def _load_config_module_path() -> Path | None:
    """Return the base path configured in config.py if present."""
    local_base_path = getattr(config_module, "LOCAL_BASE_PATH", None)
    if local_base_path is None:
        return None
    return Path(local_base_path).expanduser()


def determine_default_base_path() -> Path:
    """Return the local base path for migrated objects."""
    candidates: list[Path] = _load_env_base_paths()

    module_path = _load_config_module_path()
    if module_path is not None:
        candidates.append(module_path)

    if not candidates:
        raise ConfigurationError(
            "No valid base path found. Set LOCAL_BASE_PATH in config.py or CLEANUP_TEMP_ROOT/CLEANUP_ROOT environment variable."
        )

    for candidate in dict.fromkeys(candidates):
        if candidate.exists():
            return candidate

    raise ConfigurationError(
        "No valid base path found. Set LOCAL_BASE_PATH in config.py or CLEANUP_TEMP_ROOT/CLEANUP_ROOT environment variable."
    )


def determine_default_db_path() -> Path:
    """Return the default SQLite DB path shared with migrate_v2.

    Raises:
        ConfigurationError: If STATE_DB_PATH is not configured.
    """
    state_db = getattr(config_module, "STATE_DB_PATH", None)
    if state_db is None:
        raise ConfigurationError("STATE_DB_PATH must be set in config.py")
    candidate = Path(state_db)
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    return candidate


def _get_default_base_path() -> Path:
    """Lazily retrieve default base path."""
    try:
        return determine_default_base_path()
    except ConfigurationError:
        return Path("/tmp/cleanup_base")


def _get_default_db_path() -> Path:
    """Lazily retrieve default DB path."""
    try:
        return determine_default_db_path()
    except ConfigurationError:
        return Path("/tmp/cleanup_state.db")


DEFAULT_BASE_PATH = _get_default_base_path()
DEFAULT_DB_PATH = _get_default_db_path()
