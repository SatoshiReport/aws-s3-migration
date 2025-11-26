"""Phase 1-3: Scanning buckets and handling Glacier restores"""

import time

from botocore.exceptions import ClientError

try:  # Prefer package-relative imports when linting
    from . import config as config_module
except ImportError:  # pragma: no cover - allow running as standalone script
    import config as config_module  # type: ignore

config = config_module  # expose module for tests
EXCLUDED_BUCKETS = config_module.EXCLUDED_BUCKETS
GLACIER_RESTORE_DAYS = config_module.GLACIER_RESTORE_DAYS
GLACIER_RESTORE_TIER = config_module.GLACIER_RESTORE_TIER

try:  # Prefer package-relative imports when linting/packaged
    from cost_toolkit.common.format_utils import format_bytes

    from .migration_state_v2 import MigrationStateV2, Phase
except ImportError:  # pragma: no cover - allow direct script execution
    from cost_toolkit.common.format_utils import format_bytes
    from migration_state_v2 import MigrationStateV2, Phase


class BucketScanner:  # pylint: disable=too-few-public-methods
    """Handles Phase 1: Scanning S3 buckets"""

    def __init__(self, s3, state: MigrationStateV2):
        self.s3 = s3
        self.state = state
        self.interrupted = False

    def scan_all_buckets(self):
        """Scan all S3 buckets and track in database"""
        print("=" * 70)
        print("PHASE 1/4: SCANNING BUCKETS")
        print("=" * 70)
        print()
        response = self.s3.list_buckets()
        buckets = [b["Name"] for b in response.get("Buckets", [])]
        excluded = config.EXCLUDED_BUCKETS
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
        file_count = 0
        total_size = 0
        storage_classes = {}
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            if self.interrupted:
                return
            if "Contents" not in page:
                continue
            for obj in page["Contents"]:
                key = obj["Key"]
                # Skip S3 directory markers (empty objects with keys ending in '/')
                if key.endswith("/"):
                    continue
                size = obj["Size"]
                etag = obj.get("ETag", "").strip('"')
                storage_class = obj.get("StorageClass", "STANDARD")
                last_modified = obj["LastModified"].isoformat()
                self.state.add_file(bucket, key, size, etag, storage_class, last_modified)
                file_count += 1
                total_size += size
                storage_classes[storage_class] = storage_classes.get(storage_class, 0) + 1
                if file_count % 10000 == 0:
                    size_str = format_bytes(total_size, binary_units=False)
                    print(
                        f"  Found {file_count:,} files, {size_str}...",
                        end="\r",
                        flush=True,
                    )
        self.state.save_bucket_status(
            bucket, file_count, total_size, storage_classes, scan_complete=True
        )
        print(
            f"  Found {file_count:,} files, {format_bytes(total_size, binary_units=False)}"
            + " " * 20
        )


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
        tier = "Bulk" if storage_class == "DEEP_ARCHIVE" else config.GLACIER_RESTORE_TIER
        try:
            self.s3.restore_object(
                Bucket=bucket,
                Key=key,
                RestoreRequest={
                    "Days": config.GLACIER_RESTORE_DAYS,
                    "GlacierJobParameters": {"Tier": tier},
                },
            )
            self.state.mark_glacier_restore_requested(bucket, key)
            print(f"  [{idx}/{total}] Requested: {bucket}/{key}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
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
            time.sleep(300)
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
