"""Bucket-level verification orchestration."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Dict

_PACKAGE_PREFIX = f"{__package__}." if __package__ else ""
_migration_utils = import_module(f"{_PACKAGE_PREFIX}migration_utils")
_migration_verify_checksums = import_module(f"{_PACKAGE_PREFIX}migration_verify_checksums")
_migration_verify_common = import_module(f"{_PACKAGE_PREFIX}migration_verify_common")
_migration_verify_inventory = import_module(f"{_PACKAGE_PREFIX}migration_verify_inventory")
_format_utils = import_module("cost_toolkit.common.format_utils")

format_bytes = _format_utils.format_bytes
print_verification_success_messages = _migration_utils.print_verification_success_messages
FileChecksumVerifier = _migration_verify_checksums.FileChecksumVerifier
LocalPathMissingError = _migration_verify_common.LocalPathMissingError
VerificationCountMismatchError = _migration_verify_common.VerificationCountMismatchError
FileInventoryChecker = _migration_verify_inventory.FileInventoryChecker

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
        expected_size_str = format_bytes(expected_size, binary_units=False)
        print(f"  Expected: {expected_files:,} files, {expected_size_str}")
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
        print(f"  ✓ Total size: {format_bytes(bucket_info['total_size'], binary_units=False)}")
        print()
        return {
            "verified_count": verified_count,
            "size_verified": size_verified,
            "checksum_verified": checksum_verified,
            "total_bytes_verified": total_bytes_verified,
            "local_file_count": len(local_files),
        }


__all__ = ["BucketVerifier"]
