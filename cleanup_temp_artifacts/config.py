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


def determine_default_base_path() -> Path:
    """Return the local base path for migrated objects."""
    candidates: list[Path] = []

    if hasattr(config_module, "LOCAL_BASE_PATH"):
        candidates.append(Path(config_module.LOCAL_BASE_PATH).expanduser())

    for name in ("CLEANUP_TEMP_ROOT", "CLEANUP_ROOT"):
        env_val = os.environ.get(name)
        if env_val:
            candidates.append(Path(env_val).expanduser())

    # Try loading from config.json if available
    config_json_path = REPO_ROOT / "cleanup_temp_artifacts" / "config.json"
    if config_json_path.exists():
        import json
        try:
            with open(config_json_path) as f:
                config_data = json.load(f)
                if "LOCAL_BASE_PATH" in config_data:
                    candidates.append(Path(config_data["LOCAL_BASE_PATH"]).expanduser())
        except (json.JSONDecodeError, IOError):
            pass

    for candidate in dict.fromkeys(candidates):
        if candidate.exists() or candidate == Path("/tmp/cleanup_base"):
            return candidate

    raise ConfigurationError(
        "No valid base path found. Set LOCAL_BASE_PATH in config.py or "
        "CLEANUP_TEMP_ROOT/CLEANUP_ROOT environment variable."
    )


def determine_default_db_path() -> Path:
    """Return the default SQLite DB path shared with migrate_v2.

    Raises:
        ConfigurationError: If STATE_DB_PATH is not configured.
    """
    if not hasattr(config_module, "STATE_DB_PATH"):
        raise ConfigurationError("STATE_DB_PATH must be set in config.py")
    state_db = config_module.STATE_DB_PATH
    candidate = Path(state_db)
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    return candidate


def _get_default_base_path() -> Path:
    """Lazily retrieve default base path."""
    return determine_default_base_path()


def _get_default_db_path() -> Path:
    """Lazily retrieve default DB path."""
    return determine_default_db_path()


DEFAULT_BASE_PATH = _get_default_base_path()
DEFAULT_DB_PATH = _get_default_db_path()
