#!/usr/bin/env bash
# Usage: scripts/ci.sh ["Commit message"]
set -euo pipefail

SCRIPT_PATH=$(python - <<'PY'
import sys
from pathlib import Path

try:
    import ci_tools
except ImportError as exc:
    print("ci_tools package not installed; run `python -m pip install -e ../ci_shared`.", file=sys.stderr)
    raise SystemExit(1) from exc

path = Path(ci_tools.__file__).resolve().parent / "scripts" / "ci.sh"
print(path)
PY
)

exec "${SCRIPT_PATH}" "$@"
