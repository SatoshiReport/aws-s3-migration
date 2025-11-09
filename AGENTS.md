# Automation Agent Rulebook

Everything an automation agent needs to keep the AWS S3 management toolkit healthy before changes hit CI.

## Mission Checklist

1. **Understand the surface area.** Read this rulebook, `README.md`, `docs/README.md`, and the doc linked to your task. Skim the module you are touching plus its helpers (`migration_state_v2.py`, `aws_utils.py`, etc.).
2. **Keep changes surgical.** Never revert user edits you did not make. Favor `apply_patch` for single-file edits and isolate unrelated fixes into follow-up PRs.
3. **Validate early.** Run formatters, linters, and the smallest useful slice of tests before handing work back--CI should be a formality.

## CI Pipeline Enforcement - Non-Negotiable Rules

Agents working in this repository must pass all CI checks by fixing code, not by bypassing checks.

### Prohibited Actions
1. Adding ignore/suppression directives (`# noqa`, `# pylint: disable`, `# type: ignore`, `policy_guard: allow-*`)
2. Modifying CI pipeline configuration to skip tests or weaken checks
3. Editing guard scripts to relax enforcement thresholds
4. Adding entries to ignore lists, allowlists, or exclusion files to bypass failures
5. Disabling, skipping, or commenting out failing tests

### Required Actions
1. Fix the root cause in the code
2. Refactor to meet architectural constraints (complexity, size, structure)
3. Correct type errors with proper type annotations
4. Improve code quality to satisfy linting rules
5. Increase test coverage by writing additional tests
6. Ask for human guidance when the correct fix approach is ambiguous

### Enforcement Examples

| CI Failure | ❌ Wrong Approach | ✅ Correct Approach |
|------------|------------------|---------------------|
| Too many arguments (>7) | Add `# pylint: disable` | Refactor to use dataclass/config object |
| Type error | Add `# type: ignore` | Fix the type annotation or refactor |
| Hardcoded secret detected | Add to `.gitleaks.toml` | Move to environment variable/config |
| Broad exception handler | Add `policy_guard: allow-broad-except` | Catch specific exception types |
| Coverage below 80% | Lower threshold in config | Write tests for uncovered code |
| Function too complex | Add complexity ignore | Extract smaller functions |
| Class too large (>100 lines) | Increase structure guard limit | Split into multiple classes |

If fixing a CI failure requires architectural changes and you're uncertain about the approach, stop and request human guidance before proceeding.

```bash
# Pre-flight you can paste before coding
set -euo pipefail
git status -sb
python -m pip install -e . >/dev/null
make check
```

## Repository Map

```
.
+-- migrate_v2.py / migration_state_v2.py    # S3 migration orchestration + SQLite state machine (treat schema as an API)
+-- aws_info.py / block_s3.py / apply_block.py
|                                            # AWS identity + policy generation/apply CLIs (writes JSON to policies/, no real bucket names)
+-- duplicate_tree_cli*.py                   # Duplicate tree reporting/cleanup CLIs cached inside the migrate_v2 DB
+-- cleanup_temp_artifacts.py, find_compressible_files.py
|                                            # Local-drive maintenance CLIs that reuse migration DB helpers
+-- cost_toolkit/                            # Shared credential helpers kept from the legacy cost toolkit
+-- docs/                                    # Operator + contributor guides (start with docs/README.md)
+-- tests/                                   # Pytest suites and fixtures; expand coverage for every behavior change
+-- policies/                                # Generated bucket policies (safe mock data only)
+-- Makefile / ci_shared.mk                  # Shared CI entry points (make format|lint|type|test|check)
+-- shared-tool-config.toml                  # Linter + guard configuration consumed downstream
+-- config.py                                # Checked-in defaults; personal overrides belong in config_local.py
`-- s3_migration_state.db                    # Generated at runtime; never commit but respect schema when tooling mutates it
```

Treat `migration_state_v2.py`, `aws_utils.py`, and the CLI argument contracts as public interfaces--downstream scripts depend on them.

## Build, Test, and Automation Commands

- `python -m pip install -e .` -> install the repo in editable mode so entry points and guards are available.
- `make format`, `make lint`, `make type`, `make test` -> run individual guard rails (black, ruff, pyright, pytest).
- `make check` -> shared CI super-target (ruff, pylint, pyright, bandit, guard scripts, pytest, coverage, codespell, etc.). Always run before sharing work.
- `pytest -n auto tests/ --maxfail=1` -> fastest feedback loop for targeted suites; use `-k` to scope as needed.
- `python migrate_v2.py status` / `python migrate_v2.py reset` -> inspect or rebuild migration state when debugging DB issues.
- `python block_s3.py --all` + `python apply_block.py --all --dry-run` -> safest way to exercise policy tooling without touching production.

## Coding Style & Lint Expectations

- Python 3.10+, four-space indentation, docstrings on modules/classes/multi-step helpers. Keep function names verb-first (for example `scan_glacier_inventory`).
- Format with `black` and manage imports via `isort --profile black`; ruff enforces most style rules--prefer fixes over ignores.
- Entry points must guard execution with `if __name__ == "__main__":` and emit user-friendly progress (`print` or structured logging).
- Respect CLI UX: reuse shared option names/flags, default to safe dry-run behavior, and document new arguments in `docs/`.
- `cost_toolkit/` now only contains the shared credential helper (`aws_utils.py`). Treat it like the rest of the repo and keep it lint/CI clean.

## Testing Rules

- Tests live in `tests/` with `test_<module>.py` naming. Mirror CLI scenarios by exercising helper functions rather than invoking subprocesses when possible.
- Use `botocore.stub.Stubber`, local fixtures, or fake file systems to keep suites offline; never hit real AWS services.
- When changing the migration state machine, add regression tests for the new phase/bucket transitions and DB migrations.
- For new guard scripts or config loaders, ship pytest coverage plus golden-files/fixtures to document expected output.
- Keep runtime artifacts (`s3_migration_state.db`, generated policies) out of git; use temp dirs or pytest fixtures to stage them during tests.

## Commit & PR Hygiene

- Subjects are short and imperative (`Tighten glacier restore pacing`). Include motivation, impacted scripts, and links to tracking issues in the body.
- List every command you ran (`make check`, focused pytest, policy dry-runs) so future agents know what passed.
- Describe operational risk (for example, "touches delete flow" or "rewrites policy JSON schema") and mention any manual follow-up required.
- Split mechanical formatting from behavioral changes whenever possible to keep reviews small.

## Security & Configuration Discipline

- Never hardcode AWS credentials, account IDs, or real bucket names. Store personal overrides in `config_local.py`, which is ignored.
- Generated artifacts (`policies/*.json`, `s3_migration_state.db`, `logs/`) should be treated as ephemeral; clean them up before committing.
- If you must store sample data, sanitize identifiers and document the source.
- Keep automation context centralized in `shared-tool-config.toml` and `config.py`; do not scatter duplicate knobs elsewhere.
- Secrets scanning (`gitleaks`) and safety guards run in CI--prefer allowlist updates in `ci_tools/config/` over ad-hoc suppression.

## Quick Reference Table

| Topic                     | Command / Rule                                                                    |
|---------------------------|------------------------------------------------------------------------------------|
| Bootstrap environment     | `python -m pip install -e .`                                                      |
| Full CI sweep             | `make check`                                                                      |
| Format + lint             | `make format && make lint && make type`                                           |
| Focused tests             | `pytest -n auto tests/ --maxfail=1`                                               |
| Migration workflow        | `python migrate_v2.py`, `python migrate_v2.py status`, `python migrate_v2.py reset` |
| Policy workflow           | `python aws_info.py` -> `python block_s3.py --all` -> `python apply_block.py --all --dry-run` |
| Generated artifacts       | Never commit `s3_migration_state.db`, real policy JSON, or logs with account data |
| Docs to update            | `README.md`, `docs/README.md`, `shared-tool-config.toml` when behavior changes     |

Keep `AGENTS.md` and `CLAUDE.md` in sync--if you tighten or relax a rule here, mirror it so every automation surface shares the same expectations.
