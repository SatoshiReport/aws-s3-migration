# AWS S3 Migration & Management Toolkit

This repository contains a suite of Python tools for AWS S3 bucket migration, policy hardening, duplicate file analysis, and cost optimization. It is designed for resilient, phase-aware operations on large-scale S3 environments.

## Project Overview

*   **Purpose:** Automate S3 bucket migration (with Glacier restore support), enforce restrictive security policies, identify duplicate directory trees, and audit AWS costs.
*   **Architecture:** Flat structure for primary CLI tools (root directory), with shared utilities (`aws_utils.py`) and state management (`migration_state_v2.py`) backed by SQLite. Specialized sub-tools reside in directories like `cost_toolkit/` and `duplicate_tree/`.
*   **Key Technologies:**
    *   **Language:** Python 3.10+
    *   **AWS SDK:** `boto3` / `botocore`
    *   **State Management:** SQLite (via `sqlite3`; `psycopg2-binary` is a dependency but usage is local DB)
    *   **Validation:** `pydantic`
    *   **Testing:** `pytest`

## Getting Started

### Installation

1.  **Environment:** Create and activate a virtual environment.
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```
2.  **Dependencies:** Install the package in editable mode.
    ```bash
    python -m pip install --upgrade pip
    python -m pip install -e .
    ```
3.  **Configuration:**
    *   Create `config_local.py` in the root (git-ignored).
    *   Define `LOCAL_BASE_PATH` and `EXCLUDED_BUCKETS` as needed.
    *   Refer to `config.py` for defaults.

### Key Workflows

*   **S3 Migration:**
    *   Run: `python migrate_v2.py`
    *   Status: `python migrate_v2.py status`
    *   Reset: `python migrate_v2.py reset`
    *   *Features:* Phase-aware (Scan -> Restore -> Sync -> Verify -> Delete), resumable (SQLite state).

*   **Policy Hardening:**
    *   Audit: `python aws_info.py`
    *   Generate: `python block_s3.py --all`
    *   Apply: `python apply_block.py --all --dry-run` (Always verify generated JSON in `policies/` first).

*   **Duplicate Analysis:**
    *   Report: `python duplicate_tree_report.py --db-path migration_state_v2.db --base-path /path/to/data`

## Development & CI

This project enforces strict code quality standards. All checks must pass; overriding checks with `noqa` or similar is prohibited.

### Core Commands

*   **Full CI Pipeline:** `make check` (Runs all checks in order).
*   **Formatting:** `make format` (Black, isort).
*   **Linting:** `make lint` (Ruff, Pylint).
*   **Type Checking:** `make type` (Pyright).
*   **Testing:** `make test` (Pytest).

### CI Pipeline Contract

The CI pipeline (`make check` or `ci_tools/scripts/ci.sh`) runs the following tools in strict order. Failure in any step halts the pipeline.

1.  `codespell`
2.  `vulture` (Dead code detection)
3.  `deptry` (Dependency verification)
4.  `gitleaks` (Secret scanning)
5.  `bandit_wrapper` (Security linting)
6.  `safety scan` (Vulnerability scanning)
7.  `ruff --fix`
8.  `pyright --warnings`
9.  `pylint`
10. `pytest` (Serial execution only)
11. `coverage_guard` (Enforces 80%)
12. `compileall`

### Standards & Conventions

#### Strict Limits
*   **Module Size:** ≤ 400 lines
*   **Class Size:** ≤ 100 lines
*   **Function Size:** ≤ 80 lines
*   **Cyclomatic Complexity:** ≤ 10
*   **Cognitive Complexity:** ≤ 15
*   **Inheritance Depth:** ≤ 2
*   **Methods:** ≤ 15 public / 25 total methods per class
*   **Instantiation:** ≤ 5 instantiations in `__init__` / `__post_init__`

#### Code Hygiene
*   **No Duplication:** strictly enforced. Before writing new helpers:
    *   Search the repo: `rg "def <name>" .`
    *   Check `aws_utils.py`, `migration_state_v2.py`, and shared CLI modules.
    *   If duplicates exist: Centralize the best version, update callers to import it, and document the delegation.
*   **Config over Env:** Prefer config JSON files over adding new environment variables. Only add ENV when absolutely required and document it.
*   **No "Legacy" Patterns:** The following terms/patterns are **banned** by `policy_guard`:
    *   `legacy`, `fallback`, `default`, `catch_all`, `failover`, `backup`, `compat`, `backwards`, `deprecated`, `legacy_mode`, `old_api`, `legacy_flag`
    *   `TODO`, `FIXME`, `HACK`, `WORKAROUND`
    *   Broad/empty exception handlers.
    *   Literal fallbacks in `.get`, `setdefault`, ternaries, `os.getenv`, or `if x is None`.
    *   Blocking calls: `time.sleep`, `subprocess.*`, `requests.*` inside source code.

#### Non-Negotiables
*   **Never Bypass Checks:** Fix root causes. Do not use `# noqa`, `# pylint: disable`, `# type: ignore`, or modify thresholds/allow-lists.
*   **No Secrets:** Keep secrets and generated artifacts (DBs, policies) out of git. Use `.gitleaks.toml` for sanctioned patterns only.
*   **Maintain Docs:** Keep `README.md`, `CLAUDE.md`, and `docs/` up to date. Do not revert user edits.

### File Structure

*   `migrate_v2.py`: Main migration orchestrator.
*   `migration_state_v2.py`: Database interface for migration state.
*   `aws_utils.py`: Shared AWS API wrappers and logic.
*   `config.py`: Default configuration settings.
*   `tests/`: Comprehensive pytest suite.
*   `policies/`: Output directory for generated IAM policies (not tracked).
*   `ci_tools/`: Internal tooling for the CI pipeline.