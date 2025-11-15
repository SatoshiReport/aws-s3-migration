"""
Shared formatting utilities for consistent output across the codebase.

This module provides canonical implementations for common formatting tasks
like byte size formatting, eliminating duplicate code.
"""

from typing import Optional


def format_bytes(
    num_bytes: Optional[int],
    decimal_places: int = 2,
    use_comma_separators: bool = False,
    binary_units: bool = True,
) -> str:
    """
    Format byte count as human-readable string with appropriate units.

    This is the canonical byte formatting function. All code should use this
    instead of implementing their own formatters.

    Args:
        num_bytes: Number of bytes to format (None returns "n/a")
        decimal_places: Number of decimal places to display (default: 2)
        use_comma_separators: Add comma separators to numbers (default: False)
        binary_units: Use binary units (KiB) vs decimal (KB) (default: True)

    Returns:
        Formatted string like "1.23 MiB" or "456.78 MB"

    Examples:
        >>> format_bytes(1024)
        '1.00 KiB'
        >>> format_bytes(1536, decimal_places=1)
        '1.5 KiB'
        >>> format_bytes(1048576, use_comma_separators=True)
        '1,024.00 KiB'
        >>> format_bytes(None)
        'n/a'
        >>> format_bytes(1024, binary_units=False)
        '1.00 KB'
    """
    if num_bytes is None:
        return "n/a"

    # Choose unit labels based on binary_units flag
    if binary_units:
        units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    else:
        units = ["B", "KB", "MB", "GB", "TB", "PB"]

    divisor = 1024
    value = float(num_bytes)

    for unit in units:
        if value < divisor or unit == units[-1]:
            if use_comma_separators:
                return f"{value:,.{decimal_places}f} {unit}"
            return f"{value:.{decimal_places}f} {unit}"
        value /= divisor

    # Fallback (should never reach here due to units[-1] check)
    if use_comma_separators:
        return f"{value:,.{decimal_places}f} PiB"
    return f"{value:.{decimal_places}f} PiB"


# Convenience aliases for backward compatibility
format_size = format_bytes
