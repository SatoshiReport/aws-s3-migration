# AWS S3 Management Tools

Python toolkit for discovering, migrating, and hardening Amazon S3 buckets. It pairs a resilient migration engine with bucket policy generators and duplicate-tree diagnostics. For deeper operator guidance, see `docs/README.md`; automation notes live under `docs/contributor-guides/`.

## Installation

- Python 3.10+ (per `pyproject.toml`)
- AWS credentials available via environment variables, AWS CLI profile, or IAM role
- AWS CLI installed for fast syncing

Recommended setup from the repo root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Create `config_local.py` (ignored by git) with your personal paths and bucket filters:

```python
LOCAL_BASE_PATH = "/path/to/your/backup/directory"
EXCLUDED_BUCKETS = ["bucket-to-skip-1", "bucket-to-skip-2"]  # optional
```

Tunable defaults (Glacier options, DB paths, concurrency) live in `config.py`.

## Usage

- **S3 migration (`migrate_v2.py`)**
  - Phase-aware workflow: scan → Glacier restore → wait → sync → verify → delete.
  - Commands:
    ```bash
    python migrate_v2.py           # Run/resume migration
    python migrate_v2.py status    # Show current phase and per-bucket progress
    python migrate_v2.py reset     # Rebuild state (prompts before wiping the DB)
    ```
  - Progress is tracked in SQLite (`s3_migration_state.db`) so runs are resumable; deletions require confirmation after verification.

- **Duplicate tree reporting (`duplicate_tree_report.py`)**
  ```bash
  python duplicate_tree_report.py \
    --db-path migration_state_v2.db \
    --base-path /Volumes/backup-drive
  ```
  Leverages migration metadata to find matching directory trees; supports `--min-files`, `--min-size-gb`, and `--delete` with confirmation.

- **Policy hardening workflow**
  ```bash
  python aws_info.py                 # Show account info and buckets
  python block_s3.py --all           # Generate restrictive bucket policies
  python apply_block.py --all --dry-run
  python apply_block.py --all        # Apply after reviewing policies/<bucket>_policy.json
  ```

- **Cost toolkit**
  Helpers from the legacy cost project are under `cost_toolkit/`. Run them from the repo root, for example:
  ```bash
  python cost_toolkit/scripts/billing/aws_billing_report.py
  python cost_toolkit/scripts/audit/aws_s3_audit.py
  ```
  See `cost_toolkit/README.md` for details.

## Directory Structure

```
aws/
├── migrate_v2.py              # Migration orchestrator using AWS CLI
├── migration_state_v2.py      # SQLite state management
├── config.py                  # Configuration defaults
├── config_local.py            # Personal overrides (create locally; ignored)
├── aws_info.py                # Display AWS account info and buckets
├── block_s3.py                # Generate bucket policies
├── apply_block.py             # Apply generated policies
├── duplicate_tree_report.py   # Duplicate directory tree diagnostics
├── aws_utils.py               # Shared AWS helpers
├── docs/                      # Full operator + contributor docs
├── policies/                  # Generated policy files (not tracked)
├── s3_migration_state.db      # SQLite database (generated; not tracked)
└── tests/                     # Pytest suites
```

## Security Notes

- Keep bucket names, paths, and other sensitive overrides in `config_local.py` (already git-ignored).
- Always start policy changes with `--dry-run` and review `policies/*.json` before applying.
- Do not commit generated policy files or SQLite databases.
