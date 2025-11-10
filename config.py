"""
Configuration for S3 migration script.

Performance Optimizations:
- Parallel downloads with ThreadPoolExecutor (10 concurrent workers by default)
- S3 Transfer Manager for optimized multipart downloads of large files
- Batch processing (50 files per batch) with no artificial delays
- Thread-safe database operations with proper locking
- Reduced progress update frequency to minimize overhead
"""

# Local destination directory for all bucket data
# Set this in config_local.py (not committed to git)
LOCAL_BASE_PATH: str = "/path/to/your/backup/directory"  # Default - override in config_local.py
try:
    from config_local import LOCAL_BASE_PATH as _LOCAL_BASE_PATH_OVERRIDE

    LOCAL_BASE_PATH = _LOCAL_BASE_PATH_OVERRIDE
except ImportError:
    pass

# State database location
STATE_DB_PATH: str = "s3_migration_state.db"

# Glacier restore settings
GLACIER_RESTORE_DAYS: int = 1  # Days to keep restored file available
GLACIER_RESTORE_TIER: str = "Standard"  # Options: Expedited, Standard, Bulk

# Progress update interval (seconds) - increased for less overhead with parallel processing
PROGRESS_UPDATE_INTERVAL: int = 5

# Maximum concurrent Glacier restore requests
MAX_GLACIER_RESTORES: int = 100

# Chunk size for downloads (bytes) - 8MB
DOWNLOAD_CHUNK_SIZE: int = 8 * 1024 * 1024

# Parallel download settings
MAX_CONCURRENT_DOWNLOADS: int = (
    100  # Number of simultaneous file downloads (optimized for network throughput)
)
MAX_CONCURRENT_VERIFICATIONS: int = 5  # Number of simultaneous file verifications

# Batch processing settings
BATCH_SIZE: int = 200  # Number of files to process per batch (increased for better throughput)
DB_BATCH_COMMIT_SIZE: int = 20  # Number of state updates to batch before committing

# S3 Transfer Manager settings (for large file multipart transfers)
MULTIPART_THRESHOLD: int = 8 * 1024 * 1024  # 8MB - files larger than this use multipart
MULTIPART_CHUNKSIZE: int = 8 * 1024 * 1024  # 8MB - size of each part
MAX_CONCURRENCY: int = 10  # Number of threads for multipart transfers
USE_THREADS: bool = True  # Use threads for S3 transfers

# Bucket exclusions (optional)
# Set this in config_local.py (not committed to git)
# Add bucket names to skip during scanning (e.g., buckets you don't own or can't access)
EXCLUDED_BUCKETS: list[str] = []  # Default - override in config_local.py
try:
    from config_local import EXCLUDED_BUCKETS as _EXCLUDED_BUCKETS_OVERRIDE

    EXCLUDED_BUCKETS = _EXCLUDED_BUCKETS_OVERRIDE
except ImportError:
    pass
