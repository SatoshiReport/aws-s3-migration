# AWS S3 Management Tools

A clean, organized collection of Python scripts for managing AWS S3 buckets, including policy management and complete bucket migration to local storage.

## Prerequisites

- Python 3.6+
- AWS credentials configured (via AWS CLI, environment variables, or IAM role)
- `boto3` library: `pip install boto3`
- Sufficient local disk space for S3 data migration

## Configuration

Edit `config.py` to set your local destination path:
```python
LOCAL_BASE_PATH = os.path.expanduser("~/s3_backup")
```

## Scripts

### S3 Migration Tool (NEW)

**migrate_s3.py** - Complete S3 bucket migration to local storage with resilience and verification.

**Features:**
- Scans all S3 buckets and builds inventory
- Handles Glacier/Deep Archive with restore requests
- Downloads files with verification (ETag/MD5)
- Only deletes from S3 after successful verification
- Resilient state tracking - can stop/resume anytime
- Live progress display with ETA
- Simple, no complex fallback logic

**Usage:**
```bash
# 1. Configure destination in config.py

# 2. Scan all buckets to build inventory
python migrate_s3.py scan

# 3. Check status
python migrate_s3.py status

# 4. Start migration (can stop/resume anytime)
# Automatically handles Glacier files!
python migrate_s3.py migrate

# Optional: Reset database to start fresh
python migrate_s3.py reset
```

**That's it!** The migrate command automatically:
- Downloads standard storage files
- Detects Glacier files and requests restores
- Waits for Glacier restores to complete
- Downloads and verifies everything
- Deletes from S3 only after verification

**State Tracking:**
- All progress stored in SQLite (`s3_migration_state.db`)
- Can interrupt and resume anytime
- Each file tracked through: discovered → downloading → downloaded → verified → deleted
- Glacier files: discovered → glacier_restore_requested → glacier_restoring → downloaded → verified → deleted

**Safety:**
- Files only deleted from S3 after local verification
- Corrupted downloads detected and retried
- No data loss if interrupted

### Policy Management Tools

### 1. aws_info.py

Display AWS account information and list all S3 buckets.

```bash
python aws_info.py
```

**Output:**
- AWS Account ID
- IAM username and ARN
- List of all S3 buckets

### 2. block_s3.py

Generate restrictive S3 bucket policies that allow access only to your IAM user.

```bash
# Generate policies for specific buckets
python block_s3.py bucket1 bucket2 bucket3

# Generate policies for all buckets in your account
python block_s3.py --all

# Interactive mode (shows available buckets)
python block_s3.py
```

Policies are saved to the `policies/` directory.

### 3. apply_block.py

Apply generated bucket policies to S3 buckets.

```bash
# Apply policy to specific bucket(s)
python apply_block.py bucket1 bucket2

# Apply all available policies
python apply_block.py --all

# Dry run (preview without making changes)
python apply_block.py --all --dry-run

# Interactive mode (shows available policy files)
python apply_block.py
```

## Typical Workflows

### S3 Migration Workflow

```bash
# 1. Configure destination in config.py
# 2. Scan buckets
python migrate_s3.py scan

# 3. Start migration (handles everything automatically)
python migrate_s3.py migrate
```

The migrate command runs continuously, handling Glacier restores automatically. You can interrupt anytime with Ctrl+C and resume later.

### Policy Management Workflow

1. **Discover your AWS resources:**
   ```bash
   python aws_info.py
   ```

2. **Generate restrictive policies:**
   ```bash
   python block_s3.py --all
   ```

3. **Review and apply policies:**
   ```bash
   # Preview changes
   python apply_block.py --all --dry-run

   # Apply to specific buckets
   python apply_block.py important-bucket1 important-bucket2
   ```

## Directory Structure

```
aws/
├── migrate_s3.py              # Main migration orchestrator
├── config.py                  # Configuration (set LOCAL_BASE_PATH here)
├── migration_state.py         # SQLite state management
├── s3_scanner.py              # S3 bucket scanner
├── file_migrator.py           # Download/verify/delete handler
├── glacier_handler.py         # Glacier restore management
├── progress_tracker.py        # Progress display with ETA
├── aws_info.py                # Display AWS account info
├── block_s3.py                # Generate bucket policies
├── apply_block.py             # Apply policies to S3
├── aws_utils.py               # Shared utility functions
├── policies/                  # Generated policy files
│   ├── bucket1_policy.json
│   └── bucket2_policy.json
├── s3_migration_state.db      # SQLite database (created on first run)
└── README.md
```

## Security Notes

- Generated policies grant full S3 access (`s3:*`) only to your IAM user
- Always use `--dry-run` to preview changes before applying policies
- Review generated policy files before applying them to production buckets
- Ensure your AWS credentials have appropriate S3 permissions
