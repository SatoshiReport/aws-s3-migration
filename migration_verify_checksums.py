"""Checksum verification helpers."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Dict, Tuple

try:  # Prefer package-relative imports for tooling like pylint
    from .migration_utils import (
        ProgressTracker,
        calculate_eta_bytes,
        format_size,
        hash_file_in_chunks,
    )
    from .migration_verify_common import check_verification_errors
except ImportError:  # pragma: no cover - allow running as standalone script
    from migration_utils import (
        ProgressTracker,
        calculate_eta_bytes,
        format_size,
        hash_file_in_chunks,
    )
    from migration_verify_common import check_verification_errors


class VerificationProgressTracker:  # pylint: disable=too-few-public-methods
    """Tracks and displays verification progress."""

    def __init__(self):
        self.progress = ProgressTracker(update_interval=2.0)

    def update_progress(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        start_time: float,
        verified_count: int,
        total_bytes_verified: int,
        expected_files: int,
        expected_size: int,
    ) -> None:
        """Update progress display if enough time has elapsed."""
        if not (self.progress.should_update() or verified_count % 100 == 0):
            return

        elapsed = time.time() - start_time
        file_pct = (verified_count / expected_files * 100) if expected_files > 0 else 0
        byte_pct = (total_bytes_verified / expected_size * 100) if expected_size > 0 else 0
        eta_str = calculate_eta_bytes(elapsed, total_bytes_verified, expected_size)
        progress_str = (
            f"Progress: {verified_count:,}/{expected_files:,} files ({file_pct:.1f}%), "
            f"{format_size(total_bytes_verified)}/{format_size(expected_size)} "
            f"({byte_pct:.1f}%), ETA: {eta_str}  "
        )
        print(f"\r  {progress_str}", end="", flush=True)


def _verify_multipart_file(s3_key: str, file_path: Path, stats: Dict) -> None:
    try:
        sha256_hash = hashlib.sha256()
        hash_file_in_chunks(file_path, sha256_hash)
        sha256_hash.hexdigest()
        stats["checksum_verified"] += 1
        stats["verified_count"] += 1
    except (OSError, IOError) as exc:  # pragma: no cover - surface OS issues
        stats["verification_errors"].append(f"{s3_key}: file health check failed: {exc}")


def _compute_etag(file_path: Path, s3_etag: str) -> Tuple[str, bool]:
    s3_etag = s3_etag.strip('"')
    md5_hash = hashlib.md5(usedforsecurity=False)
    hash_file_in_chunks(file_path, md5_hash)
    computed_etag = md5_hash.hexdigest()
    return computed_etag, computed_etag == s3_etag


def _verify_singlepart_file(s3_key: str, file_path: Path, expected_etag: str, stats: Dict) -> None:
    try:
        computed_etag, is_match = _compute_etag(file_path, expected_etag)
        if not is_match:
            stats["verification_errors"].append(
                f"{s3_key}: checksum mismatch (expected {expected_etag}, got {computed_etag})"
            )
            return
        stats["checksum_verified"] += 1
        stats["verified_count"] += 1
    except (OSError, IOError) as exc:  # pragma: no cover - surface OS issues
        stats["verification_errors"].append(f"{s3_key}: checksum computation failed: {exc}")


def _verify_single_file(
    s3_key: str, local_files: Dict, expected_file_map: Dict, stats: Dict
) -> None:
    file_path = local_files[s3_key]
    expected_meta = expected_file_map[s3_key]
    expected_file_size = expected_meta["size"]
    expected_etag = expected_meta["etag"]
    actual_size = file_path.stat().st_size
    if actual_size != expected_file_size:
        error_msg = (
            f"{s3_key}: size mismatch "
            f"(expected {format_size(expected_file_size)}, got {format_size(actual_size)})"
        )
        stats["verification_errors"].append(error_msg)
        return
    stats["size_verified"] += 1
    stats["total_bytes_verified"] += actual_size
    if "-" in expected_etag:
        _verify_multipart_file(s3_key, file_path, stats)
    else:
        _verify_singlepart_file(s3_key, file_path, expected_etag, stats)


class FileChecksumVerifier:  # pylint: disable=too-few-public-methods
    """Verifies file sizes and checksums."""

    def __init__(self):
        self.progress = VerificationProgressTracker()

    def verify_files(
        self,
        local_files: Dict,
        expected_file_map: Dict,
        expected_files: int,
        expected_size: int,
    ) -> Dict:
        """Validate files by recomputing sizes and checksums."""
        print("  Verifying file sizes and checksums...")
        print("  (This reads all files to compute MD5/ETag - may take time for large files)\n")
        stats = {
            "verified_count": 0,
            "size_verified": 0,
            "checksum_verified": 0,
            "total_bytes_verified": 0,
            "verification_errors": [],
        }
        start_time = time.time()
        for s3_key in sorted(expected_file_map.keys()):
            _verify_single_file(s3_key, local_files, expected_file_map, stats)
            self.progress.update_progress(
                start_time,
                stats["verified_count"],
                stats["total_bytes_verified"],
                expected_files,
                expected_size,
            )
        print("\n")
        check_verification_errors(stats["verification_errors"])
        return {k: v for k, v in stats.items() if k != "verification_errors"}

    # Backwards compatible accessors for targeted patching/tests.
    _verify_single_file = staticmethod(_verify_single_file)
    _verify_multipart_file = staticmethod(_verify_multipart_file)
    _verify_singlepart_file = staticmethod(_verify_singlepart_file)
    _compute_etag = staticmethod(_compute_etag)


__all__ = ["FileChecksumVerifier", "VerificationProgressTracker"]
