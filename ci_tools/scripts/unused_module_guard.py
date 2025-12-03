# pylint: disable=duplicate-code,R0801
"""Repository-aware shim for the shared unused_module_guard script."""

# The import fallback pattern matches numerous migration scripts that must remain
# consistent for tooling, so suppress duplicate-code for this shim.

from __future__ import annotations

import importlib.util
import json
import os
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, Protocol, Sequence, cast


class SharedGuardMissingError(ImportError):
    """Raised when the shared unused_module_guard.py file cannot be located."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            f"Shared unused_module_guard not found at {path}. "
            "Clone ci_shared or set CI_SHARED_ROOT."
        )


class SharedGuardSpecError(ImportError):
    """Raised when the loader spec for the shared guard cannot be created."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"Unable to create spec for {path}")


class SharedGuardInitializationError(RuntimeError):
    """Raised when the shared guard's main entry point cannot be delegated."""

    def __init__(self) -> None:
        super().__init__("shared unused_module_guard failed to initialize")


_LOCAL_MODULE_PATH = Path(__file__).resolve()
_ORIGINAL_MODULE_NAME = __name__
_REPO_ROOT = _LOCAL_MODULE_PATH.parents[2]
_CONFIG_FILE = _REPO_ROOT / "unused_module_guard.config.json"
_DELEGATED_MAIN: Callable[[], int] | None = None


class GuardModule(Protocol):
    """Structural type for the shared unused_module_guard module."""

    SUSPICIOUS_PATTERNS: tuple[str, ...]

    def find_unused_modules(  # pragma: no cover - type hints only
        self, root, exclude_patterns=None
    ):
        """Return unused module metadata."""
        raise NotImplementedError

    def find_suspicious_duplicates(self, root):  # pragma: no cover - type hints only
        """Return suspicious duplicate metadata."""
        raise NotImplementedError

    def main(self) -> int:  # pragma: no cover - type hints only
        """Execute the guard CLI."""
        raise NotImplementedError


class CISharedRootNotConfiguredError(RuntimeError):
    """Raised when CI_SHARED_ROOT is not set."""


def _load_shared_guard() -> GuardModule:
    """Load the canonical unused_module_guard implementation."""
    ci_shared_root_env = os.environ.get("CI_SHARED_ROOT")
    shared_root = Path(ci_shared_root_env) if ci_shared_root_env else Path.home() / "ci_shared"

    shared_guard = shared_root / "ci_tools" / "scripts" / "unused_module_guard.py"
    if not shared_guard.exists():
        raise SharedGuardMissingError(shared_guard)

    spec = importlib.util.spec_from_file_location("_ci_shared_unused_module_guard", shared_guard)
    if spec is None or spec.loader is None:
        raise SharedGuardSpecError(shared_guard)

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return cast(GuardModule, module)


def _load_config() -> tuple[list[str], list[str], list[str]]:
    """Load repo-specific config providing excludes and allow-lists.

    Returns empty lists for each config key if the config file does not exist.
    """
    if not _CONFIG_FILE.exists():
        return [], [], []

    try:
        raw = _CONFIG_FILE.read_text()
    except OSError as exc:
        print(
            f"⚠️  Unable to read unused_module_guard config {_CONFIG_FILE}: {exc}", file=sys.stderr
        )
        return [], [], []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"⚠️  Invalid JSON in {_CONFIG_FILE}: {exc}", file=sys.stderr)
        return [], [], []

    excludes = [str(pattern) for pattern in data.get("exclude_patterns", [])]
    allow_list = [str(pattern) for pattern in data.get("suspicious_allow_patterns", [])]
    duplicate_excludes = [str(pattern) for pattern in data.get("duplicate_exclude_patterns", [])]
    return excludes, allow_list, duplicate_excludes


def _matches_duplicate_exclude(file_path: object, patterns: Sequence[str]) -> bool:
    """Return True when the given path should be filtered from duplicate results."""
    file_str = str(file_path)
    basename = Path(file_str).name
    for pattern in patterns:
        normalized = str(pattern)
        if not normalized:
            continue
        if normalized in file_str or normalized in basename:
            return True
        if fnmatch(file_str, normalized) or fnmatch(basename, normalized):
            return True
    return False


def _update_suspicious_patterns(guard: GuardModule, allowed_patterns: Sequence[str]) -> None:
    if not allowed_patterns:
        return
    suspicious_patterns = getattr(guard, "SUSPICIOUS_PATTERNS", None)
    if suspicious_patterns is None:
        print(
            "⚠️  Shared unused_module_guard missing SUSPICIOUS_PATTERNS; "
            "allowed_patterns override skipped.",
            file=sys.stderr,
        )
        guard.SUSPICIOUS_PATTERNS = tuple()
        return
    guard.SUSPICIOUS_PATTERNS = tuple(
        pattern for pattern in suspicious_patterns if pattern not in allowed_patterns
    )


def _wrap_find_unused(guard: GuardModule, extra_excludes: Sequence[str]) -> None:
    if not extra_excludes:
        return
    original_find_unused = guard.find_unused_modules

    def find_unused_with_config(root, exclude_patterns=None):
        combined = list(exclude_patterns or [])
        combined.extend(extra_excludes)
        result = original_find_unused(root, exclude_patterns=combined)
        if hasattr(guard, "LAST_EXCLUDES"):
            guard.LAST_EXCLUDES = combined  # type: ignore[attr-defined]
        return result

    guard.find_unused_modules = find_unused_with_config  # type: ignore[assignment]


def _wrap_duplicate_detection(
    guard: GuardModule, extra_excludes: Sequence[str], duplicate_excludes: Sequence[str]
) -> None:
    combined_duplicate_excludes = list(
        dict.fromkeys([p for p in [*extra_excludes, *duplicate_excludes, "tests/"] if p])
    )
    if not combined_duplicate_excludes:
        return
    original_find_duplicates = getattr(guard, "find_suspicious_duplicates", None)
    if original_find_duplicates is None:
        return

    def find_duplicates_with_config(root):
        results = original_find_duplicates(root)
        return [
            (file_path, reason)
            for file_path, reason in results
            if not _matches_duplicate_exclude(file_path, combined_duplicate_excludes)
        ]

    # type: ignore[assignment]
    guard.find_suspicious_duplicates = find_duplicates_with_config


def _apply_config_overrides(
    guard: GuardModule,
    extra_excludes: Sequence[str],
    allowed_patterns: Sequence[str],
    duplicate_excludes: Sequence[str],
) -> None:
    """Patch the shared guard module with repo-specific behavior."""
    _update_suspicious_patterns(guard, allowed_patterns)
    _wrap_find_unused(guard, extra_excludes)
    _wrap_duplicate_detection(guard, extra_excludes, duplicate_excludes)


def _bootstrap() -> Callable[[], int]:
    """Load shared module, apply overrides, and mirror its namespace."""
    guard = _load_shared_guard()
    extra_excludes, allowed_patterns, duplicate_excludes = _load_config()
    _apply_config_overrides(guard, extra_excludes, allowed_patterns, duplicate_excludes)
    globals()["CONFIG_OVERRIDES"] = (
        tuple(extra_excludes),
        tuple(allowed_patterns),
        tuple(duplicate_excludes),
    )

    globals().update(guard.__dict__)
    globals()["__file__"] = str(_LOCAL_MODULE_PATH)
    globals()["__name__"] = _ORIGINAL_MODULE_NAME
    return guard.main


def main() -> int:
    """Delegate to the shared guard's main entrypoint."""
    if _DELEGATED_MAIN is None:
        raise SharedGuardInitializationError()
    return _DELEGATED_MAIN()


_DELEGATED_MAIN = _bootstrap()
globals()["main"] = main


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
