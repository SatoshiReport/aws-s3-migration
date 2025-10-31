"""Bucket verification and deletion components"""

import hashlib
import time
from pathlib import Path
from typing import Dict, List, Tuple

from migration_state_v2 import MigrationStateV2
from migration_utils import format_duration, format_size, print_verification_success_messages


class FileInventoryChecker:  # pylint: disable=too-few-public-methods
    """Checks local file inventory against expected files"""

    def __init__(self, state: MigrationStateV2, base_path: Path):
        self.state = state
        self.base_path = base_path

    def load_expected_files(self, bucket: str) -> Dict[str, Dict]:
        """Load file metadata from database"""
        print("  Loading file metadata from database...")
        expected_file_map = {}
        with self.state.db_conn.get_connection() as conn:
            cursor = conn.execute("SELECT key, size, etag FROM files WHERE bucket = ?", (bucket,))
            for row in cursor:
                normalized_key = row["key"].replace("\\", "/")
                expected_file_map[normalized_key] = {"size": row["size"], "etag": row["etag"]}
        print(f"  Loaded {len(expected_file_map):,} file records")
        print()
        return expected_file_map

    def scan_local_files(self, bucket: str, expected_files: int) -> Dict[str, Path]:
        """Scan local directory for files"""
        print("  Scanning local files...")
        local_path = self.base_path / bucket
        local_files = {}
        scan_count = 0
        last_update = time.time()
        for file_path in local_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_path)
                s3_key = str(relative_path).replace("\\", "/")
                local_files[s3_key] = file_path
                scan_count += 1
                current_time = time.time()
                if current_time - last_update >= 2 or scan_count % 10000 == 0:
                    pct = (scan_count / expected_files * 100) if expected_files > 0 else 0
                    status = f"Scanned: {scan_count:,} files ({pct:.1f}%)  "
                    print(f"\r  {status}", end="", flush=True)
                    last_update = current_time
        print(f"\r  Found {len(local_files):,} local files" + " " * 30)
        print()
        return local_files

    def check_inventory(self, expected_keys: set, local_keys: set) -> List[str]:
        """Check for missing or extra files"""
        print("  Checking file inventory...")
        missing_files = expected_keys - local_keys
        extra_files = local_keys - expected_keys
        errors = []
        if missing_files:
            for key in list(missing_files)[:10]:
                errors.append(f"Missing file: {key}")
            if len(missing_files) > 10:
                errors.append(f"... and {len(missing_files) - 10} more missing files")
        if extra_files:
            for key in list(extra_files)[:10]:
                errors.append(f"Extra file (not in S3): {key}")
            if len(extra_files) > 10:
                errors.append(f"... and {len(extra_files) - 10} more extra files")
        if errors:
            print("  ✗ File inventory mismatch:")
            for error in errors:
                print(f"    - {error}")
            print()
            msg = (
                f"File inventory check failed: "
                f"{len(missing_files)} missing, {len(extra_files)} extra"
            )
            raise ValueError(msg)
        return errors


class VerificationProgressTracker:  # pylint: disable=too-few-public-methods
    """Tracks and displays verification progress"""

    def update_progress(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        start_time,
        last_update,
        verified_count,
        total_bytes_verified,
        expected_files,
        expected_size,
    ):
        """Update progress display if enough time has elapsed"""
        current_time = time.time()
        if current_time - last_update >= 2 or verified_count % 100 == 0:
            elapsed = current_time - start_time
            file_pct = (verified_count / expected_files * 100) if expected_files > 0 else 0
            byte_pct = (total_bytes_verified / expected_size * 100) if expected_size > 0 else 0
            eta_str = self._calculate_eta(elapsed, total_bytes_verified, expected_size)
            progress = (
                f"Progress: {verified_count:,}/{expected_files:,} files ({file_pct:.1f}%), "
                f"{format_size(total_bytes_verified)}/{format_size(expected_size)} "
                f"({byte_pct:.1f}%), ETA: {eta_str}  "
            )
            print(
                f"\r  {progress}",
                end="",
                flush=True,
            )
            return current_time
        return last_update

    def _calculate_eta(self, elapsed, total_bytes_verified, expected_size):
        """Calculate ETA string"""
        if total_bytes_verified > 0 and elapsed > 0:
            throughput = total_bytes_verified / elapsed
            remaining_bytes = expected_size - total_bytes_verified
            eta_seconds = remaining_bytes / throughput
            return format_duration(eta_seconds)
        return "calculating..."


class FileChecksumVerifier:  # pylint: disable=too-few-public-methods
    """Verifies file sizes and checksums"""

    def __init__(self):
        self.progress = VerificationProgressTracker()

    def verify_files(
        self, local_files: Dict, expected_file_map: Dict, expected_files: int, expected_size: int
    ) -> Dict:
        """Verify all files' sizes and checksums"""
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
        last_update = start_time
        expected_keys = set(expected_file_map.keys())
        for s3_key in sorted(expected_keys):
            self._verify_single_file(s3_key, local_files, expected_file_map, stats)
            last_update = self.progress.update_progress(
                start_time,
                last_update,
                stats["verified_count"],
                stats["total_bytes_verified"],
                expected_files,
                expected_size,
            )
        print("\n")
        self._check_verification_errors(stats["verification_errors"])
        return {k: v for k, v in stats.items() if k != "verification_errors"}

    def _verify_single_file(
        self, s3_key: str, local_files: Dict, expected_file_map: Dict, stats: Dict
    ):
        """Verify a single file's size and checksum"""
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
            self._verify_multipart_file(s3_key, file_path, stats)
        else:
            self._verify_singlepart_file(s3_key, file_path, expected_etag, stats)

    def _verify_multipart_file(self, s3_key: str, file_path: Path, stats: Dict):
        """Verify multipart file with SHA256"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
                    sha256_hash.update(chunk)
            sha256_hash.hexdigest()
            stats["checksum_verified"] += 1
            stats["verified_count"] += 1
        except (OSError, IOError) as e:
            stats["verification_errors"].append(f"{s3_key}: file health check failed: {e}")

    def _verify_singlepart_file(
        self, s3_key: str, file_path: Path, expected_etag: str, stats: Dict
    ):
        """Verify single-part file with MD5"""
        try:
            computed_etag, is_match = self._compute_etag(file_path, expected_etag)
            if not is_match:
                stats["verification_errors"].append(
                    f"{s3_key}: checksum mismatch (expected {expected_etag}, got {computed_etag})"
                )
                return
            stats["checksum_verified"] += 1
            stats["verified_count"] += 1
        except (OSError, IOError) as e:
            stats["verification_errors"].append(f"{s3_key}: checksum computation failed: {e}")

    def _check_verification_errors(self, verification_errors):
        """Check and report verification errors"""
        if verification_errors:
            print("  ✗ VERIFICATION FAILED:")
            for error in verification_errors[:10]:
                print(f"    - {error}")
            if len(verification_errors) > 10:
                print(f"    ... and {len(verification_errors) - 10} more errors")
            print()
            raise ValueError(f"Verification failed: {len(verification_errors)} file(s) with issues")

    def _compute_etag(self, file_path: Path, s3_etag: str) -> Tuple[str, bool]:
        """Compute ETag for a single-part upload (simple MD5 hash)"""
        s3_etag = s3_etag.strip('"')
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
                md5_hash.update(chunk)
        computed_etag = md5_hash.hexdigest()
        return computed_etag, computed_etag == s3_etag


class BucketVerifier:  # pylint: disable=too-few-public-methods
    """Handles verifying bucket files locally"""

    def __init__(self, state: MigrationStateV2, base_path: Path):
        self.state = state
        self.base_path = base_path
        self.inventory_checker = FileInventoryChecker(state, base_path)
        self.checksum_verifier = FileChecksumVerifier()

    def verify_bucket(self, bucket: str):  # pylint: disable=too-many-locals
        """Verify a bucket's files locally with complete integrity checking"""
        bucket_info = self.state.get_bucket_info(bucket)
        expected_files = bucket_info["file_count"]
        expected_size = bucket_info["total_size"]
        local_path = self.base_path / bucket
        if not local_path.exists():
            raise FileNotFoundError("Local path does not exist")
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
        print(f"  Files in S3:          {expected_files:,}")
        print(f"  Files found locally:  {len(local_files):,}")
        print(f"  Size verified:        {size_verified:,} files")
        print(f"  Checksum verified:    {checksum_verified:,} files")
        print(f"  Total verified:       {verified_count:,} files")
        print()
        if verified_count != expected_files:
            raise ValueError(
                f"File count mismatch: {verified_count} verified vs {expected_files} expected"
            )
        print(f"  ✓ File count matches: {verified_count:,} files")
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


class BucketDeleter:  # pylint: disable=too-few-public-methods
    """Handles deleting bucket from S3"""

    def __init__(self, s3, state: MigrationStateV2):
        self.s3 = s3
        self.state = state

    def delete_bucket(self, bucket: str):  # pylint: disable=too-many-locals
        """Delete a bucket and all its contents from S3"""
        bucket_info = self.state.get_bucket_info(bucket)
        total_objects = bucket_info["file_count"]
        print(f"  Deleting {total_objects:,} objects from S3...")
        print()
        paginator = self.s3.get_paginator("list_objects_v2")
        deleted_count = 0
        start_time = time.time()
        last_update = start_time
        for page in paginator.paginate(Bucket=bucket):
            if "Contents" not in page:
                continue
            objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
            if objects:
                self.s3.delete_objects(Bucket=bucket, Delete={"Objects": objects})
                deleted_count += len(objects)
                current_time = time.time()
                if current_time - last_update >= 2 or deleted_count % 1000 == 0:
                    elapsed = current_time - start_time
                    pct = (deleted_count / total_objects * 100) if total_objects > 0 else 0
                    if deleted_count > 0 and elapsed > 0:
                        rate = deleted_count / elapsed
                        remaining = total_objects - deleted_count
                        eta_seconds = remaining / rate
                        eta_str = format_duration(eta_seconds)
                    else:
                        eta_str = "calculating..."
                    progress = (
                        f"Progress: {deleted_count:,}/{total_objects:,} "
                        f"({pct:.1f}%), ETA: {eta_str}  "
                    )
                    print(
                        f"\r  {progress}",
                        end="",
                        flush=True,
                    )
                    last_update = current_time
        print()
        print(
            f"  ✓ Deleted {deleted_count:,} objects in {format_duration(time.time() - start_time)}"
        )
        print()
        print("  Deleting empty bucket...")
        self.s3.delete_bucket(Bucket=bucket)
