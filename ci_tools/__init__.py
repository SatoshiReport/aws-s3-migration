"""Namespace shim that prepends the shared ``ci_tools`` checkout."""

from __future__ import annotations

import os
from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_SHARED_ROOT = Path(os.environ.get("CI_SHARED_ROOT", Path.home() / "ci_shared"))
_SHARED_PACKAGE = _SHARED_ROOT / "ci_tools"
if _SHARED_PACKAGE.exists():
    __path__.append(str(_SHARED_PACKAGE))
