"""Phase 1-3: Scanning buckets and handling Glacier restores"""

from dataclasses import dataclass, field
from threading import Event

from botocore.exceptions import ClientError

import config as config_module
from cost_toolkit.common.format_utils import format_bytes
from migration_state_v2 import MigrationStateV2, Phase

# pylint: disable=no-member  # Attributes imported from config_local at runtime
EXCLUDED_BUCKETS = config_module.EXCLUDED_BUCKETS
GLACIER_RESTORE_DAYS = config_module.GLACIER_RESTORE_DAYS
GLACIER_RESTORE_TIER = config_module.GLACIER_RESTORE_TIER
# pylint: enable=no-member


@dataclass
class _BucketStats:
    file_count: int = 0
    total_size: int = 0
    storage_classes: dict[str, int] = field(default_factory=dict)

    def record(self, size: int, storage_class: str):
        """Track a processed object size and storage class count."""
        self.file_count += 1
        self.total_size += size
        current_count = self.storage_classes.get(storage_class, 0)
        self.storage_classes[storage_class] = current_count + 1


class BucketScanner:  # pylint: disable=too-few-public-methods
    """Handles Phase 1: Scanning S3 buckets"""

    def __init__(self, s3, state: MigrationStateV2):
        self.s3 = s3
        self.state = state
        self.interrupted = False

    def _get_page_contents(self, bucket: str, page: dict) -> list[dict]:
        """Extract object listings from a paginator page, validating key counts."""
        contents = page.get("Contents")
        key_count = page.get("KeyCount")
        if contents is None:
            if key_count not in (None, 0):
                raise RuntimeError(
                    f"list_objects_v2 missing Contents while reporting {key_count} keys"
                    f" for bucket {bucket}"
                )
            return []
        return contents

    def _print_progress(self, stats: _BucketStats):
        size_str = format_bytes(stats.total_size, binary_units=False)
        print(
            f"  Found {stats.file_count:,} files, {size_str}...",
            end="\r",
            flush=True,
        )

    def _process_object(self, bucket: str, obj: dict, stats: _BucketStats):
        key = obj["Key"]
        if key.endswith("/"):
            return
        size = obj["Size"]
        etag = obj["ETag"].strip('"')
        storage_class = obj.get("StorageClass", "STANDARD")
        last_modified = obj["LastModified"].isoformat()
        self.state.add_file(bucket, key, size, etag, storage_class, last_modified)
        stats.record(size, storage_class)
        if stats.file_count % 10000 == 0:
            self._print_progress(stats)

    def _save_bucket_stats(self, bucket: str, stats: _BucketStats):
        self.state.save_bucket_status(
            bucket, stats.file_count, stats.total_size, stats.storage_classes, scan_complete=True
        )
        print(
            f"  Found {stats.file_count:,} files, "
            f"{format_bytes(stats.total_size, binary_units=False)}" + " " * 20
        )

    def scan_all_buckets(self):
        """Scan all S3 buckets and track in database"""
        print("=" * 70)
        print("PHASE 1/4: SCANNING BUCKETS")
        print("=" * 70)
        print()
        response = self.s3.list_buckets()
        buckets = [b["Name"] for b in response["Buckets"]]
        excluded = EXCLUDED_BUCKETS
        buckets = [b for b in buckets if b not in excluded]
        print(f"Found {len(buckets)} bucket(s)")
        if excluded:
            print(f"Excluded {len(excluded)} bucket(s): {', '.join(excluded)}")
        print()
        for idx, bucket in enumerate(buckets, 1):
            if self.interrupted:
                return
            print(f"[{idx}/{len(buckets)}] Scanning: {bucket}")
            self.scan_bucket(bucket)
            print()
        self.state.set_current_phase(Phase.GLACIER_RESTORE)
        print("=" * 70)
        print("✓ PHASE 1 COMPLETE: All Buckets Scanned")
        print("=" * 70)
        print()

    def scan_bucket(self, bucket: str):
        """Scan a single bucket"""
        stats = _BucketStats()
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            if self.interrupted:
                return
            for obj in self._get_page_contents(bucket, page):
                self._process_object(bucket, obj, stats)
        self._save_bucket_stats(bucket, stats)


class GlacierRestorer:  # pylint: disable=too-few-public-methods
    """Handles Phase 2: Requesting Glacier restores"""

    def __init__(self, s3, state: MigrationStateV2):
        self.s3 = s3
        self.state = state
        self.interrupted = False

    def request_all_restores(self):
        """Request Glacier restore for all archived files"""
        print("=" * 70)
        print("PHASE 2/4: REQUESTING GLACIER RESTORES")
        print("=" * 70)
        print()
        files = self.state.get_glacier_files_needing_restore()
        if not files:
            print("✓ No Glacier files need restore")
            print()
            self.state.set_current_phase(Phase.GLACIER_WAIT)
            return
        print(f"Requesting restores for {len(files):,} file(s)")
        print()
        for idx, file in enumerate(files, 1):
            if self.interrupted:
                return
            self.request_restore(file, idx, len(files))
        self.state.set_current_phase(Phase.GLACIER_WAIT)
        print()
        print("=" * 70)
        print("✓ PHASE 2 COMPLETE: All Restores Requested")
        print("=" * 70)
        print()

    def request_restore(self, file: dict, idx: int, total: int):
        """Request restore for a single file"""
        bucket = file["bucket"]
        key = file["key"]
        storage_class = file["storage_class"]
        tier = "Bulk" if storage_class == "DEEP_ARCHIVE" else GLACIER_RESTORE_TIER
        try:
            self.s3.restore_object(
                Bucket=bucket,
                Key=key,
                RestoreRequest={
                    "Days": GLACIER_RESTORE_DAYS,
                    "GlacierJobParameters": {"Tier": tier},
                },
            )
            self.state.mark_glacier_restore_requested(bucket, key)
            print(f"  [{idx}/{total}] Requested: {bucket}/{key}")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "RestoreAlreadyInProgress":
                self.state.mark_glacier_restore_requested(bucket, key)
            else:
                raise


class GlacierWaiter:  # pylint: disable=too-few-public-methods
    """Handles Phase 3: Waiting for Glacier restores to complete"""

    def __init__(self, s3, state: MigrationStateV2):
        self.s3 = s3
        self.state = state
        self.interrupted = False
        self._wait_event = Event()

    def _wait_with_interrupt(self, seconds: int):
        """Wait in small increments so interrupts are respected without time.sleep."""
        remaining = seconds
        step = 5
        while remaining > 0 and not self.interrupted:
            self._wait_event.wait(min(step, remaining))
            remaining -= step

    def wait_for_restores(self):
        """Wait for all Glacier restores to complete"""
        print("=" * 70)
        print("PHASE 3/4: WAITING FOR GLACIER RESTORES")
        print("=" * 70)
        print()
        while not self.interrupted:
            restoring = self.state.get_files_restoring()
            if not restoring:
                break
            print(f"Checking {len(restoring):,} file(s) still restoring...")
            for idx, file in enumerate(restoring):
                if self.interrupted:
                    return
                if self.check_restore_status(file):
                    print(f"  [{idx+1}/{len(restoring)}] Restored: {file['bucket']}/{file['key']}")
            print()
            print("Waiting 5 minutes before next check...")
            self._wait_with_interrupt(300)
        self.state.set_current_phase(Phase.SYNCING)
        print("=" * 70)
        print("✓ PHASE 3 COMPLETE: All Restores Complete")
        print("=" * 70)
        print()

    def check_restore_status(self, file: dict) -> bool:
        """Check if restore is complete for a file.

        Raises:
            ClientError: If the S3 API call fails for reasons other than expected restore states.
        """
        response = self.s3.head_object(Bucket=file["bucket"], Key=file["key"])
        restore_status = response.get("Restore")
        if restore_status and 'ongoing-request="false"' in restore_status:
            self.state.mark_glacier_restored(file["bucket"], file["key"])
            return True
        return False
