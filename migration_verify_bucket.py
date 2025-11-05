"""Bucket-level verification orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict

try:  # Prefer package-relative imports for tooling like pylint
    from .migration_utils import format_size, print_verification_success_messages
    from .migration_verify_checksums import FileChecksumVerifier
    from .migration_verify_common import (
        LocalPathMissingError,
        VerificationCountMismatchError,
    )
    from .migration_verify_inventory import FileInventoryChecker
except ImportError:  # pragma: no cover - allow running as standalone script
    from migration_utils import format_size, print_verification_success_messages
    from migration_verify_checksums import FileChecksumVerifier
    from migration_verify_common import (
        LocalPathMissingError,
        VerificationCountMismatchError,
    )
    from migration_verify_inventory import FileInventoryChecker

if TYPE_CHECKING:
    try:
        from .migration_state_v2 import MigrationStateV2
    except ImportError:  # pragma: no cover
        from migration_state_v2 import MigrationStateV2


class BucketVerifier:  # pylint: disable=too-few-public-methods
    """Handles verifying bucket files locally."""

    def __init__(self, state: "MigrationStateV2", base_path: Path):
        self.state = state
        self.base_path = base_path
        self.inventory_checker = FileInventoryChecker(state, base_path)
        self.checksum_verifier = FileChecksumVerifier()

    def verify_bucket(self, bucket: str) -> Dict[str, int]:  # pylint: disable=too-many-locals
        """Verify a bucket's files locally with complete integrity checking."""
        bucket_info = self.state.get_bucket_info(bucket)
        expected_files = bucket_info["file_count"]
        expected_size = bucket_info["total_size"]
        local_path = self.base_path / bucket
        if not local_path.exists():
            raise LocalPathMissingError(local_path)
        print(f"  Expected: {expected_files:,} files, {format_size(expected_size)}")
        print()
        expected_file_map = self.inventory_checker.load_expected_files(bucket)
        local_files = self.inventory_checker.scan_local_files(bucket, expected_files)
        expected_keys = set(expected_file_map.keys())
        local_keys = set(local_files.keys())
        self.inventory_checker.check_inventory(expected_keys, local_keys)
        print(f"  ✓ All {expected_files:,} files present (no missing or extra files)")
        print()
        verify_results = self.checksum_verifier.verify_files(
            local_files, expected_file_map, expected_files, expected_size
        )
        verified_count = verify_results["verified_count"]
        size_verified = verify_results["size_verified"]
        checksum_verified = verify_results["checksum_verified"]
        total_bytes_verified = verify_results["total_bytes_verified"]

        # Calculate ignored system files
        ignored_count = len(local_files) - expected_files

        print(f"  S3 files:             {expected_files:,}")
        print(f"  Verified files:       {verified_count:,}")
        print(f"  - Size verified:      {size_verified:,}")
        print(f"  - Checksum verified:  {checksum_verified:,}")
        if ignored_count > 0:
            print()
            print(f"  (Ignored {ignored_count:,} system metadata files: .DS_Store, etc.)")
        print()
        if verified_count != expected_files:
            raise VerificationCountMismatchError(verified_count, expected_files)
        print(f"  ✓ All {verified_count:,} files verified successfully")
        print_verification_success_messages()
        print(f"  ✓ Total size: {format_size(bucket_info['total_size'])}")
        print()
        return {
            "verified_count": verified_count,
            "size_verified": size_verified,
            "checksum_verified": checksum_verified,
            "total_bytes_verified": total_bytes_verified,
            "local_file_count": len(local_files),
        }


__all__ = ["BucketVerifier"]
