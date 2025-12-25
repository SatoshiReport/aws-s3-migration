"""Shared constants and error helpers for migration verification."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

MAX_ERROR_DISPLAY = 10  # Maximum number of errors to display before truncating

# System files to ignore during verification (not stored in S3, created by OS)
IGNORED_FILE_PATTERNS = [
    ".DS_Store",  # macOS Finder metadata
    "._.DS_Store",  # macOS resource fork for .DS_Store
    "Thumbs.db",  # Windows thumbnail cache
    "desktop.ini",  # Windows folder settings
    ".Spotlight-V100",  # macOS Spotlight index (should be caught by directory filter)
    ".TemporaryItems",  # macOS temporary items
    ".Trashes",  # macOS trash
]


class VerificationFailedError(ValueError):
    """Raised when verification issues prevent migration progression."""

    def __init__(self, error_count: int) -> None:
        super().__init__(f"Verification failed: {error_count} file(s) with issues")


class LocalPathMissingError(FileNotFoundError):
    """Raised when the expected local bucket directory cannot be located."""

    def __init__(self, missing_path: Path) -> None:
        super().__init__(f"Local path does not exist: {missing_path}")


class VerificationCountMismatchError(ValueError):
    """Raised when verified file counts do not align with expectations."""

    def __init__(self, verified: int, expected: int) -> None:
        message = f"File count mismatch: {verified} verified vs {expected} expected"
        super().__init__(message)


class BucketNotEmptyError(RuntimeError):
    """Raised when S3 bucket cleanup leaves residual objects."""

    def __init__(self) -> None:
        super().__init__("Bucket still contains objects after delete pass. Re-run deletion once remaining versions are cleared.")


def should_ignore_key(key: str) -> bool:
    """Return True when the key points at a known system file."""
    file_name = key.split("/")[-1]
    return any(file_name == pattern or file_name.endswith(pattern) for pattern in IGNORED_FILE_PATTERNS)


def check_verification_errors(verification_errors: Sequence[str]) -> None:
    """Print summarized errors and raise when verification failed."""
    if not verification_errors:
        return

    print("  ✗ VERIFICATION FAILED:")
    for error in list(verification_errors)[:MAX_ERROR_DISPLAY]:
        print(f"    - {error}")

    remaining = len(verification_errors) - MAX_ERROR_DISPLAY
    if remaining > 0:
        print(f"    ... and {remaining} more errors")

    print()
    raise VerificationFailedError(len(verification_errors))


__all__ = [
    "IGNORED_FILE_PATTERNS",
    "MAX_ERROR_DISPLAY",
    "VerificationFailedError",
    "LocalPathMissingError",
    "VerificationCountMismatchError",
    "BucketNotEmptyError",
    "should_ignore_key",
    "check_verification_errors",
]
