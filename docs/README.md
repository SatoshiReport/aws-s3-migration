# AWS S3 Management Tools — Complete Documentation

This repository provides a hardened toolkit for discovering, migrating, and securing Amazon S3 buckets. It combines a resilient Python-based migration engine with policy hardening utilities, diagnostics, and supporting documentation. Use this guide to understand the system architecture, operational workflows, and how to extend or troubleshoot the tooling.

---

## 1. Getting Started
- **Python version**: 3.10+ (tested on macOS with Python 3.11)
- **Core dependencies**: `boto3`, `botocore` (installed via `python -m pip install -e .`)
- **AWS credentials**: Exported environment variables, AWS CLI profile, or an attached IAM role with S3/STS/IAM privileges
- **Local storage**: Ensure the destination path specified in `config.py` has enough space for a full copy of every source bucket
- **Required tools**: AWS CLI (for fast downloads), SQLite CLI (`sqlite3`) for ad-hoc inspections

### Quick Start Workflow
```bash
# 1. Install dependencies (inside a virtual environment if desired)
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

# 2. Configure destination paths and runtime settings
# Create config_local.py with your personal settings
cat > config_local.py << 'EOF'
LOCAL_BASE_PATH = "/path/to/your/backup/directory"
EXCLUDED_BUCKETS = []  # Add bucket names to skip
EOF

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
| `config.py` | Default configuration settings (committed to git) |
| `config_local.py` | Personal settings override (NOT in git - create this file) |
| `migrate_v2.py` | Primary migration entrypoint (phase controller + smoke test hook) |
| `migration_scanner.py` | Phase 1-3 scanning, Glacier restore requests, and polling |
| `migration_orchestrator.py` | Bucket-by-bucket sync → verify → delete pipeline |
| `migration_sync.py` | AWS CLI sync wrapper with destination safety checks |
| `migration_verify_bucket.py` | Inventory + checksum verification for a bucket |
| `migration_state_v2.py` | Phase-aware SQLite state tracking |
| `migration_state_managers.py` | File/bucket state helpers used by the orchestrator |
| `migration_utils.py` | Common utilities (ETag hashing, progress tracking, time helpers) |
| `aws_utils.py` | Shared AWS helpers (STS/IAM identity, policy generation, S3 helpers) |
| `aws_info.py` | Convenience CLI for showing account metadata and bucket list |
| `block_s3.py` | Generates restrictive bucket policies per bucket or fleet-wide |
| `apply_block.py` | Applies locally generated policies back to S3 buckets |
| `docs/contributor-guides/` | Automation/contributor helper docs (AGENTS, CLAUDE guidance) |
| `MIGRATION_GUIDE.md`, `SECURITY.md` | Supporting notes and operational guidance |
| `policies/`, `policy_template.json` | Policy output directory and template |
| `s3_migration_state.db` | SQLite database (generated on demand; not tracked in git) |

---

## 3. Configuration Reference

### Personal Settings (`config_local.py` - not in git)

| Setting | Description |
| --- | --- |
| `LOCAL_BASE_PATH` | Root directory where each S3 bucket is mirrored locally (`bucket/key` layout) |
| `EXCLUDED_BUCKETS` | List of bucket names to skip during scanning/migration |

### System Settings (`config.py`)

| Setting | Description |
| --- | --- |
| `STATE_DB_PATH` | Path to the SQLite database tracking every object and migration state |
| `GLACIER_RESTORE_DAYS` | Number of days to keep restored Glacier objects available |
| `GLACIER_RESTORE_TIER` | Restore tier (`Expedited`, `Standard`, or `Bulk`; auto-adjusted for Deep Archive) |
| `MAX_GLACIER_RESTORES` | Concurrency cap for restore submissions per batch |
| `DOWNLOAD_CHUNK_SIZE` | Streaming chunk size for downloads (bytes) |
| `MAX_CONCURRENT_VERIFICATIONS` | Parallel verification workers |
| `BATCH_SIZE`, `DB_BATCH_COMMIT_SIZE` | Batch sizing for work distribution and DB commits |
| `MULTIPART_THRESHOLD`, `MULTIPART_CHUNKSIZE`, `MAX_CONCURRENCY`, `USE_THREADS` | Transfer manager tuning parameters |

**Security Note:** `config_local.py` is in `.gitignore` and contains your sensitive settings (paths, bucket names). Never commit this file.

---

## 4. Data Model & State Management

### SQLite Database (`s3_migration_state.db`)
- Created automatically on first scan; lives beside the scripts by default
- `files` table tracks every object with metadata, ETag, storage class, and Glacier restore timestamps
- `bucket_status` table tracks inventory totals plus verification metrics (local file count, size-verified count, checksum-verified count, total bytes verified) and phase completion flags (scan → sync → verify → delete)
- `migration_metadata` captures process milestones (e.g., current phase, start timestamps)

### Migration Phases (`migration_state_v2.Phase`)
- **scanning** → **glacier_restore** → **glacier_wait** → **syncing/verifying/deleting** → **complete**
- Phase markers are persisted, so re-running `python migrate_v2.py` resumes the next required step
- Bucket-level sync/verify/delete flags ensure you never repeat completed work on already-migrated buckets

---

## 5. Migration Engines

### `migrate_v2.py` — AWS CLI Accelerated Engine
- **Phases**:
  1. Scan every bucket and record objects in SQLite
  2. Request Glacier restores (tier chosen from `config.py`, with Deep Archive forced to `Bulk`)
  3. Poll restores until clear
  4. For each bucket: `aws s3 sync` to local storage → verify inventory and checksums → prompt before deleting from S3
- **Verification**: `migration_verify_bucket.py` recomputes sizes and checksums for every expected key, stores verification counts in `bucket_status`, and re-runs verification if metrics are missing.
- **Resumability**: Phase and bucket flags live in the DB, so re-running the command resumes exactly where it stopped. Per-bucket deletion always requires a fresh confirmation prompt.
- **Commands**:
  ```bash
  python migrate_v2.py           # Run/resume migration
  python migrate_v2.py status    # Show phase/bucket progress from SQLite
  python migrate_v2.py reset     # Recreate the state DB (prompts before deleting)
  python migrate_v2.py --test    # Local smoke test for the sync/verify pipeline
  ```

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

- **Status view**: `python migrate_v2.py status` reads SQLite to print bucket-by-bucket sync/verify/delete completion plus totals.
- **Verification tooling**: `migration_verify_inventory.py` (expected vs local keys) and `migration_verify_checksums.py` (size + checksum validation) underpin the bucket verifier.
- **State helpers**: `migration_state_v2.py` + `migration_state_managers.py` centralize all DB interactions so orchestration code stays small.
- **AWS CLI**: `migrate_v2.py` leverages `aws s3 sync` for optimized bulk transfers.

---

## 8. Operational Best Practices

- **Credentials**: Run with an IAM principal that has explicit S3 and Glacier privileges, plus `iam:GetUser` (for policy generation) and `sts:GetCallerIdentity`.
- **Verification first**: Keep local copies until a bucket shows `delete_complete=1` and verification metrics are recorded.
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
- **Testing ideas**: Stand up a test account with disposable buckets; seed sample objects (STANDARD + GLACIER). Validate the `migrate_v2.py` flow end-to-end before production use.

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
- `MIGRATION_GUIDE.md` — step-by-step quick start for the current migration workflow
- `SECURITY.md` — security posture and remediation practices
- `docs/FIXES_APPLIED.md` — log of remediation work captured during past hardening efforts
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
