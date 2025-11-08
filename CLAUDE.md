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
