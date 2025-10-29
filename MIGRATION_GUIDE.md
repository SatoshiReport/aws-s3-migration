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

### Step 1: Scan Buckets

Build an inventory of all files across all buckets:

```bash
python migrate_s3.py scan
```

This creates a SQLite database (`s3_migration_state.db`) tracking every file.

### Step 2: Check Status

View what will be migrated:

```bash
python migrate_s3.py status
```

Shows:
- Total files and size
- Files in each state
- Glacier files that need restore

### Step 3: Start Migration

Begin the migration process:

```bash
python migrate_s3.py migrate
```

**That's it!** The migrate command handles everything automatically:
- Downloads standard storage files immediately
- Detects Glacier/Deep Archive files
- Requests restores for Glacier files (up to 100 at a time)
- Checks restore status every 60 seconds
- Downloads files as they become available
- Verifies each file using ETag/MD5
- Only deletes from S3 after successful verification
- Shows progress every 2 seconds with elapsed time and ETA

**You can interrupt this at any time (Ctrl+C) and resume later!**

The script runs continuously until all files are migrated, automatically handling the Glacier restore waiting period.

### Glacier Restore Times

If you have Glacier files, the migration will automatically wait for them:
- **Standard**: 3-5 hours (default)
- **Expedited**: 1-5 minutes (more expensive, configure in config.py)
- **Bulk**: 5-12 hours (cheaper, configure in config.py)

The script checks every 60 seconds for completed restores and downloads them as they become available.

## Resuming After Interruption

The migration is fully resumable. Just run:

```bash
python migrate_s3.py migrate
```

It will pick up exactly where it left off. State is saved after every file.

## Progress Display

While migrating, you'll see:

```
======================================================================
MIGRATION PROGRESS
======================================================================
Elapsed Time:    2h 15m
ETA:             45m 30s

Files:           1,234 / 5,678 (21.7%)
Data:            156.78 GB / 723.45 GB (21.7%)
Throughput:      19.45 MB/s

Status Breakdown:
  Discovered                    3,210 files    421.34 GB
  Downloading                       1 files      0.15 GB
  Downloaded                       12 files      1.23 GB
  Verified                        221 files     45.67 GB
  Deleted                       1,234 files    156.78 GB
======================================================================
```

## File States

Each file goes through these states:

1. **discovered** - Found during scan, ready to process
2. **downloading** - Currently being downloaded
3. **downloaded** - Download complete, awaiting verification
4. **verified** - Local copy verified, ready to delete from S3
5. **deleted** - Successfully deleted from S3 (migration complete!)

For Glacier files, additional states:
- **glacier_restore_requested** - Restore requested from Glacier
- **glacier_restoring** - Waiting for restore to complete

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
python migrate_s3.py status
```

### View State Database
```bash
sqlite3 s3_migration_state.db
sqlite> SELECT state, COUNT(*) FROM files GROUP BY state;
sqlite> SELECT * FROM files WHERE state = 'error';
```

### Rescan a Bucket
If new files were added during migration:
```python
from migration_state import MigrationState
from s3_scanner import S3Scanner

state = MigrationState('s3_migration_state.db')
scanner = S3Scanner(state)
scanner.rescan_bucket('bucket-name')
```

### Reset a Failed File
If a file is stuck in 'error' state and you want to retry:
```python
from migration_state import MigrationState, FileState

state = MigrationState('s3_migration_state.db')
state.update_state('bucket-name', 'file-key', FileState.DISCOVERED)
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
- Run `scan` (minutes)
- Run `migrate` - it will:
  - Download standard files immediately
  - Request Glacier restores automatically
  - Continue downloading as restores complete

**Day 2-3:**
- Standard tier Glacier restores complete
- The migrate command (still running or resumed) downloads them automatically

**Day 4+:**
- All files migrated
- S3 buckets empty (files deleted after verification)

**Note:** You don't need to babysit the migration. Run `migrate` once and it handles everything. You can interrupt and resume anytime.

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
