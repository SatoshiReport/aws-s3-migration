"""Proxy package that redirects all ``ci_tools`` imports to the shared checkout.

Consuming repositories should *not* maintain their own copies of the guard
scripts. Instead, they depend on this shim to locate ``~/ci_shared`` (or an
override specified via ``CI_SHARED_ROOT``) and execute the canonical package
from there.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

_LOCAL_PACKAGE_DIR = Path(__file__).resolve().parent


class SharedCiToolsError(ImportError):
    """Base error raised when the shared ci_tools checkout is unavailable."""


class SharedPackageMissingError(SharedCiToolsError):
    """Raised when __init__.py is missing from the shared checkout."""

    def __init__(self, shared_init: Path) -> None:
        super().__init__(
            f"Shared ci_tools package missing at {shared_init}. "
            "Clone ci_shared and/or set CI_SHARED_ROOT."
        )


class SharedSpecCreationError(SharedCiToolsError):
    """Raised when importlib cannot build a spec for the shared package."""

    def __init__(self, shared_init: Path) -> None:
        super().__init__(f"Unable to create import spec for {shared_init}")


class SharedDirectoryMissingError(SharedCiToolsError):
    """Raised when the shared ci_tools directory itself is absent."""

    def __init__(self, shared_path: Path) -> None:
        super().__init__(
            f"Shared ci_tools directory not found at {shared_path}. "
            "Ensure ci_shared is cloned locally or set CI_SHARED_ROOT."
        )


def _resolve_shared_root() -> Path:
    """Return the path to the shared ci_shared checkout."""
    env_override = os.environ.get("CI_SHARED_ROOT")
    if env_override:
        return Path(env_override).expanduser().resolve()
    return (Path.home() / "ci_shared").resolve()


def _load_shared_package(shared_ci_tools: Path) -> ModuleType:
    """Load ci_tools from the canonical shared checkout."""
    shared_init = shared_ci_tools / "__init__.py"
    if not shared_init.exists():
        raise SharedPackageMissingError(shared_init)

    spec = importlib.util.spec_from_file_location("_ci_shared_ci_tools", shared_init)
    if spec is None or spec.loader is None:
        raise SharedSpecCreationError(shared_init)

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def _bootstrap_shared_ci_tools() -> None:
    """Replace this shim module with the shared ci_tools implementation."""
    shared_root = _resolve_shared_root()
    shared_ci_tools = shared_root / "ci_tools"
    if not shared_ci_tools.exists():
        raise SharedDirectoryMissingError(shared_ci_tools)

    shared_path = shared_ci_tools.as_posix()
    if shared_path not in sys.path:
        sys.path.insert(0, shared_path)

    shared_module = _load_shared_package(shared_ci_tools)

    # Mirror key module attributes so downstream imports behave identically.
    globals().update(shared_module.__dict__)
    globals()["__file__"] = getattr(shared_module, "__file__", shared_path)
    local_path_str = _LOCAL_PACKAGE_DIR.as_posix()
    shared_paths = list(getattr(shared_module, "__path__", [shared_path]))
    if local_path_str not in shared_paths:
        shared_paths.insert(0, local_path_str)
    globals()["__path__"] = shared_paths
    globals()["__package__"] = shared_module.__package__


_bootstrap_shared_ci_tools()
