# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a personal AWS S3 bucket management repository containing Python scripts for:
1. **S3 Migration**: Complete bucket migration to local storage with resilience and Glacier support
2. **Policy Management**: Managing S3 bucket policies and AWS account information

All scripts use shared utility functions and support command-line arguments for flexible operation.

## Architecture

### S3 Migration System

The migration system uses AWS CLI for optimized downloads:

**migrate_v2.py** - Main orchestrator using AWS CLI `aws s3 sync`:
- Scans all buckets and builds inventory
- Handles Glacier restores automatically
- Downloads using AWS CLI (faster than boto3)
- Verifies locally and deletes after confirmation
- Processes one bucket fully before moving to next

**State Management (migration_state_v2.py)**:
- SQLite database tracks migration phases
- Phases: scanning → glacier_restore → glacier_wait → migrate_buckets → complete
- Each bucket tracked: pending → syncing → verifying → deleting → completed
- Enables instant resumption after interruption

**Core Components**:
- `migrate_v2.py` - All-in-one orchestrator (scan, restore, download, verify)
- `migration_state_v2.py` - Phase and bucket state management
- `config.py` - Configuration (LOCAL_BASE_PATH, Glacier settings, etc.)

**Key Design Principles**:
1. Safety first: Only delete from S3 after verified local copy
2. Resilience: Can stop/resume at any time via state DB
3. Simplicity: No complex fallback logic, straightforward phases
4. Performance: AWS CLI sync for optimized downloads

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

# Run/resume migration (handles everything automatically)
python migrate_v2.py

# Show current status and progress
python migrate_v2.py status

# Reset database to start fresh (requires confirmation)
python migrate_v2.py reset
```

**Migration workflow:**
1. Edit `config.py` to set `LOCAL_BASE_PATH`
2. Run `python migrate_v2.py` - it handles everything automatically in phases:
   - **Phase 1 (Scanning)**: Discovers all files across all buckets
   - **Phase 2 (Glacier Restore)**: Requests restores for GLACIER/DEEP_ARCHIVE files
   - **Phase 3 (Glacier Wait)**: Waits for all restores to complete
   - **Phase 4 (Migrate Buckets)**: For each bucket:
     - Downloads using AWS CLI `aws s3 sync`
     - Verifies all files (size + integrity checks)
     - Deletes from S3 after manual confirmation
     - Moves to next bucket only after current bucket is complete

**Storage Classes:**
- `STANDARD`, `GLACIER_IR`: Downloaded immediately in Phase 4
- `GLACIER`, `DEEP_ARCHIVE`: Restored in Phases 2-3, downloaded in Phase 4
- Multipart uploads verified by size (ETag verification not possible)

**Note:** The migration runs continuously through all phases. You can interrupt anytime (Ctrl+C) and resume later. State is saved after each phase and after each bucket completion.

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
