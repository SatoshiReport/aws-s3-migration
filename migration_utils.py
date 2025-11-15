"""Shared utility functions for migration scripts"""

import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

# Constants for size and time conversions
BYTES_PER_KB = 1024.0
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400


def derive_local_path(base_path: Path, bucket: str, key: str) -> Path | None:
    """
    Convert a bucket/key pair into the expected local filesystem path.

    Args:
        base_path: Base directory containing bucket folders
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Path object if valid, None if path traversal detected
    """
    candidate = base_path / bucket
    for part in PurePosixPath(key).parts:
        if part in ("", "."):
            continue
        if part == "..":
            return None
        candidate /= part
    try:
        candidate.relative_to(base_path)
    except ValueError:
        return None
    return candidate


def format_duration(seconds: float) -> str:
    """Format seconds to human readable duration"""
    if seconds < SECONDS_PER_MINUTE:
        return f"{int(seconds)}s"
    if seconds < SECONDS_PER_HOUR:
        minutes = int(seconds / SECONDS_PER_MINUTE)
        secs = int(seconds % SECONDS_PER_MINUTE)
        return f"{minutes}m {secs}s"
    if seconds < SECONDS_PER_DAY:
        hours = int(seconds / SECONDS_PER_HOUR)
        minutes = int((seconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE)
        return f"{hours}h {minutes}m"
    days = int(seconds / SECONDS_PER_DAY)
    hours = int((seconds % SECONDS_PER_DAY) / SECONDS_PER_HOUR)
    return f"{days}d {hours}h"


def print_verification_success_messages():
    """Print standard verification success messages"""
    print("  ✓ All file sizes verified (exact byte match)")
    print("  ✓ All files verified healthy and readable:")
    print("    - Single-part files: MD5 hash (matches S3 ETag)")
    print("    - Multipart files: SHA256 hash (verifies file integrity)")
    print("    - Every byte of every file was read and hashed")


def get_utc_now() -> str:
    """Get current UTC timestamp as ISO format string"""
    return datetime.now(timezone.utc).isoformat()


def calculate_eta_bytes(elapsed: float, bytes_processed: int, total_bytes: int) -> str:
    """Calculate ETA string based on bytes processed"""
    if bytes_processed > 0 and elapsed > 0:
        throughput = bytes_processed / elapsed
        remaining_bytes = total_bytes - bytes_processed
        eta_seconds = remaining_bytes / throughput
        return format_duration(eta_seconds)
    return "calculating..."


def calculate_eta_items(elapsed: float, items_processed: int, total_items: int) -> str:
    """Calculate ETA string based on items processed"""
    if items_processed > 0 and elapsed > 0:
        rate = items_processed / elapsed
        remaining = max(0, total_items - items_processed)
        if remaining > 0:
            return format_duration(remaining / rate)
        return "complete"
    return "calculating..."


def hash_file_in_chunks(file_path, hash_obj, chunk_size: int = 8 * 1024 * 1024):
    """Read file in chunks and update hash object

    Args:
        file_path: Path to file to hash
        hash_obj: Hash object (e.g., hashlib.md5() or hashlib.sha256())
        chunk_size: Size of chunks to read (default: 8MB)
    """
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hash_obj.update(chunk)


class ProgressTracker:
    """Tracks progress with time-based updates"""

    def __init__(self, update_interval: float = 2.0):
        self.update_interval = update_interval
        self.last_update = time.time()

    def should_update(self, force: bool = False) -> bool:
        """Check if enough time has elapsed to update progress"""
        current_time = time.time()
        if force or current_time - self.last_update >= self.update_interval:
            self.last_update = current_time
            return True
        return False

    def reset(self):
        """Reset the tracker"""
        self.last_update = time.time()
