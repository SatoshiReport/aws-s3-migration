"""Bucket verification and deletion façade.

This module re-exports the primary verification/deletion utilities so callers
can continue importing from `migration_verify` while the implementation lives
in smaller, focused modules.
"""

from __future__ import annotations

try:  # Prefer package-relative imports for tooling like pylint
    from . import migration_verify_common as _common
    from .migration_verify_bucket import BucketVerifier
    from .migration_verify_checksums import FileChecksumVerifier, VerificationProgressTracker
    from .migration_verify_delete import BucketDeleter
    from .migration_verify_inventory import FileInventoryChecker
except ImportError:  # pragma: no cover - allow running as standalone script
    import migration_verify_common as _common
    from migration_verify_bucket import BucketVerifier
    from migration_verify_checksums import FileChecksumVerifier, VerificationProgressTracker
    from migration_verify_delete import BucketDeleter
    from migration_verify_inventory import FileInventoryChecker

MAX_ERROR_DISPLAY = _common.MAX_ERROR_DISPLAY
IGNORED_FILE_PATTERNS = list(_common.IGNORED_FILE_PATTERNS)
VerificationFailedError = _common.VerificationFailedError
LocalPathMissingError = _common.LocalPathMissingError
VerificationCountMismatchError = _common.VerificationCountMismatchError
BucketNotEmptyError = _common.BucketNotEmptyError
check_verification_errors = _common.check_verification_errors
should_ignore_key = _common.should_ignore_key

__all__ = [
    "BucketDeleter",
    "BucketVerifier",
    "FileChecksumVerifier",
    "FileInventoryChecker",
    "IGNORED_FILE_PATTERNS",
    "LocalPathMissingError",
    "BucketNotEmptyError",
    "MAX_ERROR_DISPLAY",
    "VerificationCountMismatchError",
    "VerificationFailedError",
    "VerificationProgressTracker",
    "check_verification_errors",
    "should_ignore_key",
]
