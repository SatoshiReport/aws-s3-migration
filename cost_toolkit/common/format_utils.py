"""
Shared formatting utilities for consistent output across the codebase.

This module provides canonical implementations for common formatting tasks
like byte size formatting and parsing, eliminating duplicate code.
"""

import argparse
from typing import Optional

# Canonical byte size constants
BYTES_PER_KIB = 1024
BYTES_PER_MIB = 1024**2
BYTES_PER_GIB = 1024**3
BYTES_PER_TIB = 1024**4
MIN_PARTS_WITH_UNIT = 2


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

    if use_comma_separators:
        return f"{value:,.{decimal_places}f} PiB"
    return f"{value:.{decimal_places}f} PiB"


def parse_size(value: str, *, for_argparse: bool = False) -> int:
    """
    Parse human-readable size strings (e.g., 512M, 2G) into bytes.

    This is the canonical size parsing function. All code should use this
    instead of implementing their own parsers.

    Args:
        value: Size string like "10G", "512M", "2048k", "1.5T"
        for_argparse: If True, raise argparse.ArgumentTypeError on invalid input

    Returns:
        Number of bytes as integer

    Raises:
        ValueError: If the size string is invalid (when for_argparse=False)
        argparse.ArgumentTypeError: If invalid and for_argparse=True

    Examples:
        >>> parse_size("512M")
        536870912
        >>> parse_size("2G")
        2147483648
        >>> parse_size("1.5T")
        1649267441664
        >>> parse_size("1024")  # No suffix = bytes
        1024
        >>> parse_size("invalid")
        Traceback (most recent call last):
        ...
        ValueError: Invalid size value: invalid
    """
    raw = value.strip()
    if not raw:
        error_msg = "Size cannot be empty"
        if for_argparse:
            raise argparse.ArgumentTypeError(error_msg)
        raise ValueError(error_msg)

    bytes_per_unit = 1024
    # Support both uppercase and lowercase suffixes
    multipliers = {
        "k": bytes_per_unit,
        "m": bytes_per_unit**2,
        "g": bytes_per_unit**3,
        "t": bytes_per_unit**4,
    }

    suffix = raw[-1].lower()
    if suffix in multipliers:
        number_part = raw[:-1]
        try:
            base = float(number_part)
        except ValueError as exc:
            error_msg = f"Invalid size value: {value}"
            if for_argparse:
                raise argparse.ArgumentTypeError(error_msg) from exc
            raise ValueError(error_msg) from exc
        return int(base * multipliers[suffix])

    # No suffix, treat as bytes
    try:
        return int(raw)
    except ValueError as exc:
        error_msg = f"Invalid size value: {value}"
        if for_argparse:
            raise argparse.ArgumentTypeError(error_msg) from exc
        raise ValueError(error_msg) from exc


def _to_float(value: str, original: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Cannot parse size: {original}") from exc


def _parse_compact_size(raw: str, multipliers: dict[str, int]) -> tuple[str, str]:
    lower_raw = raw.lower()
    for suffix in multipliers:
        if lower_raw.endswith(suffix):
            return raw[: -len(suffix)], suffix
    return raw, "bytes"


def _split_size_components(raw: str, multipliers: dict[str, int]) -> tuple[str, str]:
    parts = raw.split()
    if len(parts) >= MIN_PARTS_WITH_UNIT:
        return parts[0], parts[-1].lower()
    if len(parts) == 1:
        return _parse_compact_size(raw, multipliers)
    raise ValueError(f"Cannot parse size: {raw}")


def parse_aws_cli_size(size_str: str) -> int:
    """
    Parse byte size from AWS CLI output format (e.g., "1.5 GiB", "512 MiB").

    This is the canonical parser for AWS CLI size output. Use this instead of
    implementing your own parser for AWS CLI output parsing.

    Args:
        size_str: Size string from AWS CLI like "1.5 GiB", "512 MiB", "1024 KiB"

    Returns:
        Number of bytes as integer

    Raises:
        ValueError: If the size string cannot be parsed

    Examples:
        >>> parse_aws_cli_size("1.5 GiB")
        1610612736
        >>> parse_aws_cli_size("512 MiB")
        536870912
        >>> parse_aws_cli_size("1024 KiB")
        1048576
    """
    raw = size_str.strip()
    if not raw:
        raise ValueError("Size string cannot be empty")

    multipliers = {
        "kib": BYTES_PER_KIB,
        "mib": BYTES_PER_MIB,
        "gib": BYTES_PER_GIB,
        "tib": BYTES_PER_TIB,
    }

    try:
        number_part, unit_part = _split_size_components(raw, multipliers)
    except ValueError as exc:
        raise ValueError(f"Cannot parse size: {size_str}") from exc

    size_val = _to_float(number_part, size_str)

    if unit_part in multipliers:
        return int(size_val * multipliers[unit_part])

    if unit_part == "bytes":
        return int(size_val)

    raise ValueError(f"Unknown size unit in: {size_str}")
