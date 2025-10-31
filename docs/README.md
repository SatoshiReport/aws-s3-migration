# AWS S3 Management Tools — Complete Documentation

This repository provides a hardened toolkit for discovering, migrating, and securing Amazon S3 buckets. It combines a resilient Python-based migration engine with policy hardening utilities, diagnostics, and supporting documentation. Use this guide to understand the system architecture, operational workflows, and how to extend or troubleshoot the tooling.

---

## 1. Getting Started
- **Python version**: 3.8+ (tested on macOS with Python 3.11)
- **Core dependencies**: `boto3`, `botocore` (install via `pip install boto3`)
- **AWS credentials**: Exported environment variables, AWS CLI profile, or an attached IAM role with S3/STS/IAM privileges
- **Local storage**: Ensure the destination path specified in `config.py` has enough space for a full copy of every source bucket
- **Required tools**: AWS CLI (for fast downloads), SQLite CLI (`sqlite3`) for ad-hoc inspections

### Quick Start Workflow
```bash
# 1. Install dependencies (inside a virtual environment if desired)
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip boto3

# 2. Configure destination paths and runtime settings
cp config.py config.local.py  # optional safeguard
# edit config.py → LOCAL_BASE_PATH, STATE_DB_PATH, Glacier settings

# 3. Run the migration (handles scanning, Glacier restores, downloads automatically)
python migrate_v2.py

# 4. Monitor status as needed
python migrate_v2.py status
```

---

## 2. Repository Map

| Path | Purpose |
| --- | --- |
| `README.md` | High-level overview and quick usage summary |
| `config.py` | Centralized runtime configuration options |
| `migrate_v2.py` | Primary migration orchestrator using AWS CLI for fast downloads |
| `migration_state_v2.py` | Phase-aware SQLite state tracking |
| `aws_utils.py` | Shared AWS helpers (STS/IAM identity, policy generation, S3 helpers) |
| `aws_info.py` | Convenience CLI for showing account metadata and bucket list |
| `block_s3.py` | Generates restrictive bucket policies per bucket or fleet-wide |
| `apply_block.py` | Applies locally generated policies back to S3 buckets |
| `MIGRATION_GUIDE.md`, `SECURITY.md` | Supporting notes and operational guidance |
| `policies/`, `policy_template.json` | Policy output directory and template |
| `s3_migration_state.db` | SQLite database (generated on demand; not tracked in git) |

---

## 3. Configuration Reference (`config.py`)

| Setting | Description |
| --- | --- |
| `LOCAL_BASE_PATH` | Root directory where each S3 bucket is mirrored locally (`bucket/key` layout) |
| `STATE_DB_PATH` | Path to the SQLite database tracking every object and migration state |
| `GLACIER_RESTORE_DAYS` | Number of days to keep restored Glacier objects available |
| `GLACIER_RESTORE_TIER` | Restore tier (`Expedited`, `Standard`, or `Bulk`; auto-adjusted for Deep Archive) |
| `MAX_GLACIER_RESTORES` | Concurrency cap for restore submissions per batch |
| `DOWNLOAD_CHUNK_SIZE` | Streaming chunk size for downloads (bytes) |
| `MAX_CONCURRENT_DOWNLOADS` | (Legacy - not used by migrate_v2.py which uses AWS CLI) |
| `MAX_CONCURRENT_VERIFICATIONS` | Parallel verification workers |
| `BATCH_SIZE`, `DB_BATCH_COMMIT_SIZE` | Batch sizing for work distribution and DB commits |
| `MULTIPART_THRESHOLD`, `MULTIPART_CHUNKSIZE`, `MAX_CONCURRENCY`, `USE_THREADS` | Transfer manager tuning parameters |
| `EXCLUDED_BUCKETS` | Optional list of buckets to skip during scans/migration |

**Tip:** Check `config.py` into version control as ground truth, but keep sensitive overrides (e.g., alternative paths) in a private copy and load via environment variables inside a wrapper if needed.

---

## 4. Data Model & State Management

### SQLite Database (`s3_migration_state.db`)
- Created automatically on first scan; lives beside the scripts by default
- `files` table tracks every object with metadata, lifecycle state, errors, and local paths
- `scanned_buckets` table (V1) records bucket-level inventory summary
- `bucket_status` table (V2) tracks phase completion per bucket (scan → sync → verify → delete)
- `migration_metadata` captures process milestones (e.g., current phase, start timestamps)

### File Lifecycle (`migration_state.FileState`)
`discovered → glacier_restore_requested → glacier_restoring → downloading → downloaded → verified → deleted`  
`error` flags require operator review or `retry-errors`. States are idempotent so interrupted runs can resume safely.

### V2 Phases (`migration_state_v2.Phase`)
`scanning → glacier_restore → glacier_wait → syncing → verifying → deleting → complete`  
Each phase can be resumed independently; bucket-level completion markers protect prior progress.

---

## 5. Migration Engines

### 5.1 `migrate_s3.py` — Python Native Engine
**Use when** you need full control from Python with integrated verification and throttling awareness.

- **Scan (`scan`)**: Enumerates all buckets (or a supplied subset) and builds the object inventory. Respects `EXCLUDED_BUCKETS` and skips already-tracked buckets.
- **Migrate (`migrate`)**: Concurrently downloads files, verifies size checks, and deletes from S3 only after success. Automatically handles Glacier/Deep Archive restores by invoking `GlacierHandler`.
- **Status (`status`)**: Rich progress dashboard showing elapsed time, throughput, per-state counts, and Glacier backlog.
- **Glacier (`glacier`)**: Manually trigger Glacier restore requests/status checks (usually called automatically by the migration loop).
- **Errors (`errors`)**: Lists failed files with contextual metadata.
- **Retry Errors (`retry-errors`)**: Resets error-state files to `discovered` so the next migrate run retries them.
- **Reset (`reset`)**: Prompts before deleting the SQLite database to start fresh.
- **Flags**: `--buckets` limits scanning to named buckets.

**Runtime behavior**
- Thread pool downloads with exponential backoff when the AWS API returns `SlowDown` or `RequestLimitExceeded`
- Local filesystem layout mirrors S3 hierarchy: `<LOCAL_BASE_PATH>/<bucket>/<key>`
- Verification is primarily size-based; boto3 transfer manager handles checksum validation during download
- Safe to interrupt (`Ctrl+C`); state transitions prevent data loss or double-deletion

### 5.2 `migrate_v2.py` — AWS CLI Accelerated Engine
**Use when** you want to leverage `aws s3 sync` for higher throughput while keeping the same safety rails.

- **Phases**: `phase1_scanning` → `phase2_glacier_restore` → `phase3_glacier_wait` → `phase4_sync` → `phase5_verify` → `phase6_delete`
- **AWS CLI integration**: Runs targeted `aws s3 sync` per bucket after Glacier restores complete
- **Bucket gating**: Requires manual confirmation before deletions, ensuring an extra review step
- **Resumability**: Checks current phase on every invocation, so re-running `python migrate_v2.py` continues where it left off
- **Schema upgrades**: Prior to V2 usage, run `python migrate_database.py` to seed bucket-level status if migrating from the original schema

---

## 6. Policy Hardening Utilities

| Script | Description |
| --- | --- |
| `aws_info.py` | Prints AWS account ID, IAM username/ARN, and enumerates all S3 buckets |
| `block_s3.py` | Generates bucket policies that grant `s3:*` only to the current IAM user; supports `--all`, explicit bucket arguments, or interactive mode |
| `apply_block.py` | Applies generated policies. Supports `--all`, explicit bucket names, and `--dry-run` to preview actions |
| `policies/` | Destination directory for generated `<bucket>_policy.json` artifacts |
| `policy_template.json` | Example policy document for custom tweaking |

**Workflow**
1. Discover identity and buckets: `python aws_info.py`
2. Generate policies: `python block_s3.py --all`
3. Inspect policy JSON files under `policies/`
4. Apply in dry-run mode first: `python apply_block.py --all --dry-run`
5. Commit changes: `python apply_block.py --all`

---

## 7. Diagnostics & Operational Helpers

- **`migration_state_v2.py`**: SQLite-backed phase and bucket state tracking for the migration workflow.
- **AWS CLI**: `migrate_v2.py` leverages `aws s3 sync` for optimized bulk transfers.

---

## 8. Operational Best Practices

- **Credentials**: Run with an IAM principal that has explicit S3 and Glacier privileges, plus `iam:GetUser` (for policy generation) and `sts:GetCallerIdentity`.
- **Backups & verification**: Keep local copies until confidence is established; `deleted` state indicates an S3 delete has occurred.
- **Glacier restores**: Expect up to several hours for `DEEP_ARCHIVE` restores. The tooling limits outstanding restore submissions via `MAX_GLACIER_RESTORES`.
- **Throttling**: AWS CLI handles throttling automatically with built-in retry logic.
- **Interruptions**: It is safe to stop processes mid-run; rerun `python migrate_v2.py` to resume.
- **State reset**: Use `python migrate_v2.py reset` only when you intentionally want to rebuild the inventory; deleting the DB requires a fresh scan.

---

## 9. Development & Contribution Notes

- **Environment**: Use a virtual environment; consider creating a `requirements.txt` derived from `pip freeze` for reproducibility.
- **Linting/formatting**: The codebase favors readable, comment-light Python. Align with existing style (PEP 8 spacing, docstrings on modules/classes).
- **Extending commands**: Add argparse subcommands within `migrate_v2.py` when introducing new workflows. Keep docstrings up to date.
- **Database migrations**: If schema changes are required, preserve existing data and document upgrades.
- **Testing ideas**: Stand up a test account with disposable buckets; seed sample objects (STANDARD + GLACIER). Validate both migration engines end-to-end before production use.

---

## 10. Troubleshooting

| Symptom | Probable Cause | Suggested Action |
| --- | --- | --- |
| `botocore.exceptions.NoCredentialsError` | AWS credentials unavailable | Export `AWS_PROFILE`, set env vars, or attach IAM role |
| Bucket stuck in syncing/verifying | Interrupted session | Run `python migrate_v2.py`; the migrator resumes from last phase |
| Glacier files not downloading | Restores still in progress | Wait for Phase 3 to complete; check AWS console for restore job status |
| SQLite locked errors | Multiple processes writing simultaneously | Avoid running multiple migrations at once; allow current job to flush batch updates |
| Local disk fills up | Underestimated storage footprint | Expand `LOCAL_BASE_PATH` capacity or migrate buckets individually |

---

## 11. Additional Reading

- `README.md` — concise overview and primary workflows
- `MIGRATION_GUIDE.md` — historical notes on moving between migration strategies
- `BUGFIXES.md` — recorded fixes with context (useful when auditing behavior)
- `SECURITY.md` — security posture and remediation practices
- AWS official docs on [S3 Lifecycle and Storage Classes](https://docs.aws.amazon.com/AmazonS3/latest/dev/storage-class-intro.html) and [Glacier Restore](https://docs.aws.amazon.com/AmazonS3/latest/userguide/restoring-objects.html)

---

## 12. Support Checklist

Before declaring a migration complete:
1. `python migrate_v2.py status` shows phase=complete and all buckets marked completed
2. All local directories match S3 bucket structure
3. Verify local data integrity (spot-check large files, confirm directory structure)
4. Archive the `s3_migration_state.db` snapshot for provenance
5. If using V2, confirm manual delete confirmations have been executed bucket by bucket

This documentation should equip operators and developers alike with the context needed to run, tune, and extend the AWS S3 management toolkit safely.
