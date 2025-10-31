# AWS S3 Management Tools

A clean, organized collection of Python scripts for managing AWS S3 buckets, including policy management and complete bucket migration to local storage.

For comprehensive operator and development guidance, see the full documentation in `docs/README.md`.

## Prerequisites

- Python 3.6+
- AWS credentials configured (via AWS CLI, environment variables, or IAM role)
- `boto3` library: `pip install boto3`
- Sufficient local disk space for S3 data migration

## Configuration

**Create `config_local.py`** with your personal settings (not committed to git):

```python
# Local destination directory for all bucket data
LOCAL_BASE_PATH = "/path/to/your/backup/directory"

# Bucket exclusions (optional)
EXCLUDED_BUCKETS = [
    "bucket-to-skip-1",
    "bucket-to-skip-2",
]
```

Other settings (performance tuning, Glacier options) are in `config.py`.

## Scripts

### S3 Migration Tool

**migrate_v2.py** - Optimized S3 bucket migration to local storage using AWS CLI.

**Features:**
- Scans all S3 buckets and builds inventory
- Handles Glacier/Deep Archive with restore requests
- Fast downloads using AWS CLI `aws s3 sync`
- Verifies files locally (size + integrity checks)
- **Deletes all object versions** (handles versioned buckets correctly)
- Only deletes from S3 after manual confirmation per bucket
- Resilient state tracking - can stop/resume anytime
- Processes one bucket fully before moving to next
- Simple, no complex fallback logic
- **99% test coverage** with 600+ comprehensive tests

**Usage:**
```bash
# 1. Create config_local.py with your settings

# 2. Run migration (or check status)
python migrate_v2.py           # Run/resume migration
python migrate_v2.py status    # Show current status
python migrate_v2.py reset     # Reset and start over
```

**Migration automatically:**
1. Scans all buckets and detects Glacier files
2. Requests Glacier restores (90 days)
3. Waits for all Glacier restores to complete
4. For each bucket (one at a time):
   - Downloads using AWS CLI
   - Verifies files locally
   - Deletes from S3 after manual confirmation

**State Tracking:**
- All progress stored in SQLite (`s3_migration_state.db`)
- Can interrupt and resume anytime
- Tracks phases: scanning → glacier_restore → glacier_wait → migrate_buckets → complete
- Each bucket fully completed before moving to next

**Safety:**
- Files only deleted from S3 after local verification
- Manual confirmation required before deletion
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
# 1. Create config_local.py with your settings
# 2. Run migration
python migrate_v2.py
```

The migration runs in phases, handling Glacier restores automatically. You can interrupt anytime with Ctrl+C and resume later.

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
├── migrate_v2.py              # Main migration orchestrator (uses AWS CLI)
├── migration_state_v2.py      # SQLite state management
├── config.py                  # Configuration defaults
├── config_local.py            # Your personal settings (not in git)
├── aws_info.py                # Display AWS account info
├── block_s3.py                # Generate bucket policies
├── apply_block.py             # Apply policies to S3
├── aws_utils.py               # Shared utility functions
├── policies/                  # Generated policy files (not in git)
│   ├── bucket1_policy.json
│   └── bucket2_policy.json
├── s3_migration_state.db      # SQLite database (not in git)
├── tests/                     # 600+ tests with 99% coverage
└── README.md
```

## Recent Improvements

- ✅ **Bucket versioning support**: Deletes all object versions and delete markers (not just current versions)
- ✅ **Security hardening**: Sensitive settings moved to `config_local.py` (not committed to git)
- ✅ **Test coverage**: 600+ comprehensive tests with 99% code coverage
- ✅ **CI/CD pipeline**: Automated testing with pytest, coverage, linting, and type checking

## Security Notes

- **Sensitive data**: Store paths and bucket names in `config_local.py` (already in `.gitignore`)
- Generated policies grant full S3 access (`s3:*`) only to your IAM user
- Always use `--dry-run` to preview changes before applying policies
- Review generated policy files before applying them to production buckets
- Ensure your AWS credentials have appropriate S3 permissions
- Never commit AWS credentials, policy files, or database files
