"""Allow repository-specific overrides for ci_tools scripts."""

from __future__ import annotations

import os
from pathlib import Path
from pkgutil import extend_path


class CISharedRootNotConfiguredError(RuntimeError):
    """Raised when CI_SHARED_ROOT is not set and the shared scripts cannot be found."""


__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_CI_SHARED_ROOT_ENV = os.environ.get("CI_SHARED_ROOT")
if not _CI_SHARED_ROOT_ENV:
    raise CISharedRootNotConfiguredError(
        "CI_SHARED_ROOT environment variable is required. " "Set it to the path of your ci_shared repository clone."
    )

_shared_root = Path(_CI_SHARED_ROOT_ENV)
_shared_scripts = _shared_root / "ci_tools" / "scripts"
if _shared_scripts.exists():
    __path__.append(str(_shared_scripts))

# Note: policy_context is available via __path__ extension if needed
