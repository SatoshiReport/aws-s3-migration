"""Shared utility functions for migration scripts"""


def format_size(bytes_size: int) -> str:
    """Format bytes to human readable size"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def format_duration(seconds: float) -> str:
    """Format seconds to human readable duration"""
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    if seconds < 86400:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"
    days = int(seconds / 86400)
    hours = int((seconds % 86400) / 3600)
    return f"{days}d {hours}h"


def print_verification_success_messages():
    """Print standard verification success messages"""
    print("  ✓ All file sizes verified (exact byte match)")
    print("  ✓ All files verified healthy and readable:")
    print("    - Single-part files: MD5 hash (matches S3 ETag)")
    print("    - Multipart files: SHA256 hash (verifies file integrity)")
    print("    - Every byte of every file was read and hashed")
