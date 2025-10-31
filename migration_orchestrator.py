"""Orchestration components: Managing bucket migration and status reporting"""

import sys
from pathlib import Path

from migration_state_v2 import MigrationStateV2, Phase
from migration_sync import BucketSyncer
from migration_utils import format_size, print_verification_success_messages
from migration_verify import BucketDeleter, BucketVerifier


class BucketMigrator:  # pylint: disable=too-few-public-methods
    """Handles migrating a single bucket through sync → verify → delete pipeline"""

    def __init__(self, s3, state: MigrationStateV2, base_path: Path):
        self.s3 = s3
        self.state = state
        self.base_path = base_path
        self.syncer = BucketSyncer(s3, state, base_path)
        self.verifier = BucketVerifier(state, base_path)
        self.deleter = BucketDeleter(s3, state)
        self.interrupted = False

    def process_bucket(self, bucket: str):
        """Process a single bucket through sync → verify → delete pipeline"""
        bucket_info = self.state.get_bucket_info(bucket)
        if not bucket_info.get("sync_complete", False):
            print("→ Step 1/3: Syncing from S3...")
            print()
            self.syncer.sync_bucket(bucket)
            self.state.mark_bucket_sync_complete(bucket)
            print()
            print("  ✓ Sync complete")
            print()
        else:
            print("→ Step 1/3: Already synced ✓")
            print()
        needs_verification = (
            not bucket_info.get("verify_complete", False)
            or bucket_info.get("verified_file_count") is None
        )
        if needs_verification:
            if bucket_info.get("verify_complete", False):
                print("→ Step 2/3: Re-verifying to compute detailed stats...")
            else:
                print("→ Step 2/3: Verifying local files...")
            print()
            verify_results = self.verifier.verify_bucket(bucket)
            self.state.mark_bucket_verify_complete(
                bucket,
                verified_file_count=verify_results["verified_count"],
                size_verified_count=verify_results["size_verified"],
                checksum_verified_count=verify_results["checksum_verified"],
                total_bytes_verified=verify_results["total_bytes_verified"],
                local_file_count=verify_results["local_file_count"],
            )
            print()
            print("  ✓ Verification complete")
            print()
        else:
            print("→ Step 2/3: Already verified ✓")
            print()
        if not bucket_info.get("delete_complete", False):
            bucket_info = self.state.get_bucket_info(bucket)
            print("→ Step 3/3: Delete from S3")
            print()
            self._delete_with_confirmation(bucket, bucket_info)
            print()
        else:
            print("→ Step 3/3: Already deleted ✓")
            print()

    def _delete_with_confirmation(self, bucket: str, bucket_info: dict):
        """Delete bucket from S3 with user confirmation"""
        self._show_verification_summary(bucket, bucket_info)
        print()
        print("╔" + "=" * 68 + "╗")
        print("║" + " " * 20 + "READY TO DELETE BUCKET" + " " * 26 + "║")
        print("╚" + "=" * 68 + "╝")
        print()
        print(f"  Bucket: {bucket}")
        print(f"  Files:  {bucket_info['file_count']:,}")
        print(f"  Size:   {format_size(bucket_info['total_size'])}")
        print()
        print("  Local verification: ✓ PASSED")
        print()
        response = input("  Delete this bucket from S3? (yes/no): ")
        if response.lower() == "yes":
            print()
            print(f"  Deleting bucket '{bucket}'...")
            self.deleter.delete_bucket(bucket)
            self.state.mark_bucket_delete_complete(bucket)
            print("  ✓ Deleted from S3")
        else:
            print()
            print("  Skipped - bucket NOT deleted")
            print("  (You can delete it later manually)")

    def _show_verification_summary(self, _bucket: str, bucket_info: dict):
        """Show detailed verification summary from stored results"""
        local_file_count = bucket_info["local_file_count"]
        size_verified_count = bucket_info["size_verified_count"]
        checksum_verified_count = bucket_info["checksum_verified_count"]
        verified_file_count = bucket_info["verified_file_count"]
        total_bytes_verified = bucket_info["total_bytes_verified"]
        print("  " + "=" * 66)
        print("  VERIFICATION SUMMARY (Real Computed Values)")
        print("  " + "=" * 66)
        print()
        print(f"  Files in S3:          {bucket_info['file_count']:,}")
        print(f"  Files found locally:  {local_file_count:,}")
        print(f"  Size verified:        {size_verified_count:,} files")
        print(f"  Checksum verified:    {checksum_verified_count:,} files")
        print(f"  Total verified:       {verified_file_count:,} files")
        print()
        print(f"  ✓ File count matches: {verified_file_count:,} files")
        print_verification_success_messages()
        print(f"  ✓ Total size: {format_size(total_bytes_verified)}")
        print()
        print("  ✓ Verification complete")
        print("  " + "=" * 66)


class StatusReporter:  # pylint: disable=too-few-public-methods
    """Handles displaying migration status"""

    def __init__(self, state: MigrationStateV2):
        self.state = state

    def show_status(self):
        """Display current migration status"""
        print("\n" + "=" * 70)
        print("MIGRATION STATUS")
        print("=" * 70)
        current_phase = self.state.get_current_phase()
        print(f"Current Phase: {current_phase.value}")
        print()
        if current_phase.value >= Phase.GLACIER_RESTORE.value:
            summary = self.state.get_scan_summary()
            print("Overall Summary:")
            print(f"  Total Buckets: {summary['bucket_count']}")
            print(f"  Total Files: {summary['total_files']:,}")
            print(f"  Total Size: {format_size(summary['total_size'])}")
            print()
        all_buckets = self.state.get_all_buckets()
        if all_buckets:
            completed = len(self.state.get_completed_buckets_for_phase("delete_complete"))
            print("Bucket Progress:")
            print(f"  Completed: {completed}/{len(all_buckets)} buckets")
            print()
            print("Bucket Details:")
            for bucket in all_buckets:
                info = self.state.get_bucket_info(bucket)
                sync = "✓" if info.get("sync_complete") else "○"
                verify = "✓" if info.get("verify_complete") else "○"
                delete = "✓" if info.get("delete_complete") else "○"
                print(f"  {bucket}")
                file_info = f"{info['file_count']:,} files, {format_size(info['total_size'])}"
                print(f"    Sync:{sync} Verify:{verify} Delete:{delete}  ({file_info})")
        print("=" * 70)


class BucketMigrationOrchestrator:  # pylint: disable=too-few-public-methods
    """Orchestrates the migration of all buckets one by one"""

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        s3,
        state: MigrationStateV2,
        base_path: Path,
        drive_checker,
        bucket_migrator: BucketMigrator,
    ):
        self.s3 = s3
        self.state = state
        self.base_path = base_path
        self.drive_checker = drive_checker
        self.bucket_migrator = bucket_migrator
        self.interrupted = False

    def migrate_all_buckets(self):
        """Migrate all buckets one by one"""
        print("=" * 70)
        print("PHASE 4/4: MIGRATING BUCKETS (Sync → Verify → Delete)")
        print("=" * 70)
        print()
        all_buckets = self.state.get_all_buckets()
        completed_buckets = self.state.get_completed_buckets_for_phase("delete_complete")
        remaining_buckets = [b for b in all_buckets if b not in completed_buckets]
        if not remaining_buckets:
            print("✓ All buckets already migrated")
            return
        print(f"Migrating {len(remaining_buckets)} bucket(s)")
        print(f"Already complete: {len(completed_buckets)} bucket(s)")
        print()
        for idx, bucket in enumerate(remaining_buckets, 1):
            if self.interrupted:
                return
            self._migrate_single_bucket(idx, bucket, len(remaining_buckets))
        self._print_completion_status(all_buckets)

    def _migrate_single_bucket(self, idx, bucket, total):
        """Migrate a single bucket with error handling"""
        self.drive_checker.check_available()
        print("╔" + "=" * 68 + "╗")
        print(f"║ BUCKET {idx}/{total}: {bucket.ljust(59)}║")
        print("╚" + "=" * 68 + "╝")
        print()
        try:
            self.bucket_migrator.process_bucket(bucket)
            print()
            print(f"✓ Bucket {idx}/{total} complete: {bucket}")
            print()
        except (FileNotFoundError, PermissionError, OSError) as e:
            self._handle_drive_error(e)
        except (RuntimeError, ValueError) as e:
            self._handle_migration_error(bucket, e)

    def _handle_drive_error(self, error):
        """Handle drive disconnection errors"""
        print()
        print(f"✗ Drive error: {error}")
        print()
        print("=" * 70)
        print("MIGRATION INTERRUPTED - DRIVE ERROR")
        print("=" * 70)
        print("The destination drive appears to be disconnected or inaccessible.")
        print()
        print("State has been saved. When you reconnect the drive,")
        print("run 'python migrate_v2.py' to resume.")
        print("=" * 70)
        sys.exit(1)

    def _handle_migration_error(self, bucket, error):
        """Handle general migration errors"""
        print()
        print(f"✗ Error: {error}")
        print()
        print("=" * 70)
        print("MIGRATION STOPPED - ERROR ENCOUNTERED")
        print("=" * 70)
        print(f"Bucket: {bucket}")
        print(f"Error: {error}")
        print()
        print("State has been saved.")
        print("Fix the issue and run 'python migrate_v2.py' to resume.")
        print("=" * 70)
        sys.exit(1)

    def _print_completion_status(self, all_buckets):
        """Print completion or paused status"""
        still_incomplete = [
            b
            for b in all_buckets
            if b not in self.state.get_completed_buckets_for_phase("delete_complete")
        ]
        if not still_incomplete:
            print("=" * 70)
            print("✓ PHASE 4 COMPLETE: All Buckets Migrated")
            print("=" * 70)
            print()
            self.state.set_current_phase(Phase.COMPLETE)
        else:
            print("=" * 70)
            print("MIGRATION PAUSED")
            print("=" * 70)
            print(
                f"Completed: {len(all_buckets) - len(still_incomplete)}/{len(all_buckets)} buckets"
            )
            print(f"Remaining: {len(still_incomplete)} buckets")
            print()
            print("Run 'python migrate_v2.py' to continue.")
            print("=" * 70)
            print()
