#!/usr/bin/env bash
# Usage: scripts/ci.sh ["Commit message"]
set -euo pipefail

CI_SHARED_ROOT="${CI_SHARED_ROOT:-${HOME}/ci_shared}"
SHARED_SCRIPT="${CI_SHARED_ROOT}/ci_tools/scripts/ci.sh"

if [[ ! -x "${SHARED_SCRIPT}" ]]; then
  echo "Shared CI runner not found at ${SHARED_SCRIPT}." >&2
  echo "Set CI_SHARED_ROOT or clone ci_shared to ${HOME}/ci_shared." >&2
  exit 1
fi

export PYTHONPATH="${CI_SHARED_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

exec "${SHARED_SCRIPT}" "$@"
