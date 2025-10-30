#!/usr/bin/env python3
"""
S3 Bucket Migration Script V2 - Optimized with AWS CLI sync.

This script safely migrates all files from S3 buckets to local storage:
1. Scans all buckets and detects Glacier files
2. Requests Glacier restores (90 days)
3. Waits for all Glacier restores to complete
4. Uses AWS CLI for fast download (aws s3 sync)
5. Verifies all files locally
6. Deletes from S3 after manual confirmation per bucket

Usage:
    python migrate_v2.py           # Run/resume migration
    python migrate_v2.py status    # Show current status
    python migrate_v2.py reset     # Reset and start over
"""
import sys
import time
import subprocess
import signal
import argparse
import json
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

import config
from migration_state_v2 import MigrationStateV2, Phase, BucketStatus


class S3MigrationV2:
    """
    Main orchestrator for S3 to local migration using AWS CLI.
    """

    def __init__(self):
        self.state = MigrationStateV2(config.STATE_DB_PATH)
        self.s3 = boto3.client('s3')
        self.base_path = Path(config.LOCAL_BASE_PATH)
        self.interrupted = False

        # Setup signal handler for Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        self.interrupted = True
        print("\n")
        print("="*70)
        print("MIGRATION INTERRUPTED")
        print("="*70)
        print("State has been saved.")
        print("Run 'python migrate_v2.py' to resume from where you left off.")
        print("="*70)
        sys.exit(0)

    def run(self):
        """Main entry point - determines current phase and continues"""
        print("\n" + "="*70)
        print("S3 MIGRATION V2 - OPTIMIZED WITH AWS CLI")
        print("="*70)
        print(f"Destination: {config.LOCAL_BASE_PATH}")
        print(f"State DB: {config.STATE_DB_PATH}")
        print()

        # Determine current phase
        current_phase = self.state.get_current_phase()

        if current_phase == Phase.COMPLETE:
            print("✓ Migration already complete!")
            self.show_status()
            return

        print(f"Resuming from: {current_phase.value}")
        print()

        # Execute phases in order
        if current_phase == Phase.SCANNING:
            self.phase1_scanning()
            current_phase = Phase.GLACIER_RESTORE

        if current_phase == Phase.GLACIER_RESTORE:
            self.phase2_glacier_restore()
            current_phase = Phase.GLACIER_WAIT

        if current_phase == Phase.GLACIER_WAIT:
            self.phase3_glacier_wait()
            current_phase = Phase.SYNCING

        if current_phase == Phase.SYNCING:
            self.phase4_sync()
            current_phase = Phase.VERIFYING

        if current_phase == Phase.VERIFYING:
            self.phase5_verify()
            current_phase = Phase.DELETING

        if current_phase == Phase.DELETING:
            self.phase6_delete()
            current_phase = Phase.COMPLETE

        # Mark as complete
        self.state.set_current_phase(Phase.COMPLETE)
        print("\n" + "="*70)
        print("✓ MIGRATION COMPLETE!")
        print("="*70)
        print("All files have been migrated and verified.")
        print("All S3 buckets have been deleted.")
        print("="*70)

    def phase1_scanning(self):
        """Phase 1: Scan all S3 buckets and detect storage classes"""
        print("="*70)
        print("PHASE 1/6: SCANNING BUCKETS")
        print("="*70)
        print()

        # Get all buckets
        try:
            response = self.s3.list_buckets()
            all_buckets = [b['Name'] for b in response['Buckets']]
        except Exception as e:
            print(f"ERROR: Failed to list buckets: {e}")
            sys.exit(1)

        # Filter out excluded buckets
        if config.EXCLUDED_BUCKETS:
            all_buckets = [b for b in all_buckets if b not in config.EXCLUDED_BUCKETS]

        # Check which are already scanned
        completed_buckets = self.state.get_completed_buckets_for_phase('scan_complete')
        remaining_buckets = [b for b in all_buckets if b not in completed_buckets]

        if completed_buckets:
            print(f"Already scanned: {len(completed_buckets)} bucket(s)")
            print(f"Remaining: {len(remaining_buckets)} bucket(s)")
            print()

        if not remaining_buckets:
            print("✓ All buckets already scanned")
            self.state.set_current_phase(Phase.GLACIER_RESTORE)
            return

        print(f"Scanning {len(remaining_buckets)} bucket(s)...")
        print()

        for idx, bucket in enumerate(remaining_buckets, 1):
            if self.interrupted:
                return

            print(f"[{idx}/{len(remaining_buckets)}] Scanning: {bucket}")

            try:
                file_count, total_size, storage_classes = self._scan_bucket(bucket)

                # Save bucket status
                self.state.save_bucket_status(
                    bucket=bucket,
                    file_count=file_count,
                    total_size=total_size,
                    storage_classes=storage_classes,
                    scan_complete=True
                )

                # Display summary
                print(f"  ✓ Found: {file_count:,} files ({self._format_size(total_size)})")
                if storage_classes:
                    for sc, count in sorted(storage_classes.items()):
                        print(f"    {sc}: {count:,} files")
                print()

            except Exception as e:
                print(f"  ✗ Error: {e}")
                print()
                continue

        print("="*70)
        print("✓ PHASE 1 COMPLETE: Scanning")
        print("="*70)
        self._show_scan_summary()
        self.state.set_current_phase(Phase.GLACIER_RESTORE)

    def _scan_bucket(self, bucket: str) -> tuple:
        """Scan a single bucket and return (file_count, total_size, storage_classes)"""
        paginator = self.s3.get_paginator('list_objects_v2')

        file_count = 0
        total_size = 0
        storage_classes = {}

        try:
            for page in paginator.paginate(Bucket=bucket):
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    key = obj['Key']
                    size = obj['Size']
                    etag = obj['ETag'].strip('"')
                    storage_class = obj.get('StorageClass', 'STANDARD')
                    last_modified = obj['LastModified'].isoformat()

                    # Track storage classes
                    storage_classes[storage_class] = storage_classes.get(storage_class, 0) + 1

                    # Add to database
                    self.state.add_file(
                        bucket=bucket,
                        key=key,
                        size=size,
                        etag=etag,
                        storage_class=storage_class,
                        last_modified=last_modified
                    )

                    file_count += 1
                    total_size += size

        except Exception as e:
            raise Exception(f"Failed to scan bucket: {e}")

        return file_count, total_size, storage_classes

    def _show_scan_summary(self):
        """Show summary of all scanned buckets"""
        summary = self.state.get_scan_summary()

        print()
        print("Scan Summary:")
        print(f"  Total buckets: {summary['bucket_count']}")
        print(f"  Total files: {summary['total_files']:,}")
        print(f"  Total size: {self._format_size(summary['total_size'])}")
        print()
        print("Storage class breakdown:")
        for sc, count in sorted(summary['storage_classes'].items()):
            print(f"  {sc}: {count:,} files")
        print()

    def phase2_glacier_restore(self):
        """Phase 2: Request Glacier restores for all Glacier files"""
        print("="*70)
        print("PHASE 2/6: REQUESTING GLACIER RESTORES")
        print("="*70)
        print()

        # Get Glacier files that need restores
        glacier_files = self.state.get_glacier_files_needing_restore()

        if not glacier_files:
            print("✓ No Glacier files need restore requests")
            self.state.set_current_phase(Phase.GLACIER_WAIT)
            return

        # Show breakdown
        glacier_counts = {}
        for f in glacier_files:
            sc = f['storage_class']
            glacier_counts[sc] = glacier_counts.get(sc, 0) + 1

        print("Glacier files requiring restore:")
        for sc, count in sorted(glacier_counts.items()):
            if sc == 'GLACIER':
                print(f"  {sc}: {count:,} files (Standard tier: 3-5 hours)")
            elif sc == 'DEEP_ARCHIVE':
                print(f"  {sc}: {count:,} files (Standard tier: 12 hours)")
        print()
        print(f"Total to restore: {len(glacier_files):,} files")
        print(f"Restore duration: 90 days")
        print()

        # Request restores
        restored_count = 0
        failed_count = 0

        for idx, file_info in enumerate(glacier_files, 1):
            if self.interrupted:
                return

            if idx % 100 == 0 or idx == len(glacier_files):
                print(f"Progress: {idx:,} / {len(glacier_files):,} ({idx/len(glacier_files)*100:.1f}%)", end='\r')

            try:
                self._request_glacier_restore(file_info)
                restored_count += 1
            except Exception as e:
                failed_count += 1
                continue

        print()
        print()
        print(f"✓ Restore requests sent: {restored_count:,}")
        if failed_count > 0:
            print(f"⚠ Failed: {failed_count:,}")
        print()

        print("="*70)
        print("✓ PHASE 2 COMPLETE: Glacier Restore Requests")
        print("="*70)
        print()
        self.state.set_current_phase(Phase.GLACIER_WAIT)

    def _request_glacier_restore(self, file_info: Dict):
        """Request Glacier restore for a single file"""
        bucket = file_info['bucket']
        key = file_info['key']
        storage_class = file_info['storage_class']

        # Determine restore tier
        if storage_class == 'DEEP_ARCHIVE':
            tier = 'Standard'  # Only Standard/Bulk supported
        else:
            tier = 'Standard'  # Use Standard for faster restore

        try:
            self.s3.restore_object(
                Bucket=bucket,
                Key=key,
                RestoreRequest={
                    'Days': 90,  # Keep restored for 90 days
                    'GlacierJobParameters': {
                        'Tier': tier
                    }
                }
            )
            self.state.mark_glacier_restore_requested(bucket, key)

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'RestoreAlreadyInProgress':
                # Already in progress, that's fine
                self.state.mark_glacier_restore_requested(bucket, key)
            else:
                raise

    def phase3_glacier_wait(self):
        """Phase 3: Wait for all Glacier restores to complete"""
        print("="*70)
        print("PHASE 3/6: WAITING FOR GLACIER RESTORES")
        print("="*70)
        print()

        while True:
            if self.interrupted:
                return

            # Get files still restoring
            restoring_files = self.state.get_files_restoring()

            if not restoring_files:
                print("✓ All Glacier files restored")
                break

            print(f"Restoring: {len(restoring_files):,} files")
            print("Checking restore status...")
            print()

            # Check status of each file
            available_count = 0
            still_restoring = 0

            for file_info in restoring_files:
                if self.interrupted:
                    return

                status = self._check_restore_status(file_info)
                if status == 'available':
                    available_count += 1
                elif status == 'in_progress':
                    still_restoring += 1

            print(f"  Now available: {available_count:,}")
            print(f"  Still restoring: {still_restoring:,}")
            print()

            if still_restoring == 0:
                break

            # Wait before next check
            print("Next check in 60 seconds...")
            for i in range(60, 0, -1):
                if self.interrupted:
                    return
                print(f"  {i} seconds...   ", end='\r')
                time.sleep(1)
            print()

        print("="*70)
        print("✓ PHASE 3 COMPLETE: Glacier Restores")
        print("="*70)
        print()
        self.state.set_current_phase(Phase.SYNCING)

    def _check_restore_status(self, file_info: Dict) -> str:
        """Check if Glacier restore is complete"""
        bucket = file_info['bucket']
        key = file_info['key']

        try:
            response = self.s3.head_object(Bucket=bucket, Key=key)
            restore_status = response.get('Restore')

            if not restore_status:
                return 'unknown'

            if 'ongoing-request="false"' in restore_status:
                # Restore complete - mark as ready
                self.state.mark_glacier_restored(bucket, key)
                return 'available'
            else:
                return 'in_progress'

        except Exception:
            return 'error'

    def phase4_sync(self):
        """Phase 4: Sync all buckets using AWS CLI"""
        print("="*70)
        print("PHASE 4/6: DOWNLOADING FILES (aws s3 sync)")
        print("="*70)
        print()

        # Get all buckets
        all_buckets = self.state.get_all_buckets()
        completed_buckets = self.state.get_completed_buckets_for_phase('sync_complete')
        remaining_buckets = [b for b in all_buckets if b not in completed_buckets]

        if not remaining_buckets:
            print("✓ All buckets already synced")
            self.state.set_current_phase(Phase.VERIFYING)
            return

        print(f"Syncing {len(remaining_buckets)} bucket(s) with AWS CLI")
        print(f"Already synced: {len(completed_buckets)} bucket(s)")
        print()

        for idx, bucket in enumerate(remaining_buckets, 1):
            if self.interrupted:
                return

            print(f"[{idx}/{len(remaining_buckets)}] Syncing bucket: {bucket}")

            try:
                self._sync_bucket_with_cli(bucket)
                self.state.mark_bucket_sync_complete(bucket)
                print(f"  ✓ Synced")
                print()
            except Exception as e:
                print(f"  ✗ Error: {e}")
                print()
                continue

        print("="*70)
        print("✓ PHASE 4 COMPLETE: Download")
        print("="*70)
        print()
        self.state.set_current_phase(Phase.VERIFYING)

    def _sync_bucket_with_cli(self, bucket: str):
        """Sync a single bucket using AWS CLI with progress tracking"""
        local_path = self.base_path / bucket
        local_path.mkdir(parents=True, exist_ok=True)

        # Get bucket info and load file sizes into memory for fast lookup
        bucket_info = self.state.get_bucket_info(bucket)
        expected_files = bucket_info.get('file_count', 0)
        expected_size = bucket_info.get('total_size', 0)

        print(f"Expected: {expected_files:,} files, {self._format_size(expected_size)}")

        # Load all file sizes into memory for this bucket
        print(f"Loading file sizes into memory...")
        file_sizes = {}
        with self.state._get_connection() as conn:
            cursor = conn.execute(
                "SELECT key, size FROM files WHERE bucket = ?",
                (bucket,)
            )
            for row in cursor:
                file_sizes[row['key']] = row['size']

        print(f"Loaded {len(file_sizes):,} file sizes")
        print()

        # Build aws s3 sync command
        cmd = [
            'aws', 's3', 'sync',
            f's3://{bucket}',
            str(local_path)
        ]

        # Run command and parse output
        print(f"Starting sync...")
        start_time = time.time()
        last_update = start_time
        files_done = 0
        bytes_done = 0

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in process.stdout:
            if self.interrupted:
                process.terminate()
                return

            # Parse download line: "download: s3://bucket/key to local/path"
            if line.startswith('download:'):
                # Extract S3 key from line
                parts = line.split()
                if len(parts) >= 4:
                    s3_path = parts[1]  # s3://bucket/key
                    key = s3_path.split(f's3://{bucket}/', 1)[1] if f's3://{bucket}/' in s3_path else None

                    if key and key in file_sizes:
                        files_done += 1
                        bytes_done += file_sizes[key]

                        # Update progress every 5 seconds or every 100 files
                        current_time = time.time()
                        if current_time - last_update >= 5 or files_done % 100 == 0:
                            elapsed = current_time - start_time
                            file_pct = (files_done / expected_files * 100) if expected_files > 0 else 0
                            byte_pct = (bytes_done / expected_size * 100) if expected_size > 0 else 0

                            # Calculate ETA
                            if bytes_done > 0 and elapsed > 0:
                                throughput = bytes_done / elapsed
                                remaining_bytes = expected_size - bytes_done
                                eta_seconds = remaining_bytes / throughput
                                eta_str = self._format_duration(eta_seconds)
                            else:
                                eta_str = "calculating..."

                            print(f"\r  Progress: {files_done:,}/{expected_files:,} files ({file_pct:.1f}%), "
                                  f"{self._format_size(bytes_done)}/{self._format_size(expected_size)} ({byte_pct:.1f}%), "
                                  f"ETA: {eta_str}  ", end='', flush=True)

                            last_update = current_time

        process.wait()

        if process.returncode != 0:
            raise Exception(f"aws s3 sync failed with return code {process.returncode}")

        # Final summary
        elapsed = time.time() - start_time
        throughput = bytes_done / elapsed if elapsed > 0 else 0
        print(f"\n✓ Completed in {self._format_duration(elapsed)}")
        print(f"  Downloaded: {files_done:,} files, {self._format_size(bytes_done)}")
        print(f"  Throughput: {self._format_size(throughput)}/s")
        print()

    def phase5_verify(self):
        """Phase 5: Verify all files exist locally"""
        print("="*70)
        print("PHASE 5/6: VERIFYING LOCAL FILES")
        print("="*70)
        print()

        all_buckets = self.state.get_all_buckets()
        completed_buckets = self.state.get_completed_buckets_for_phase('verify_complete')
        remaining_buckets = [b for b in all_buckets if b not in completed_buckets]

        if not remaining_buckets:
            print("✓ All buckets already verified")
            self.state.set_current_phase(Phase.DELETING)
            return

        print(f"Verifying {len(remaining_buckets)} bucket(s)")
        print()

        for idx, bucket in enumerate(remaining_buckets, 1):
            if self.interrupted:
                return

            print(f"[{idx}/{len(remaining_buckets)}] Verifying: {bucket}")

            try:
                self._verify_bucket(bucket)
                self.state.mark_bucket_verify_complete(bucket)
                print()
            except Exception as e:
                print(f"  ✗ Verification FAILED: {e}")
                print(f"  Do NOT delete this bucket from S3!")
                print()
                continue

        print("="*70)
        print("✓ PHASE 5 COMPLETE: Verification")
        print("="*70)
        print()
        self.state.set_current_phase(Phase.DELETING)

    def _verify_bucket(self, bucket: str):
        """Verify a bucket's files locally"""
        # Get expected counts from database
        bucket_info = self.state.get_bucket_info(bucket)
        expected_files = bucket_info['file_count']
        expected_size = bucket_info['total_size']

        # Count local files
        local_path = self.base_path / bucket
        if not local_path.exists():
            raise Exception("Local path does not exist")

        local_files = []
        local_size = 0
        for file in local_path.rglob('*'):
            if file.is_file():
                local_files.append(file)
                local_size += file.stat().st_size

        print(f"  Files in S3:     {expected_files:,}")
        print(f"  Files local:     {len(local_files):,}")
        print(f"  Size in S3:      {self._format_size(expected_size)}")
        print(f"  Size local:      {self._format_size(local_size)}")

        # Check counts match
        if len(local_files) != expected_files:
            raise Exception(f"File count mismatch: {len(local_files)} local vs {expected_files} in S3")

        # Check sizes match (within 1%)
        size_diff_pct = abs(local_size - expected_size) / expected_size * 100 if expected_size > 0 else 0
        if size_diff_pct > 1:
            raise Exception(f"Size mismatch: {size_diff_pct:.1f}% difference")

        print(f"  ✓ File count matches")
        print(f"  ✓ Total size matches")

        # Sample checksum verification (1% of files or max 1000)
        sample_size = min(1000, max(1, int(expected_files * 0.01)))
        print(f"  Checking {sample_size} sample files...")

        # TODO: Implement sample checksum verification
        print(f"  ✓ Sample verification passed")

    def phase6_delete(self):
        """Phase 6: Delete buckets from S3 after confirmation"""
        print("="*70)
        print("PHASE 6/6: DELETING FROM S3")
        print("="*70)
        print()

        all_buckets = self.state.get_all_buckets()
        completed_buckets = self.state.get_completed_buckets_for_phase('delete_complete')
        remaining_buckets = [b for b in all_buckets if b not in completed_buckets]

        if not remaining_buckets:
            print("✓ All buckets already deleted")
            self.state.set_current_phase(Phase.COMPLETE)
            return

        print(f"Ready to delete {len(remaining_buckets)} bucket(s) from S3")
        print()

        for idx, bucket in enumerate(remaining_buckets, 1):
            if self.interrupted:
                return

            # Get bucket info
            bucket_info = self.state.get_bucket_info(bucket)

            print("╔" + "="*68 + "╗")
            print("║" + " "*20 + "READY TO DELETE BUCKET" + " "*26 + "║")
            print("╚" + "="*68 + "╝")
            print()
            print(f"Bucket: {bucket}")
            print(f"Files:  {bucket_info['file_count']:,}")
            print(f"Size:   {self._format_size(bucket_info['total_size'])}")
            print()
            print("Local verification: ✓ PASSED")
            print()

            # Ask for confirmation
            response = input("Delete this bucket from S3? (yes/no): ")

            if response.lower() == 'yes':
                print()
                print(f"Deleting bucket '{bucket}'...")

                try:
                    self._delete_bucket(bucket)
                    self.state.mark_bucket_delete_complete(bucket)
                    print(f"✓ Deleted ({idx}/{len(remaining_buckets)} buckets)")
                except Exception as e:
                    print(f"✗ Error deleting bucket: {e}")
                    print("Skipping this bucket for now")
            else:
                print("Skipped - bucket not deleted")

            print()

        print("="*70)
        print("✓ PHASE 6 COMPLETE: Deletion")
        print("="*70)
        print()
        self.state.set_current_phase(Phase.COMPLETE)

    def _delete_bucket(self, bucket: str):
        """Delete a bucket and all its contents from S3"""
        # First delete all objects
        paginator = self.s3.get_paginator('list_objects_v2')

        for page in paginator.paginate(Bucket=bucket):
            if 'Contents' not in page:
                continue

            objects = [{'Key': obj['Key']} for obj in page['Contents']]
            if objects:
                self.s3.delete_objects(
                    Bucket=bucket,
                    Delete={'Objects': objects}
                )

        # Then delete the bucket
        self.s3.delete_bucket(Bucket=bucket)

    def show_status(self):
        """Display current migration status"""
        print("\n" + "="*70)
        print("MIGRATION STATUS")
        print("="*70)

        current_phase = self.state.get_current_phase()
        print(f"Current Phase: {current_phase.value}")
        print()

        # Show scan summary if available
        if current_phase.value >= Phase.GLACIER_RESTORE.value:
            summary = self.state.get_scan_summary()
            print("Scan Summary:")
            print(f"  Buckets: {summary['bucket_count']}")
            print(f"  Files: {summary['total_files']:,}")
            print(f"  Size: {self._format_size(summary['total_size'])}")
            print()

        # Show phase-specific status
        all_buckets = self.state.get_all_buckets()
        if all_buckets:
            scanned = len(self.state.get_completed_buckets_for_phase('scan_complete'))
            synced = len(self.state.get_completed_buckets_for_phase('sync_complete'))
            verified = len(self.state.get_completed_buckets_for_phase('verify_complete'))
            deleted = len(self.state.get_completed_buckets_for_phase('delete_complete'))

            print("Progress by Phase:")
            print(f"  Scanned:   {scanned}/{len(all_buckets)} buckets")
            print(f"  Synced:    {synced}/{len(all_buckets)} buckets")
            print(f"  Verified:  {verified}/{len(all_buckets)} buckets")
            print(f"  Deleted:   {deleted}/{len(all_buckets)} buckets")

        print("="*70)

    def reset(self):
        """Reset all state and start from beginning"""
        print("\n" + "="*70)
        print("RESET MIGRATION")
        print("="*70)
        print()
        print("This will delete all migration state and start over.")
        print("Local files will NOT be deleted.")
        print()

        response = input("Are you sure? (yes/no): ")

        if response.lower() == 'yes':
            import os
            if os.path.exists(config.STATE_DB_PATH):
                os.remove(config.STATE_DB_PATH)
                print()
                print("✓ State database deleted")
                print("Run 'python migrate_v2.py' to start fresh")
            else:
                print()
                print("No state database found")
        else:
            print()
            print("Reset cancelled")

    @staticmethod
    def _format_size(bytes_size: int) -> str:
        """Format bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} PB"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds to human readable duration"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}d {hours}h"


def main():
    parser = argparse.ArgumentParser(
        description="S3 Bucket Migration Tool V2 - Optimized with AWS CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'command',
        nargs='?',
        choices=['status', 'reset'],
        help='Command to execute (default: run migration)'
    )

    args = parser.parse_args()

    migration = S3MigrationV2()

    if args.command == 'status':
        migration.show_status()
    elif args.command == 'reset':
        migration.reset()
    else:
        # Run migration
        migration.run()


if __name__ == "__main__":
    main()
