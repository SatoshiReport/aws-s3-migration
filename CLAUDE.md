# CLAUDE Automation Guide

Claude Code follows the same safety rules as `AGENTS.md`, with a few tool-specific reminders up front.

## Claude Mission Checklist

1. **Load repo context.** Review `AGENTS.md`, `docs/README.md`, and any task-specific doc before proposing edits. Skim the module plus helpers it touches.
2. **Stay surgical.** Use `apply_patch` for focused diffs, avoid bulk rewrites, and never revert user edits you did not make.
3. **Validate early.** Run the fastest relevant formatter/linter/test slice so CI is a formality.

```bash
# Claude-friendly pre-flight
set -euo pipefail
git status -sb
python -m pip install -e . >/dev/null
make check
```

## Repo Primer for Claude

- **migrate_v2.py / migration_state_v2.py**: Treat as public API. Every change needs regression tests under `tests/` plus doc updates.
- **Policy CLIs (`aws_info.py`, `block_s3.py`, `apply_block.py`)**: Never hardcode identities; policies in `policies/` must remain sanitized.
- **Maintenance CLIs**: `duplicate_tree_cli*.py`, `cleanup_temp_artifacts.py`, `find_compressible_files.py`, and `state_db_admin.py` all mutate or depend on the migration DB. Keep schema compatibility.
- **Legacy toolkit**: only the credential helper remains under `cost_toolkit/`; keep it lint/CI clean like any other module.
- **Docs**: Update `README.md`, `docs/README.md`, and runbooks whenever behavior or CLI flags change.

## Code Duplication Policy - CRITICAL

**ALWAYS search for existing implementations before creating new functions.**

### Before Writing Any New Function

1. **Search the codebase first**:
   ```bash
   # Search for similar function names
   grep -r "def function_name" src/

   # Search for similar functionality by keyword
   grep -r "keyword" src/ | grep "def "
   ```

2. **Check `src/` for common utilities**: Look for existing implementations before creating new functions

3. **Use the exploration agent**: When unsure if functionality exists:
   ```
   "Search the codebase for functions that process X"
   "Find all implementations of Y"
   ```

### When You Find Duplicate Functions

**Consolidate them immediately.** Do NOT add another duplicate.

1. Identify the most complete/tested implementation
2. Move it to an appropriate shared location if needed (e.g., `src/common/`, `src/utils/`)
3. Update duplicates to delegate to the canonical version
4. Add clear documentation about the delegation
5. Test that behavior is preserved

Example consolidation:
```python
# BEFORE: Duplicate implementation
def process_data(data):
    return data.strip().lower()

# AFTER: Delegate to canonical
from src.utils.string_utils import normalize_string

def process_data(data):
    """Delegates to canonical implementation in src.utils.string_utils."""
    return normalize_string(data)
```

### Leverage Shared Utilities

- **DO**: Create reusable utilities for common operations
- **DO**: Put shared functions in appropriate modules (`src/common/`, `src/utils/`, etc.)
- **DO**: Document and test shared utilities thoroughly
- **DON'T**: Duplicate logic across modules
- **DON'T**: Create module-specific versions of common utilities

### Why This Matters

Duplicate functions cause:
- **Behavioral drift**: Different parts of code using slightly different logic
- **Bug multiplication**: Same bug must be fixed in multiple places
- **Maintenance burden**: Changes must be made in multiple locations
- **Testing complexity**: Same logic tested multiple times
- **Code bloat**: Unnecessary increase in codebase size

**Keep it DRY (Don't Repeat Yourself).**

## Build, Test, and Automation Commands

- `python -m pip install -e .` -> install tooling for local runs.
- `make format` / `make lint` / `make type` / `make test` -> individual guard rails (black, ruff, pyright, pytest).
- `make check` -> shared CI target (ruff, pylint, pyright, bandit, guard scripts, pytest, coverage, codespell, etc.). Run before handing off work.
- `pytest -n auto tests/ --maxfail=1` -> fastest test loop; scope via `-k` if needed.
- `python migrate_v2.py status` / `python migrate_v2.py reset` -> inspect or rebuild migration state.
- `python block_s3.py --all` + `python apply_block.py --all --dry-run` -> safe policy workflow for validation.

## Coding Style & Testing Expectations

- Python 3.10+, four-space indentation, docstrings on modules/classes/multi-step helpers. Prefer verb-first names like `scan_glacier_inventory`.
- Format with `black` + `isort --profile black`; let `ruff` guide stylistic fixes instead of suppressions.
- Entry points guard execution with `if __name__ == "__main__":` and log actionable status.
- For tests, rely on local fixtures, `botocore.stub.Stubber`, or fake FS layers; never reach live AWS services.
- Schema or state-machine changes require regression tests that prove migration continuity and downgrade safety.

## Commit & Security Hygiene

- Commit subjects are imperative ("Tighten glacier restore pacing"). Bodies mention motivation, impacted scripts, and commands executed.
- Document operational risk (for example, "touches delete flow" or "rewrites policy JSON schema") and required follow-up.
- Keep secrets out of git. Store overrides in `config_local.py`, never in tracked files. Generated artifacts (`s3_migration_state.db`, real policies, logs) stay uncommitted.
- If a linter or guard needs exceptions, update the appropriate entry in `shared-tool-config.toml` or guard-specific config instead of scattering ignores.

## CI Pipeline Compliance - CRITICAL

When CI checks fail, you MUST fix the underlying code issues. This is non-negotiable.

**NEVER:**
- Add ignore statements (`# noqa`, `# pylint: disable`, `# type: ignore`, etc.)
- Add suppression comments (`policy_guard: allow-*`, etc.)
- Modify CI pipeline configuration to skip or weaken tests
- Modify guard scripts to relax thresholds
- Add entries to ignore lists or allowlists to bypass checks
- Disable or comment out failing tests

**ALWAYS:**
- Change the code to fix the actual issue
- Refactor to meet complexity/size limits
- Fix type errors by correcting types
- Resolve linting issues by improving code quality
- Ask the user for guidance if the fix approach is unclear

**Examples:**
- ❌ `# pylint: disable=too-many-arguments` → ✅ Refactor to use a config object
- ❌ `# type: ignore` → ✅ Fix the type annotation
- ❌ Adding to `.gitleaks.toml` → ✅ Remove the hardcoded credential
- ❌ `policy_guard: allow-broad-except` → ✅ Catch specific exceptions
- ❌ Lowering coverage threshold → ✅ Write tests to increase coverage

If you're unsure how to fix a CI failure, ask the user for direction before proceeding.

## Quick Reference

| Topic               | Command / Rule                                                                    |
|---------------------|------------------------------------------------------------------------------------|
| Bootstrap env       | `python -m pip install -e .`                                                      |
| Full CI sweep       | `make check`                                                                      |
| Fast test loop      | `pytest -n auto tests/ --maxfail=1`                                               |
| Migration workflow  | `python migrate_v2.py`, `python migrate_v2.py status`, `python migrate_v2.py reset` |
| Policy workflow     | `python aws_info.py` -> `python block_s3.py --all` -> `python apply_block.py --all --dry-run` |
| Generated artifacts | Never commit `s3_migration_state.db`, sanitized policy JSON only                   |
| Docs touchpoints    | `README.md`, `docs/README.md`, `shared-tool-config.toml`                          |

Claude and the general `AGENTS.md` guidance must stay aligned. If you change one, mirror the change in the other so every automation surface shares identical expectations.
