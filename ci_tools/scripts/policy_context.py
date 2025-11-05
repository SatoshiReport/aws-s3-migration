"""Repository-aware shim for the shared policy_guard context."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict

_LOCAL_PATH = Path(__file__).resolve()
_REPO_ROOT = _LOCAL_PATH.parents[2]
_SHARED_ROOT = Path(os.environ.get("CI_SHARED_ROOT", Path.home() / "ci_shared"))
_SHARED_CONTEXT_PATH = _SHARED_ROOT / "ci_tools" / "scripts" / "policy_context.py"


class SharedPolicyContextError(RuntimeError):
    """Raised when the shared policy_context module cannot be loaded."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            f"Shared policy_context not found at {path}. "
            "Clone ci_shared or set CI_SHARED_ROOT."
        )


def _load_shared_context() -> ModuleType:
    """Load the canonical policy_context module from the shared repo."""
    if not _SHARED_CONTEXT_PATH.exists():
        raise SharedPolicyContextError(_SHARED_CONTEXT_PATH)

    spec = importlib.util.spec_from_file_location(
        "_ci_shared_policy_context", _SHARED_CONTEXT_PATH
    )
    if spec is None or spec.loader is None:
        raise SharedPolicyContextError(_SHARED_CONTEXT_PATH)

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


_shared_context = _load_shared_context()
_shared_context.ROOT = _REPO_ROOT
_shared_context.SCAN_DIRECTORIES = _determine_scan_dirs(_REPO_ROOT)

# Re-export the shared context symbols with our overrides applied.
for name, value in _shared_context.__dict__.items():
    if name.startswith("__") and name not in {"__all__", "__doc__"}:
        continue
    globals()[name] = value

ROOT = _shared_context.ROOT
SCAN_DIRECTORIES = _shared_context.SCAN_DIRECTORIES
