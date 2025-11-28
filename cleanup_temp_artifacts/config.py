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
    """Return the local base path for migrated objects.

    Raises:
        ConfigurationError: If no valid base path can be determined.
    """
    candidates: list[Path] = []

    local_base = getattr(config_module, "LOCAL_BASE_PATH", None) if config_module else None
    if local_base is not None:
        candidates.append(Path(local_base).expanduser())

    for name in ("CLEANUP_TEMP_ROOT", "CLEANUP_ROOT"):
        env_val = os.environ.get(name)
        if env_val:
            candidates.append(Path(env_val).expanduser())

    for candidate in dict.fromkeys(candidates):
        if candidate.exists():
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
    state_db = getattr(config_module, "STATE_DB_PATH", None)
    if not state_db:
        raise ConfigurationError("STATE_DB_PATH must be set in config.py")
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


# For backwards compatibility, these can be imported but will raise on access
# if configuration is missing. Tests that don't need these paths won't trigger errors.
class _LazyPath:
    """Lazy path accessor that defers configuration checks until first access."""

    def __init__(self, getter):
        self._getter = getter
        self._value: Path | None = None
        self._resolved = False

    def __fspath__(self):
        return str(self._resolve())

    def __str__(self):
        return str(self._resolve())

    def __repr__(self):
        if self._resolved:
            return repr(self._value)
        return f"<LazyPath: {self._getter.__name__}>"

    def _resolve(self) -> Path:
        if not self._resolved:
            self._value = self._getter()
            self._resolved = True
        # At this point _value is always a Path (getter returns Path)
        assert self._value is not None
        return self._value

    def __truediv__(self, other):
        return self._resolve() / other

    def __eq__(self, other):
        return self._resolve() == other

    def __hash__(self):
        return hash(self._resolve())

    @property
    def parent(self):
        """Return the parent directory of the resolved path."""
        return self._resolve().parent

    def exists(self):
        """Check if the resolved path exists on disk."""
        return self._resolve().exists()

    def resolve(self):
        """Return the absolute resolved path."""
        return self._resolve().resolve()


DEFAULT_BASE_PATH = _LazyPath(_get_default_base_path)
DEFAULT_DB_PATH = _LazyPath(_get_default_db_path)
