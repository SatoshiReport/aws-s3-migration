"""
Utility functions for S3 audit.
Formatting and calculation helpers.
"""

from .constants import BYTES_PER_KB, STORAGE_CLASS_PRICING


def calculate_monthly_cost(size_bytes, storage_class):
    """Calculate estimated monthly cost for given size and storage class"""
    size_gb = size_bytes / (1024**3)  # Convert bytes to GB
    price_per_gb = STORAGE_CLASS_PRICING.get(storage_class, STORAGE_CLASS_PRICING["STANDARD"])
    return size_gb * price_per_gb


def format_bytes(bytes_value):
    """Format bytes into human readable format"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < BYTES_PER_KB:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= BYTES_PER_KB
    return f"{bytes_value:.2f} PB"
