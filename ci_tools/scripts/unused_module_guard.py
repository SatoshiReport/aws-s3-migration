"""Repository-aware shim for the shared unused_module_guard script."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
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

    def main(self) -> int:  # pragma: no cover - type hints only
        """Execute the guard CLI."""
        raise NotImplementedError


def _load_shared_guard() -> GuardModule:
    """Load the canonical unused_module_guard implementation."""
    shared_root = Path(os.environ.get("CI_SHARED_ROOT", Path.home() / "ci_shared"))
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


def _load_config() -> tuple[list[str], list[str]]:
    """Load repo-specific config providing excludes and allow-lists."""
    if not _CONFIG_FILE.exists():
        return [], []

    try:
        data = json.loads(_CONFIG_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return [], []

    excludes = [str(pattern) for pattern in data.get("exclude_patterns", [])]
    allow_list = [str(pattern) for pattern in data.get("suspicious_allow_patterns", [])]
    return excludes, allow_list


def _apply_config_overrides(
    guard: GuardModule,
    extra_excludes: Sequence[str],
    allowed_patterns: Sequence[str],
) -> None:
    """Patch the shared guard module with repo-specific behavior."""
    if allowed_patterns:
        guard.SUSPICIOUS_PATTERNS = tuple(
            pattern for pattern in guard.SUSPICIOUS_PATTERNS if pattern not in allowed_patterns
        )

    if extra_excludes:
        original_find_unused = guard.find_unused_modules

        def find_unused_with_config(root, exclude_patterns=None):
            combined = list(exclude_patterns or [])
            combined.extend(extra_excludes)
            return original_find_unused(root, exclude_patterns=combined)

        guard.find_unused_modules = find_unused_with_config  # type: ignore[assignment]


def _bootstrap() -> Callable[[], int]:
    """Load shared module, apply overrides, and mirror its namespace."""
    guard = _load_shared_guard()
    extra_excludes, allowed_patterns = _load_config()
    _apply_config_overrides(guard, extra_excludes, allowed_patterns)

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


if __name__ == "__main__":
    sys.exit(main())
