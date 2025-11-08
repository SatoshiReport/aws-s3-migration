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


class SharedCiToolsPackageMissingError(ImportError):
    """Raised when the shared package __init__ is missing."""

    def __init__(self, shared_init: Path) -> None:
        super().__init__(
            f"Shared ci_tools package missing at {shared_init}. "
            "Clone ci_shared and/or set CI_SHARED_ROOT."
        )


class SharedCiToolsSpecError(ImportError):
    """Raised when importlib cannot create a module spec."""

    def __init__(self, shared_init: Path) -> None:
        super().__init__(f"Unable to create import spec for {shared_init}")


class SharedCiToolsDirectoryMissingError(ImportError):
    """Raised when the shared ci_tools directory is absent."""

    def __init__(self, shared_ci_tools: Path) -> None:
        super().__init__(
            f"Shared ci_tools directory not found at {shared_ci_tools}. "
            "Ensure ci_shared is cloned locally or set CI_SHARED_ROOT."
        )


_ORIGINAL_MODULE_NAME = __name__


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
        raise SharedCiToolsPackageMissingError(shared_init)

    spec = importlib.util.spec_from_file_location("_ci_shared_ci_tools", shared_init)
    if spec is None or spec.loader is None:
        raise SharedCiToolsSpecError(shared_init)

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def _bootstrap_shared_ci_tools() -> None:
    """Replace this shim module with the shared ci_tools implementation."""
    shared_root = _resolve_shared_root()
    shared_ci_tools = shared_root / "ci_tools"
    if not shared_ci_tools.exists():
        raise SharedCiToolsDirectoryMissingError(shared_ci_tools)

    shared_path = shared_ci_tools.as_posix()
    if shared_path not in sys.path:
        sys.path.insert(0, shared_path)

    shared_module = _load_shared_package(shared_ci_tools)
    local_ci_tools = Path(__file__).resolve().parent

    # Mirror key module attributes so downstream imports behave identically.
    globals().update(shared_module.__dict__)
    globals()["__file__"] = getattr(shared_module, "__file__", shared_path)

    shared_module_paths = [str(path) for path in getattr(shared_module, "__path__", [shared_path])]
    combined_paths: list[str] = []
    for candidate in [local_ci_tools.as_posix(), *shared_module_paths]:
        if candidate not in combined_paths:
            combined_paths.append(candidate)

    globals()["__path__"] = combined_paths
    globals()["__package__"] = _ORIGINAL_MODULE_NAME
    globals()["__name__"] = _ORIGINAL_MODULE_NAME


_bootstrap_shared_ci_tools()
