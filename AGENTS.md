# Repository Guidelines

## Project Structure & Module Organization
The toolkit lives in self-contained Python scripts at the repository root. `migrate_v2.py` drives bucket migrations using AWS CLI for optimized downloads, with state tracking in `migration_state_v2.py`. Policy automation resides in `block_s3.py`, `apply_block.py`, and the `policies/` folder where generated JSON lives; never commit real bucket names. Documentation and deep dives are in `docs/`, while operational state such as `s3_migration_state.db` is created at runtime and should stay out of version control.

## Build, Test, and Development Commands
Create a virtual environment and install dependencies with `python -m venv .venv && source .venv/bin/activate && pip install --upgrade pip boto3`. Use `python migrate_v2.py` to run migrations and `python migrate_v2.py status` to review progress. Policy workflows follow `python aws_info.py`, `python block_s3.py --all`, and `python apply_block.py --all --dry-run`.

## Coding Style & Naming Conventions
Target Python 3.8+ and follow PEP 8 with 4-space indentation and descriptive, verb-first function names (e.g., `sync_glacier_restores`). Shared configuration options live in `config.py`; keep overrides in `config.local.py` or environment variables. Script entry points should gate execution with `if __name__ == "__main__":` and log meaningful progress via `print` or `progress_tracker`.

## Testing Guidelines
Automated tests are not yet committed, so add new coverage under `tests/` using pytest naming (`test_<module>.py`). Mock AWS with `botocore Stubber` or local fixtures so suites run offline. Run `pytest -q` before submitting; include regression checks for Glacier transitions, policy rendering, and database migrations.

## Commit & Pull Request Guidelines
Commits follow short, imperative subject lines (`Optimize S3 migration with throttle detection`). Group logical changes together and mention affected scripts in the body when relevant. Pull requests should summarize risk, list reproduced commands, link any tracking issue, and attach screenshots or CLI snippets for policy diffs or migration status outputs.

## Security & Configuration Tips
Review `SECURITY.md` before handling real buckets and scrub credentials from logs. Keep `config.py` sane defaults in git, but store sensitive overrides outside the repository and document them for operators in `docs/`. When sharing traces, mask bucket names and account IDs, and prefer dry-run modes until configurations are double-checked.
