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


class SharedCiToolsError(ImportError):
    """Base exception for shared ci_tools bootstrap failures."""


class SharedCiToolsPackageMissingError(SharedCiToolsError):
    """Raised when the shared package cannot be located."""

    def __init__(self, path: Path) -> None:
        message = (
            f"Shared ci_tools package missing at {path}. "
            "Clone ci_shared and/or set CI_SHARED_ROOT."
        )
        super().__init__(message)


class SharedCiToolsSpecError(SharedCiToolsError):
    """Raised when the shared package cannot create an import spec."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"Unable to create import spec for {path}")


class SharedCiToolsDirectoryMissingError(SharedCiToolsError):
    """Raised when the shared ci_tools directory is missing."""

    def __init__(self, path: Path) -> None:
        message = (
            f"Shared ci_tools directory not found at {path}. "
            "Ensure ci_shared is cloned locally or set CI_SHARED_ROOT."
        )
        super().__init__(message)


_THIS_MODULE = sys.modules[__name__]
_LOCAL_REPO_ROOT = Path(__file__).resolve().parent


def _load_local_scripts_package() -> None:
    """Ensure the repo-local ci_tools.scripts package is imported."""
    local_scripts = _LOCAL_REPO_ROOT / "scripts"
    init_file = local_scripts / "__init__.py"
    if not init_file.exists():
        return

    spec = importlib.util.spec_from_file_location(
        "ci_tools.scripts",
        init_file,
        submodule_search_locations=[str(local_scripts)],
    )
    if spec is None or spec.loader is None:
        return

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]


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

    spec = importlib.util.spec_from_file_location("ci_tools", shared_init)
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

    local_package_path = Path(__file__).resolve().parent.as_posix()
    shared_paths = list(getattr(shared_module, "__path__", [shared_path]))
    merged_path: list[str] = []
    for candidate in [local_package_path, *shared_paths]:
        if candidate not in merged_path:
            merged_path.append(candidate)

    globals().update(shared_module.__dict__)
    globals()["__file__"] = getattr(shared_module, "__file__", shared_path)
    globals()["__path__"] = merged_path
    globals()["__package__"] = shared_module.__package__
    spec = getattr(shared_module, "__spec__", None)
    if spec is not None:
        spec.submodule_search_locations = merged_path
    globals()["__spec__"] = spec
    sys.modules[__name__] = _THIS_MODULE
    _load_local_scripts_package()


_bootstrap_shared_ci_tools()
