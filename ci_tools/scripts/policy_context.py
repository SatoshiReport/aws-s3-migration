"""Repository-aware shim for the shared policy_guard context."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict, Protocol, Sequence, cast


class CISharedRootNotConfiguredError(RuntimeError):
    """Raised when CI_SHARED_ROOT is not configured and cannot be found."""


_LOCAL_PATH = Path(__file__).resolve()
_REPO_ROOT = _LOCAL_PATH.parents[2]


def _load_ci_shared_root() -> Path:
    """Load CI_SHARED_ROOT from config file or environment variable."""
    config_file = _REPO_ROOT / "ci_shared_root.json"

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                ci_shared_root = config.get("ci_shared_root")
                if ci_shared_root:
                    return Path(ci_shared_root).expanduser().resolve()
        except (IOError, json.JSONDecodeError):
            pass

    env_root = os.environ.get("CI_SHARED_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    raise CISharedRootNotConfiguredError(
        f"CI_SHARED_ROOT not configured. "
        f"Create {config_file} with:\n"
        f'{{"ci_shared_root": "/path/to/ci_shared"}}\n'
        f"or set the CI_SHARED_ROOT environment variable."
    )


_ENV_SHARED_ROOT = _load_ci_shared_root()


def _candidate_context_paths() -> tuple[Path, ...]:
    """Return candidate paths for the shared policy_context module."""
    resolved = _ENV_SHARED_ROOT.expanduser().resolve()
    candidate = resolved / "ci_tools" / "scripts" / "policy_context.py"
    return (candidate,)


class _PolicyContextModule(Protocol):  # pylint: disable=too-few-public-methods
    ROOT: Path
    SCAN_DIRECTORIES: Sequence[Path]


class SharedPolicyContextError(RuntimeError):
    """Raised when the shared policy_context module cannot be loaded."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            f"Shared policy_context not found at {path}. Clone ci_shared or set CI_SHARED_ROOT."
        )


def _load_shared_context() -> ModuleType:
    """Load the canonical policy_context module from the shared repo."""
    for candidate in _candidate_context_paths():
        if candidate.exists():
            context_path = candidate
            break
    else:
        raise SharedPolicyContextError(_candidate_context_paths()[0])

    spec = importlib.util.spec_from_file_location("_ci_shared_policy_context", context_path)
    if spec is None or spec.loader is None:
        raise SharedPolicyContextError(context_path)

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def _determine_scan_dirs(repo_root: Path) -> tuple[Path, ...]:
    """Return the tuple of directories policy guard should scan."""
    candidates = []
    for path in (repo_root, repo_root / "tests"):
        if path.exists():
            candidates.append(path)
    if not candidates:
        candidates.append(repo_root)
    # Preserve order while removing duplicates.
    ordered: Dict[Path, None] = {}
    for path in candidates:
        ordered.setdefault(path, None)
    return tuple(ordered.keys())


_shared_context = cast(_PolicyContextModule, _load_shared_context())
_shared_context.ROOT = _REPO_ROOT
_shared_context.SCAN_DIRECTORIES = _determine_scan_dirs(_REPO_ROOT)

# Re-export the shared context symbols with our overrides applied.
for name, value in _shared_context.__dict__.items():
    if name.startswith("__") and name not in {"__all__", "__doc__"}:
        continue
    globals()[name] = value

ROOT = _shared_context.ROOT
SCAN_DIRECTORIES = _shared_context.SCAN_DIRECTORIES
