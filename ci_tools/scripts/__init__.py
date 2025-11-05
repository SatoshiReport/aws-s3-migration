"""Allow repository-specific overrides for ci_tools scripts."""

from __future__ import annotations

import os
from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_shared_root = Path(os.environ.get("CI_SHARED_ROOT", Path.home() / "ci_shared"))
_shared_scripts = _shared_root / "ci_tools" / "scripts"
if _shared_scripts.exists():
    __path__.append(str(_shared_scripts))
