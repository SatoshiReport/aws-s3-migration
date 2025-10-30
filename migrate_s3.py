#!/usr/bin/env python3
"""
S3 Bucket Migration Script - Move all S3 buckets to local storage.

This script safely migrates all files from S3 buckets to local storage:
1. Scans all buckets and builds inventory
2. Automatically handles Glacier restore requests
3. Downloads files with verification
4. Deletes from S3 only after successful verification
5. Tracks state for resilient resumption

Usage:
    python migrate_s3.py scan              # Scan buckets and build inventory
    python migrate_s3.py migrate           # Start/resume migration (handles Glacier automatically)
    python migrate_s3.py status            # Show current status
    python migrate_s3.py glacier           # Manually check/process Glacier files (optional)
"""
import sys
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from migration_state import MigrationState, FileState
from s3_scanner import S3Scanner
from file_migrator import FileMigrator
from glacier_handler import GlacierHandler
from progress_tracker import ProgressTracker
import config


class S3Migration:
    """
    Main orchestrator for S3 to local migration.
    """

    def __init__(self):
        self.state = MigrationState(config.STATE_DB_PATH)
        self.scanner = S3Scanner(self.state)
        self.migrator = FileMigrator(self.state)
        self.glacier = GlacierHandler(self.state)
        self.progress = ProgressTracker(self.state)

    def scan_buckets(self, bucket_names=None):
        """Scan S3 buckets and build inventory"""
        print("="*70)
        print("SCANNING S3 BUCKETS")
        print("="*70)
        print(f"Destination: {config.LOCAL_BASE_PATH}\n")

        # Show existing database stats if any
        existing_stats = self.state.get_statistics()
        existing_count = existing_stats.get('total', {}).get('count', 0)
        existing_size = existing_stats.get('total', {}).get('size', 0)

        if existing_count > 0:
            print("Database already contains:")
            print(f"  Files:   {existing_count:,}")
            print(f"  Size:    {self._format_size(existing_size)}")
            print(f"  Buckets: {len(self.state.get_buckets())}")
            print("\nContinuing scan (will skip existing files)...\n")

        self.scanner.scan_all_buckets(bucket_names)

        print("\n" + "="*70)
        print("SCAN COMPLETE")
        print("="*70)
        stats = self.state.get_statistics()
        total = stats.get('total', {})
        new_count = total.get('count', 0)
        new_size = total.get('size', 0)

        print(f"Grand total in database:")
        print(f"  Files:   {new_count:,}")
        print(f"  Size:    {self._format_size(new_size)}")
        print(f"  Buckets: {len(self.state.get_buckets())}")

        if existing_count > 0:
            added_count = new_count - existing_count
            added_size = new_size - existing_size
            print(f"\nAdded in this scan:")
            print(f"  Files:   {added_count:,}")
            print(f"  Size:    {self._format_size(added_size)}")
        print()

    def check_stuck_files(self):
        """Check for and reset files stuck in intermediate states"""
        stuck_states = [FileState.DOWNLOADING, FileState.DOWNLOADED, FileState.VERIFIED]
        stuck_files = self.state.get_files_by_states(stuck_states)

        if stuck_files:
            print(f"\nFound {len(stuck_files)} file(s) in intermediate states (likely interrupted)")
            response = input("Reset these files to retry? (yes/no): ")
            if response.lower() == 'yes':
                for f in stuck_files:
                    self.state.update_state(f['bucket'], f['key'], FileState.DISCOVERED)
                print(f"✓ Reset {len(stuck_files)} file(s) to DISCOVERED state\n")
            else:
                print("Skipped.\n")

    def show_status(self):
        """Display current migration status"""
        from datetime import datetime, timezone

        stats = self.state.get_statistics()

        if not stats.get('total', {}).get('count', 0):
            print("No files in database. Run 'scan' first.")
            return

        # Get database creation time and migration runtime info
        db_stats = self.state.get_overall_stats()
        runtime_info = self.state.get_migration_runtime_info()

        print("="*70)
        print("OVERALL MIGRATION STATUS")
        print("="*70)

        # Show database creation time
        if db_stats['start_time']:
            db_created_dt = datetime.fromisoformat(db_stats['start_time'])
            # Make timezone-aware if it's naive (for compatibility with old database entries)
            if db_created_dt.tzinfo is None:
                db_created_dt = db_created_dt.replace(tzinfo=timezone.utc)
            print(f"Database Created:   {db_created_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Show migration timing only if migration has started
        migration_start_time = runtime_info.get('migration_start_time')
        if migration_start_time:
            migration_start_dt = datetime.fromisoformat(migration_start_time)
            # Make timezone-aware if it's naive
            if migration_start_dt.tzinfo is None:
                migration_start_dt = migration_start_dt.replace(tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            elapsed_seconds = (now_dt - migration_start_dt).total_seconds()

            print(f"Migration Started:  {migration_start_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"Migration Runtime:  {self._format_duration(elapsed_seconds)}")

            # Calculate overall average throughput
            if elapsed_seconds > 0 and runtime_info['completed_bytes'] > 0:
                avg_throughput = runtime_info['completed_bytes'] / elapsed_seconds
                print(f"Average Throughput: {self._format_size(avg_throughput)}/s")

        print(f"\nFiles Completed:    {runtime_info['completed_files']:,} / {runtime_info['total_files']:,} " +
              f"({runtime_info['completed_files']/runtime_info['total_files']*100:.1f}%)" if runtime_info['total_files'] > 0 else "0.0%)")
        print(f"Data Completed:     {self._format_size(runtime_info['completed_bytes'])} / " +
              f"{self._format_size(runtime_info['total_bytes'])} " +
              f"({runtime_info['completed_bytes']/runtime_info['total_bytes']*100:.1f}%)" if runtime_info['total_bytes'] > 0 else "0.0%)")

        print()

        self.progress.display_progress()

        # Show Glacier summary
        glacier_summary = self.glacier.get_glacier_summary()
        if any(glacier_summary.values()):
            print("Glacier Files:")
            print(f"  Discovered (needs restore): {glacier_summary['discovered']:,}")
            print(f"  Restore requested:          {glacier_summary['restore_requested']:,}")
            print(f"  Currently restoring:        {glacier_summary['restoring']:,}")
            print()

    def process_glacier_files(self):
        """Process Glacier restore requests and status checks"""
        print("="*70)
        print("PROCESSING GLACIER FILES")
        print("="*70)

        glacier_summary = self.glacier.get_glacier_summary()
        print(f"Glacier files to process: {glacier_summary['discovered']:,}")
        print(f"Files being restored: {glacier_summary['restoring']:,}")
        print()

        if glacier_summary['discovered'] == 0 and glacier_summary['restoring'] == 0:
            print("No Glacier files to process.")
            return

        stats = self.glacier.process_glacier_files()

        print(f"\nGlacier processing complete:")
        print(f"  Restore requests sent: {stats['requested']:,}")
        print(f"  Files now available:   {stats['available']:,}")
        print(f"  Still restoring:       {stats['in_progress']:,}")
        print(f"  Errors:                {stats['failed']:,}")

    def migrate(self):
        """
        Main migration loop: downloads, verifies, and deletes files.
        Automatically handles Glacier files with restore requests.
        Handles resumption automatically.
        """
        # Ensure destination directory exists
        Path(config.LOCAL_BASE_PATH).mkdir(parents=True, exist_ok=True)

        print("="*70)
        print("S3 MIGRATION")
        print("="*70)
        print(f"Destination: {config.LOCAL_BASE_PATH}")
        print(f"State DB: {config.STATE_DB_PATH}")
        print()

        # Check for stuck files from previous interrupted runs
        self.check_stuck_files()

        if not self.state.has_files_to_process():
            print("No files to process. Migration may be complete!")
            self.show_status()
            return

        # Record migration start time (only if not already set)
        from datetime import datetime, timezone
        if not self.state.get_metadata('migration_start_time'):
            self.state.set_metadata('migration_start_time', datetime.now(timezone.utc).isoformat())
            print("Migration started - start time recorded.\n")

        print("Starting migration with parallel downloads...\n")
        print(f"Concurrent workers: {config.MAX_CONCURRENT_DOWNLOADS}\n")

        # Show initial status
        self.progress.display_progress()

        last_progress_update = time.time()
        last_glacier_check = time.time()
        files_completed = 0

        # Create thread pool for parallel downloads
        with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_DOWNLOADS) as executor:
            while self.state.has_files_to_process():
                current_time = time.time()

                # Show periodic progress updates (every 5 seconds)
                if current_time - last_progress_update >= config.PROGRESS_UPDATE_INTERVAL:
                    self.progress.display_progress()
                    last_progress_update = current_time

                # Process Glacier files periodically (every 60 seconds)
                glacier_summary = self.glacier.get_glacier_summary()
                if (glacier_summary['discovered'] > 0 or glacier_summary['restoring'] > 0):
                    if current_time - last_glacier_check >= 60 or last_glacier_check == 0:
                        print("\nProcessing Glacier files...")
                        glacier_stats = self.glacier.process_glacier_files()
                        if glacier_stats['requested'] > 0:
                            print(f"  Requested restore for {glacier_stats['requested']} Glacier file(s)")
                        if glacier_stats['available'] > 0:
                            print(f"  {glacier_stats['available']} Glacier file(s) now available for download")
                        if glacier_stats['in_progress'] > 0:
                            print(f"  {glacier_stats['in_progress']} Glacier file(s) still restoring...")
                        last_glacier_check = current_time
                        # Show progress after Glacier check
                        self.progress.display_progress()
                        last_progress_update = current_time

                # Get files ready to download (standard storage + restored Glacier)
                # OPTIMIZATION: Only fetch what we need (batch size), not all 3.9M files!
                discovered_files = self.state.get_files_by_state(FileState.DISCOVERED, limit=config.BATCH_SIZE * 2)

                # Separate Glacier files from ready files
                glacier_needing_restore = []
                ready_files = []

                for f in discovered_files:
                    if self.glacier.is_glacier_storage(f['storage_class']):
                        if f.get('glacier_restore_requested_at') is not None:
                            # Glacier file with restore requested - might be ready
                            ready_files.append(f)
                        else:
                            # Glacier file needing restore request
                            glacier_needing_restore.append(f)
                    else:
                        # Standard storage - ready to download
                        ready_files.append(f)


                # If we have Glacier files needing restore, trigger Glacier processing
                if glacier_needing_restore and not ready_files:
                    print(f"\nFound {len(glacier_needing_restore)} Glacier file(s) needing restore requests...")
                    print("Processing Glacier files...")
                    glacier_stats = self.glacier.process_glacier_files()
                    if glacier_stats['requested'] > 0:
                        print(f"  Requested restore for {glacier_stats['requested']} Glacier file(s)")
                    if glacier_stats['available'] > 0:
                        print(f"  {glacier_stats['available']} Glacier file(s) now available for download")
                    if glacier_stats['in_progress'] > 0:
                        print(f"  {glacier_stats['in_progress']} Glacier file(s) still restoring...")
                    last_glacier_check = time.time()
                    self.progress.display_progress()
                    last_progress_update = time.time()
                    continue

                if not ready_files:
                    # Check if we're just waiting for Glacier
                    glacier_summary = self.glacier.get_glacier_summary()
                    if glacier_summary['restoring'] > 0:
                        print(f"\nWaiting for {glacier_summary['restoring']} Glacier file(s) to restore...")
                        print("Checking again in 60 seconds...")
                        # Show progress while waiting
                        self.progress.display_progress()
                        last_progress_update = time.time()
                        time.sleep(60)
                        continue
                    else:
                        # No more files to process
                        break

                # Submit batch of files to thread pool
                batch = ready_files[:config.BATCH_SIZE]
                futures = {
                    executor.submit(self.migrator.process_file, file_info): file_info
                    for file_info in batch
                }

                # Wait for completions and handle results
                for future in as_completed(futures):
                    file_info = futures[future]
                    try:
                        success = future.result()
                        if success:
                            files_completed += 1
                    except Exception as e:
                        print(f"  ERROR: {file_info['bucket']}/{file_info['key']}: {str(e)}")

                    # Show progress during batch processing if enough time has passed
                    current_time = time.time()
                    if current_time - last_progress_update >= config.PROGRESS_UPDATE_INTERVAL:
                        self.progress.display_progress()
                        last_progress_update = current_time


        # Final progress display
        print("\n" + "="*70)
        print("MIGRATION COMPLETE")
        print("="*70)
        self.progress.display_summary()

        # Check for errors
        error_files = self.state.get_files_by_state(FileState.ERROR)
        if error_files:
            print("\n" + "="*70)
            print(f"WARNING: {len(error_files)} file(s) encountered errors")
            print("="*70)
            for f in error_files[:10]:  # Show first 10
                print(f"  {f['bucket']}/{f['key']}")
                if f.get('error_message'):
                    print(f"    Error: {f['error_message']}")
            if len(error_files) > 10:
                print(f"  ... and {len(error_files) - 10} more")
            print("\nRun 'python migrate_s3.py status' to see full error details")
            print("="*70)

    def show_errors(self):
        """Display all files in ERROR state with details"""
        error_files = self.state.get_files_by_state(FileState.ERROR)

        if not error_files:
            print("No files in ERROR state.")
            return

        print("="*70)
        print(f"FILES IN ERROR STATE ({len(error_files)} total)")
        print("="*70)

        for f in error_files:
            print(f"\n{f['bucket']}/{f['key']}")
            print(f"  Size: {self._format_size(f['size'])}")
            print(f"  Storage: {f['storage_class']}")
            if f.get('error_message'):
                print(f"  Error: {f['error_message']}")
            print(f"  Last updated: {f['updated_at']}")

        print("\n" + "="*70)
        print("To retry these files, use: python migrate_s3.py retry-errors")
        print("="*70)

    def retry_errors(self):
        """Reset ERROR state files back to appropriate state for retry"""
        error_files = self.state.get_files_by_state(FileState.ERROR)

        if not error_files:
            print("No files in ERROR state to retry.")
            return

        print("="*70)
        print(f"RETRY ERROR FILES")
        print("="*70)
        print(f"Found {len(error_files)} file(s) in ERROR state\n")

        response = input("Reset these files to retry? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return

        for f in error_files:
            # Reset to DISCOVERED state for retry
            self.state.update_state(f['bucket'], f['key'], FileState.DISCOVERED)

        print(f"\n✓ Reset {len(error_files)} file(s) to DISCOVERED state")
        print("Run 'python migrate_s3.py migrate' to retry.\n")

    def reset_database(self):
        """Delete the state database to start fresh"""
        import os

        if os.path.exists(config.STATE_DB_PATH):
            print("="*70)
            print("RESET DATABASE")
            print("="*70)
            print(f"Database: {config.STATE_DB_PATH}\n")

            response = input("Are you sure you want to delete the database? (yes/no): ")
            if response.lower() == 'yes':
                os.remove(config.STATE_DB_PATH)
                print(f"\n✓ Database deleted: {config.STATE_DB_PATH}")
                print("Run 'python migrate_s3.py scan' to start fresh.\n")
            else:
                print("Reset cancelled.\n")
        else:
            print(f"No database found at: {config.STATE_DB_PATH}\n")

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
        description="S3 Bucket Migration Tool - Move S3 buckets to local storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrate_s3.py scan              # Scan all buckets
  python migrate_s3.py migrate           # Start migration (handles Glacier automatically)
  python migrate_s3.py status            # Show progress
  python migrate_s3.py errors            # Show files in ERROR state
  python migrate_s3.py retry-errors      # Retry failed files
  python migrate_s3.py reset             # Delete database and start fresh

Simple workflow:
  1. Edit config.py to set LOCAL_BASE_PATH
  2. python migrate_s3.py scan
  3. python migrate_s3.py migrate        # Handles everything, including Glacier
  4. python migrate_s3.py errors         # Check for any failures (if needed)
  5. python migrate_s3.py retry-errors   # Retry failed files (if any)

The migration is resilient and can be stopped/resumed at any time.
Glacier files are automatically detected, restored, and downloaded.
State is tracked in SQLite database for resumption.
Use 'reset' to delete the database and start over.
        """
    )

    parser.add_argument(
        'command',
        choices=['scan', 'migrate', 'status', 'glacier', 'errors', 'retry-errors', 'reset'],
        help='Command to execute'
    )

    parser.add_argument(
        '--buckets',
        nargs='+',
        help='Specific buckets to scan (default: all buckets)'
    )

    args = parser.parse_args()

    migration = S3Migration()

    try:
        if args.command == 'scan':
            migration.scan_buckets(args.buckets)

        elif args.command == 'status':
            migration.show_status()

        elif args.command == 'glacier':
            migration.process_glacier_files()

        elif args.command == 'migrate':
            migration.migrate()

        elif args.command == 'errors':
            migration.show_errors()

        elif args.command == 'retry-errors':
            migration.retry_errors()

        elif args.command == 'reset':
            migration.reset_database()

    except KeyboardInterrupt:
        print("\n\nMigration interrupted. State has been saved.")
        print("Run 'python migrate_s3.py migrate' to resume.\n")
        sys.exit(0)

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
