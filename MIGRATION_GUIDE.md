# S3 Migration Quick Start Guide

## Overview

- `migrate_v2.py` runs the entire migration: inventory, Glacier restores, `aws s3 sync`, full verification, then an explicit delete prompt per bucket.
- Four persisted phases: **scanning** → **glacier_restore** → **glacier_wait** → **bucket migration (sync → verify → delete)** → **complete**.
- State lives in `s3_migration_state.db` (`files`, `bucket_status`, `migration_metadata` tables), so reruns are safe after interruptions.

## Setup

1. **Environment**: Python 3.10+, AWS CLI v2 on PATH, and valid AWS credentials (env vars, CLI profile, or IAM role).
2. **Install** (repo root):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -e .
   ```
3. **Configure**: create `config_local.py` (git-ignored) for your paths/filters:
   ```python
   LOCAL_BASE_PATH = "/path/to/your/backup/directory"
   EXCLUDED_BUCKETS = []  # optional skips
   ```
   Tunables such as `STATE_DB_PATH`, `GLACIER_RESTORE_DAYS`, and `GLACIER_RESTORE_TIER` are in `config.py`.

## Run the Migration

```bash
python migrate_v2.py        # run/resume
python migrate_v2.py status # view progress
python migrate_v2.py reset  # rebuild state DB (prompts)
python migrate_v2.py --test # local smoke test harness
```

What happens on `python migrate_v2.py`:
1. **Scan**: enumerate buckets (excluding any in `EXCLUDED_BUCKETS`), record every key/size/ETag/storage class in SQLite.
2. **Glacier restore**: submit restores for archived objects (Deep Archive uses `Bulk` automatically).
3. **Glacier wait**: poll restore completion every five minutes until clear.
4. **Bucket pipeline** (one bucket at a time):
   - Sync via `aws s3 sync` to `LOCAL_BASE_PATH/<bucket>`
   - Verify inventory and checksums for every expected key
   - Show a verification summary and prompt `Delete this bucket from S3? (yes/no)`
   - Mark the bucket complete only after deletion succeeds

## Checking Progress & State

- `python migrate_v2.py status` prints the current phase, totals, and per-bucket sync/verify/delete flags.
- SQLite is human-readable; quick queries:
  ```bash
  sqlite3 s3_migration_state.db "SELECT bucket, file_count, total_size, sync_complete, verify_complete, delete_complete, verified_file_count FROM bucket_status;"
  sqlite3 s3_migration_state.db "SELECT COUNT(*) FROM files WHERE glacier_restored_at IS NULL AND storage_class LIKE 'GLACIER%';"
  ```
- Verification metrics (`size_verified_count`, `checksum_verified_count`, `total_bytes_verified`, `local_file_count`) live in `bucket_status` after a bucket finishes verification.

## Verification Details

- Inventory: `migration_verify_inventory.py` ensures the local file list exactly matches the recorded S3 keys (no missing or extra files; system files like `.DS_Store` are ignored in counts).
- Checksums: `migration_verify_checksums.py` recomputes sizes and MD5/ETag (or SHA for multipart uploads), updates verification counters, and raises if any mismatch is found.
- If verification metrics are missing, the verifier re-runs even when `verify_complete` was previously set, ensuring consistent records before deletion.

## Resuming & Safety

- Safe to interrupt with `Ctrl+C`; rerun `python migrate_v2.py` to continue from the recorded phase.
- Bucket-level flags prevent re-syncing or re-deleting completed buckets.
- Deletion always requires a fresh `yes` confirmation after showing verification results.

## Troubleshooting

- **Drive issues**: If the destination drive is missing or unwritable, the run stops and prints instructions. Reconnect/mount the drive and rerun.
- **Restore backlog**: Use the SQLite query above to see remaining Glacier files.
- **Verification failures**: The verifier reports the exact key; fix the local path or re-sync the bucket, then rerun `python migrate_v2.py`.
- **Fresh start**: `python migrate_v2.py reset` recreates the DB without touching local files.

## Cost & Timing Notes

- Glacier restores incur retrieval costs; Deep Archive restores use `Bulk` by design and can take many hours.
- Data transfer and API request charges follow standard S3 pricing.
- Sync/verify performance depends on network and disk throughput; checksum verification reads every byte.

## More Info

- `README.md` for a high-level overview
- `docs/README.md` for architecture details and component map
- `SECURITY.md` for data-handling guidance
