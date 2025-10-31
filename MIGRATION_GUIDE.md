# S3 Migration Quick Start Guide

## Overview

This tool safely migrates all your S3 buckets to local storage. It's designed to be simple, resilient, and safe.

## Setup

### 1. Configure Destination

Edit `config.py` and set your local destination path:

```python
LOCAL_BASE_PATH = os.path.expanduser("~/s3_backup")  # Change this!
```

### 2. Ensure AWS Credentials

Make sure your AWS credentials are configured:
```bash
aws configure
# or set environment variables:
# export AWS_ACCESS_KEY_ID=...
# export AWS_SECRET_ACCESS_KEY=...
```

## Migration Steps

### Step 1: Run Migration

Start the migration process:

```bash
python migrate_v2.py
```

**That's it!** The migration handles everything automatically in phases:

**Phase 1 - Scanning:**
- Discovers all files across all buckets
- Identifies Glacier/Deep Archive files

**Phase 2 - Glacier Restore:**
- Requests restores for all Glacier files

**Phase 3 - Glacier Wait:**
- Checks restore status every 60 seconds
- Waits for all restores to complete

**Phase 4 - Migrate Buckets:**
- For each bucket (one at a time):
  - Downloads using AWS CLI `aws s3 sync` (fast!)
  - Verifies all files (size + integrity checks)
  - Deletes from S3 after manual confirmation
  - Marks bucket complete before moving to next

**You can interrupt this at any time (Ctrl+C) and resume later!**

The script runs continuously through all phases, automatically handling Glacier restores.

### Check Status

View current progress:

```bash
python migrate_v2.py status
```

Shows:
- Current phase
- Completed buckets
- Total files and size
- Glacier restore progress

### Glacier Restore Times

If you have Glacier files, the migration will automatically wait for them:
- **Standard**: 3-5 hours (default)
- **Expedited**: 1-5 minutes (more expensive, configure in config.py)
- **Bulk**: 5-12 hours (cheaper, configure in config.py)

The script checks every 60 seconds for completed restores and downloads them as they become available.

## Resuming After Interruption

The migration is fully resumable. Just run:

```bash
python migrate_v2.py
```

It will pick up exactly where it left off. State is saved after each phase and after each bucket completion.

## Progress Display

While migrating, you'll see phase-specific progress:

**Phase 1-3 (Scanning & Glacier):**
```
Phase: scanning
Buckets scanned: 5/10
Files discovered: 1,234
Glacier files: 234
```

**Phase 4 (Migrating Buckets):**
```
Phase: migrate_buckets
Current bucket: my-bucket-name
Status: syncing (downloading files via AWS CLI)
Completed buckets: 3/10
```

## Migration Phases

The migration progresses through these phases:

1. **scanning** - Discovering all files across all buckets
2. **glacier_restore** - Requesting Glacier restores
3. **glacier_wait** - Waiting for all restores to complete
4. **migrate_buckets** - Downloading, verifying, and deleting bucket-by-bucket
5. **complete** - All buckets migrated successfully

Each bucket in Phase 4 goes through:
- **pending** - Waiting to be processed
- **syncing** - Downloading via AWS CLI
- **verifying** - Checking file integrity
- **deleting** - Removing from S3 (after confirmation)
- **completed** - Bucket fully migrated

## Safety Features

1. **Verification Before Deletion**: Files are only deleted from S3 after:
   - Successful download
   - Checksum verification passes
   - Local file exists and matches

2. **Corruption Detection**: If verification fails:
   - Local file is deleted
   - State is marked as error
   - File can be retried

3. **State Persistence**: All progress saved to SQLite:
   - No in-memory state
   - Survives crashes/interruptions
   - Fast startup on resume

## File Organization

Files are organized locally as:
```
~/s3_backup/
├── bucket1/
│   ├── file1.txt
│   └── folder/
│       └── file2.txt
├── bucket2/
│   └── data.csv
└── bucket3/
    └── images/
        └── photo.jpg
```

Each bucket becomes a directory, preserving the S3 key structure.

## Troubleshooting

### Check Status Anytime
```bash
python migrate_v2.py status
```

### View State Database
```bash
sqlite3 s3_migration_state.db
sqlite> SELECT phase FROM migration_state;
sqlite> SELECT bucket_name, status FROM bucket_states;
```

### Reset Migration
To start completely over:
```bash
python migrate_v2.py reset
```

## Configuration Options

In `config.py`:

```python
# Local destination directory
LOCAL_BASE_PATH = os.path.expanduser("~/s3_backup")

# Glacier restore settings
GLACIER_RESTORE_DAYS = 1              # Days to keep restored
GLACIER_RESTORE_TIER = "Standard"      # Expedited, Standard, or Bulk

# Progress update interval
PROGRESS_UPDATE_INTERVAL = 2           # Seconds

# Verification method
VERIFICATION_METHOD = "etag"           # 'etag' or 'md5'

# Max concurrent Glacier restores
MAX_GLACIER_RESTORES = 100

# Download chunk size
DOWNLOAD_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB
```

## Best Practices

1. **Test First**: Try with a small bucket first to verify setup
2. **Monitor Disk Space**: Ensure enough space for all data
3. **Check Status Regularly**: Run `status` command to monitor progress
4. **Keep Database Safe**: Back up `s3_migration_state.db` periodically
5. **Verify Results**: After completion, spot-check some files
6. **Let It Run**: The migrate command handles everything automatically - just let it run

## Glacier Timeline

Typical timeline for migration with Glacier files:

**Day 1:**
- Phase 1: Scanning (minutes)
- Phase 2: Request Glacier restores (minutes)
- Phase 3: Wait for restores (begins)

**Day 2-3:**
- Phase 3: Standard tier Glacier restores complete
- Phase 4: Migrate buckets (begins)

**Day 4+:**
- Phase 4: All buckets migrated
- S3 buckets empty (files deleted after verification)
- Migration complete!

**Note:** You don't need to babysit the migration. Run `python migrate_v2.py` once and it handles everything. You can interrupt and resume anytime.

## Performance

Expected throughput varies based on:
- Network speed
- File sizes (many small files = slower)
- S3 region
- Local disk speed

Typical speeds:
- Fast connection: 50-100 MB/s
- Normal connection: 10-30 MB/s
- Slow connection: 1-10 MB/s

## Cost Considerations

- **Glacier Restores**: Cost per GB restored (varies by tier)
- **Data Transfer**: S3 egress charges apply
- **API Requests**: LIST, GET, DELETE operations (minimal cost)

Expedited retrievals cost more but are faster. Standard tier is usually sufficient.

## Questions?

Check `README.md` or `CLAUDE.md` for more details on architecture and implementation.
