# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a personal AWS S3 bucket management repository containing Python scripts for:
1. **S3 Migration**: Complete bucket migration to local storage with resilience and Glacier support
2. **Policy Management**: Managing S3 bucket policies and AWS account information

All scripts use shared utility functions and support command-line arguments for flexible operation.

## Architecture

### S3 Migration System

The migration system is designed for resilience and safety:

**migrate_s3.py** - Main orchestrator with commands:
- `scan` - Build inventory of all S3 files
- `migrate` - Execute migration (resumable)
- `glacier` - Process Glacier restore requests
- `status` - Display current progress

**State Management (migration_state.py)**:
- SQLite database tracks every file through its lifecycle
- States: discovered → downloading → downloaded → verified → deleted
- Glacier files have additional states: glacier_restore_requested → glacier_restoring
- Enables instant resumption after interruption

**Core Components**:
- `s3_scanner.py` - Discovers all files across all buckets
- `file_migrator.py` - Downloads, verifies (ETag/MD5), and deletes files
- `glacier_handler.py` - Manages Glacier restore requests and status checks
- `progress_tracker.py` - Live progress display with ETA calculations
- `config.py` - Configuration (LOCAL_BASE_PATH, Glacier settings, etc.)

**Key Design Principles**:
1. Safety first: Only delete from S3 after verified local copy
2. Resilience: Can stop/resume at any time via state DB
3. Simplicity: No complex fallback logic, straightforward state machine
4. Transparency: Live progress with elapsed time and ETA

### Policy Management System

**Core Modules**

**aws_utils.py** - Shared utility library providing:
- `get_boto3_clients()` - Creates boto3 clients for S3, STS, and IAM
- `get_aws_identity()` - Retrieves AWS account ID, username, and user ARN
- `list_s3_buckets()` - Lists all S3 buckets in the account
- `generate_restrictive_bucket_policy()` - Creates policies allowing only specific IAM user
- `save_policy_to_file()` / `load_policy_from_file()` - Policy file I/O
- `apply_bucket_policy()` - Applies policy to S3 bucket

### Scripts

**aws_info.py** - Displays AWS account information and all S3 buckets using shared utilities.

**block_s3.py** - Generates restrictive S3 bucket policies with CLI support:
- Accepts bucket names as arguments
- Supports `--all` flag to process all buckets
- Interactive mode when run without arguments
- Dynamically retrieves IAM user ARN (no hardcoded values)
- Saves policies to `policies/` directory

**apply_block.py** - Applies bucket policies to S3 with CLI support:
- Accepts bucket names as arguments
- Supports `--all` flag to apply all available policies
- Supports `--dry-run` to preview changes
- Interactive mode shows available policy files
- Reads policies from `policies/` directory

## Common Commands

### S3 Migration

```bash
# Configure destination path in config.py first

# Scan all buckets and build inventory
python migrate_s3.py scan

# Show current status and progress
python migrate_s3.py status

# Start/resume migration (handles Glacier automatically)
python migrate_s3.py migrate

# View files that encountered errors
python migrate_s3.py errors

# Retry failed files
python migrate_s3.py retry-errors

# Reset database to start fresh (requires confirmation)
python migrate_s3.py reset
```

**Migration workflow:**
1. Edit `config.py` to set `LOCAL_BASE_PATH`
2. Run `scan` to build inventory
3. Run `migrate` - it handles everything automatically:
   - Automatically detects and resets stuck files from interrupted runs
   - Downloads standard files with size and checksum verification
   - Detects and requests Glacier restores (GLACIER, DEEP_ARCHIVE)
   - Waits for restores to complete (checking every 60s)
   - Downloads and verifies all files (including multipart uploads)
   - Deletes from S3 only after successful verification
4. If errors occur, use `errors` to view them and `retry-errors` to retry

**Storage Classes:**
- `STANDARD`, `GLACIER_IR`: Downloaded immediately
- `GLACIER`, `DEEP_ARCHIVE`: Automatically restored, then downloaded
- Multipart uploads verified by size (ETag verification not possible)

**Note:** The migrate command runs continuously until complete. It automatically handles Glacier files without separate commands. You can interrupt anytime (Ctrl+C) and resume later. Interrupted downloads are automatically detected and reset on next run.

### Policy Management

### Display AWS Account Information
```bash
python aws_info.py
```

### Generate Bucket Policies
```bash
# Specific buckets
python block_s3.py bucket1 bucket2

# All buckets
python block_s3.py --all

# Interactive (shows available buckets)
python block_s3.py
```

### Apply Bucket Policies
```bash
# Specific buckets
python apply_block.py bucket1 bucket2

# All available policies
python apply_block.py --all

# Dry run (preview only)
python apply_block.py --all --dry-run

# Interactive (shows available policies)
python apply_block.py
```

## Typical Workflow

1. Run `python aws_info.py` to discover resources
2. Run `python block_s3.py --all` to generate policies for all buckets
3. Run `python apply_block.py --all --dry-run` to preview changes
4. Run `python apply_block.py bucket1 bucket2` to apply selected policies

## Code Organization

- All scripts follow Python best practices with `if __name__ == "__main__"` pattern
- Common functionality is abstracted to `aws_utils.py`
- Policy files are organized in `policies/` directory
- All scripts support argparse for CLI arguments
- No hardcoded values - AWS identity is retrieved dynamically

## Dependencies

- `boto3` - AWS SDK for Python
- AWS credentials configured via environment, CLI, or IAM role
