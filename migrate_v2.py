#!/usr/bin/env python3
"""
S3 Bucket Migration Script V2 - Optimized with AWS CLI sync.

This script safely migrates all files from S3 buckets to local storage:
1. Scans all buckets and detects Glacier files
2. Requests Glacier restores (90 days)
3. Waits for all Glacier restores to complete
4. For each bucket (one at a time):
   a. Downloads using AWS CLI (aws s3 sync)
   b. Verifies files locally
   c. Deletes from S3 after manual confirmation

Each bucket is completed fully before moving to the next.
Interrupted migrations resume from the last incomplete bucket.

Usage:
    python migrate_v2.py           # Run/resume migration
    python migrate_v2.py status    # Show current status
    python migrate_v2.py reset     # Reset and start over
"""
import argparse
import signal
import sys
from pathlib import Path

import boto3

try:  # Prefer package-relative imports when linting
    from . import config as config_module
except ImportError:  # pragma: no cover - allow running as standalone script
    import config as config_module  # type: ignore

LOCAL_BASE_PATH = config_module.LOCAL_BASE_PATH
STATE_DB_PATH = config_module.STATE_DB_PATH
config = config_module  # expose module for tests
try:  # Prefer package-relative imports for tooling
    from .migration_orchestrator import (
        BucketMigrationOrchestrator,
        BucketMigrator,
        StatusReporter,
    )
    from .migration_scanner import BucketScanner, GlacierRestorer, GlacierWaiter
    from .migration_state_v2 import MigrationStateV2, Phase
except ImportError:  # pragma: no cover - allow running as standalone script
    from migration_orchestrator import (
        BucketMigrationOrchestrator,
        BucketMigrator,
        StatusReporter,
    )
    from migration_scanner import BucketScanner, GlacierRestorer, GlacierWaiter
    from migration_state_v2 import MigrationStateV2, Phase


def reset_migration_state():
    """Reset all state and start from beginning"""
    import os  # pylint: disable=import-outside-toplevel

    print("\n" + "=" * 70)
    print("RESET MIGRATION")
    print("=" * 70)
    print()
    print("This will delete all migration state and start over.")
    print("Local files will NOT be deleted.")
    print()
    response = input("Are you sure? (yes/no): ")
    if response.lower() == "yes":
        if os.path.exists(STATE_DB_PATH):
            os.remove(STATE_DB_PATH)
            print()
            print("✓ State database deleted")
            print("Run 'python migrate_v2.py' to start fresh")
        else:
            print()
            print("No state database found")
    else:
        print()
        print("Reset cancelled")


class DriveChecker:  # pylint: disable=too-few-public-methods
    """Handles checking if destination drive is available and writable"""

    def __init__(self, base_path: Path):
        self.base_path = base_path

    def check_available(self):
        """Check if the destination drive is mounted and writable"""
        parent = self.base_path.parent
        if not parent.exists():
            print()
            print("=" * 70)
            print("DRIVE NOT AVAILABLE")
            print("=" * 70)
            print("The destination drive is not mounted:")
            print(f"  Expected: {parent}")
            print()
            print("Please:")
            print("  1. Connect your external drive")
            print("  2. Ensure it's mounted at the correct location")
            print("  3. Run the migration again")
            print("=" * 70)
            sys.exit(1)
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            print()
            print("=" * 70)
            print("PERMISSION DENIED")
            print("=" * 70)
            print("Cannot write to destination:")
            print(f"  Path: {self.base_path}")
            print()
            print("Please check:")
            print("  1. The drive is properly mounted")
            print("  2. You have write permissions")
            print("=" * 70)
            sys.exit(1)


class S3MigrationV2:  # pylint: disable=too-many-instance-attributes
    """Main orchestrator for S3 to local migration using AWS CLI"""

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments  # noqa: PLR0913
        self,
        state: MigrationStateV2,
        drive_checker: DriveChecker,
        scanner: BucketScanner,
        glacier_restorer: GlacierRestorer,
        glacier_waiter: GlacierWaiter,
        migration_orchestrator: BucketMigrationOrchestrator,
        bucket_migrator: BucketMigrator,
        status_reporter: StatusReporter,
    ):
        self.state = state
        self.drive_checker = drive_checker
        self.scanner = scanner
        self.glacier_restorer = glacier_restorer
        self.glacier_waiter = glacier_waiter
        self.bucket_migrator = bucket_migrator
        self.migration_orchestrator = migration_orchestrator
        self.status_reporter = status_reporter
        self.interrupted = False
        signal.signal(signal.SIGINT, self._signal_handler)

    def _set_interrupted_flags(self):
        """Set interrupted flags on all components"""
        self.interrupted = True
        self.scanner.interrupted = True
        self.glacier_restorer.interrupted = True
        self.glacier_waiter.interrupted = True
        self.bucket_migrator.interrupted = True
        self.bucket_migrator.syncer.interrupted = True
        self.migration_orchestrator.interrupted = True

    def _signal_handler(self, _signum, _frame):
        """Handle Ctrl+C gracefully"""
        self._set_interrupted_flags()
        print("\n" + "=" * 70)
        print("MIGRATION INTERRUPTED")
        print("=" * 70)
        print("State has been saved.")
        print("Run 'python migrate_v2.py' to resume from where you left off.")
        print("=" * 70)
        sys.exit(0)

    def run(self):
        """Main entry point - determines current phase and continues"""
        print("\n" + "=" * 70)
        print("S3 MIGRATION V2 - OPTIMIZED WITH AWS CLI")
        print("=" * 70)
        print(f"Destination: {LOCAL_BASE_PATH}")
        print(f"State DB: {STATE_DB_PATH}")
        print()
        self.drive_checker.check_available()
        current_phase = self.state.get_current_phase()
        if current_phase == Phase.COMPLETE:
            print("✓ Migration already complete!")
            self.status_reporter.show_status()
            return
        print(f"Resuming from: {current_phase.value}")
        print()
        if current_phase == Phase.SCANNING:
            self.scanner.scan_all_buckets()
            current_phase = Phase.GLACIER_RESTORE
        if current_phase == Phase.GLACIER_RESTORE:
            self.glacier_restorer.request_all_restores()
            current_phase = Phase.GLACIER_WAIT
        if current_phase == Phase.GLACIER_WAIT:
            self.glacier_waiter.wait_for_restores()
            current_phase = Phase.SYNCING
        if current_phase == Phase.SYNCING:
            self.migration_orchestrator.migrate_all_buckets()
            current_phase = self.state.get_current_phase()
        if current_phase == Phase.COMPLETE:
            self._print_completion_message()

    def _print_completion_message(self):
        """Print migration completion message"""
        self.state.set_current_phase(Phase.COMPLETE)
        print("\n" + "=" * 70)
        print("✓ MIGRATION COMPLETE!")
        print("=" * 70)
        print("All files have been migrated and verified.")
        print("All S3 buckets have been deleted.")
        print("=" * 70)

    def show_status(self):
        """Display current migration status"""
        self.status_reporter.show_status()

    def reset(self):
        """Reset all state and start from beginning"""
        reset_migration_state()


def create_migrator() -> S3MigrationV2:
    """Factory function to create S3MigrationV2 with all dependencies"""
    state = MigrationStateV2(config.STATE_DB_PATH)
    s3 = boto3.client("s3")
    base_path = Path(config.LOCAL_BASE_PATH)
    drive_checker = DriveChecker(base_path)
    scanner = BucketScanner(s3, state)
    glacier_restorer = GlacierRestorer(s3, state)
    glacier_waiter = GlacierWaiter(s3, state)
    bucket_migrator = BucketMigrator(s3, state, base_path)
    migration_orchestrator = BucketMigrationOrchestrator(
        s3, state, base_path, drive_checker, bucket_migrator
    )
    status_reporter = StatusReporter(state)
    return S3MigrationV2(
        state,
        drive_checker,
        scanner,
        glacier_restorer,
        glacier_waiter,
        migration_orchestrator,
        bucket_migrator,
        status_reporter,
    )


def main():
    """Main entry point for S3 migration"""
    parser = argparse.ArgumentParser(
        description="S3 Bucket Migration Tool V2 - Optimized with AWS CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["status", "reset"],
        help="Command to execute (default: run migration)",
    )
    args = parser.parse_args()
    migrator = create_migrator()
    if args.command == "status":
        migrator.show_status()
    elif args.command == "reset":
        migrator.reset()
    else:
        migrator.run()


if __name__ == "__main__":
    main()
