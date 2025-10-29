# Security & Privacy

This repository contains tools for AWS S3 management. Several types of files are intentionally excluded from version control to protect sensitive information.

## Excluded Files (.gitignore)

### AWS Credentials
- `.aws/` directory
- `*.pem`, `*.key` files
- `credentials`, `credentials.json`
- AWS config files

### Database Files
- `*.db` - SQLite database containing bucket names, file paths, and migration state
- `*.db-journal`, `*.db-shm`, `*.db-wal` - Database journal files

### Policy Files
- `policies/` directory - Contains bucket policies with AWS account IDs and bucket names
- `*.json` files (except template)

### Local Data
- `s3_backup/` - Local directory where S3 files are downloaded

### Standard Exclusions
- Python cache (`__pycache__/`)
- Virtual environments (`venv/`, `env/`)
- IDE settings (`.vscode/`, `.idea/`)
- Environment files (`.env`)
- Log files (`*.log`)

## Safe to Share

The following files are safe to commit and share:

- All Python source code (`.py` files)
- Documentation files (`.md` files)
- `policy_template.json` - Template with placeholder values
- `.gitignore` - Security configuration

## Before Sharing This Repository

If you plan to make this repository public or share it:

1. **Verify no credentials**: Run `git log --all --full-history -- "*credentials*"`
2. **Check for account IDs**: Search for patterns like `arn:aws:iam::[0-9]+:`
3. **Review commit history**: Use `git log --patch` to inspect all changes
4. **Scan for secrets**: Consider using tools like `git-secrets` or `truffleHog`

## AWS Credentials Setup

This tool expects AWS credentials to be configured via:

- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- AWS CLI configuration (`~/.aws/credentials`)
- IAM role (when running on EC2)

**Never commit credentials to version control.**

## Policy Files

To generate bucket policies without exposing your account information:

```bash
# Generate policies (stored in policies/ directory - not committed)
python block_s3.py --all

# Policies contain your AWS account ID and are automatically excluded from git
```

The `policy_template.json` file shows the structure without real values.

## Database Security

The SQLite database (`s3_migration_state.db`) contains:
- Your S3 bucket names
- File paths and keys
- File sizes and metadata

This file is excluded from git. If sharing migration statistics, sanitize bucket/file names first.

## Questions?

If you're unsure whether a file contains sensitive information, err on the side of caution and don't commit it.
