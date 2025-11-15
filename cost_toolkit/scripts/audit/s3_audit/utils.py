"""
Utility functions for S3 audit.
Formatting and calculation helpers.
"""

from .constants import STORAGE_CLASS_PRICING


def calculate_monthly_cost(size_bytes, storage_class):
    """Calculate estimated monthly cost for given size and storage class"""
    size_gb = size_bytes / (1024**3)  # Convert bytes to GB
    price_per_gb = STORAGE_CLASS_PRICING.get(storage_class, STORAGE_CLASS_PRICING["STANDARD"])
    return size_gb * price_per_gb


if __name__ == "__main__":  # pragma: no cover - script entry point
    pass
