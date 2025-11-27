"""
Configuration for S3 migration script.

Performance Optimizations:
- Parallel downloads with ThreadPoolExecutor (10 concurrent workers by default)
- S3 Transfer Manager for optimized multipart downloads of large files
- Batch processing (50 files per batch) with no artificial delays
- Thread-safe database operations with proper locking
- Reduced progress update frequency to minimize overhead
"""

# Re-exported from config_local for use by other modules
__all__ = ["LOCAL_BASE_PATH", "EXCLUDED_BUCKETS"]

# Local destination directory for all bucket data
# Set this in config_local.py (not committed to git)
try:
    from config_local import LOCAL_BASE_PATH
except ImportError as exc:
    raise ImportError(
        "config_local.py is required. Create config_local.py with LOCAL_BASE_PATH defined. "
        "Example: LOCAL_BASE_PATH = '/path/to/your/backup/directory'"
    ) from exc

# State database location
STATE_DB_PATH: str = "s3_migration_state.db"

# Glacier restore settings
GLACIER_RESTORE_DAYS: int = 1  # Days to keep restored file available
GLACIER_RESTORE_TIER: str = "Standard"  # Options: Expedited, Standard, Bulk

# Bucket exclusions
# Set this in config_local.py (not committed to git)
# Add bucket names to skip during scanning (e.g., buckets you don't own or can't access)
try:
    from config_local import EXCLUDED_BUCKETS
except ImportError as exc:
    raise ImportError(
        "config_local.py must define EXCLUDED_BUCKETS (can be empty list []). "
        "Example: EXCLUDED_BUCKETS = []"
    ) from exc
