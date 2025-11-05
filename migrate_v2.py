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
import hashlib
import shutil
import signal
import sys
import tempfile
from dataclasses import dataclass
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


@dataclass(frozen=True)
class MigrationComponents:
    """Aggregates the orchestration helpers required by S3MigrationV2."""

    drive_checker: DriveChecker
    scanner: BucketScanner
    glacier_restorer: GlacierRestorer
    glacier_waiter: GlacierWaiter
    migration_orchestrator: BucketMigrationOrchestrator
    bucket_migrator: BucketMigrator
    status_reporter: StatusReporter


class S3MigrationV2:  # pylint: disable=too-many-instance-attributes
    """Main orchestrator for S3 to local migration using AWS CLI"""

    def __init__(self, state: MigrationStateV2, components: MigrationComponents):
        self.state = state
        self.drive_checker = components.drive_checker
        self.scanner = components.scanner
        self.glacier_restorer = components.glacier_restorer
        self.glacier_waiter = components.glacier_waiter
        self.bucket_migrator = components.bucket_migrator
        self.migration_orchestrator = components.migration_orchestrator
        self.status_reporter = components.status_reporter
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
    components = MigrationComponents(
        drive_checker=drive_checker,
        scanner=scanner,
        glacier_restorer=glacier_restorer,
        glacier_waiter=glacier_waiter,
        migration_orchestrator=migration_orchestrator,
        bucket_migrator=bucket_migrator,
        status_reporter=status_reporter,
    )
    return S3MigrationV2(state, components)


def _materialize_sample_tree(root: Path):
    """Create nested directories and files for smoke testing."""
    structure = {
        "photos/2022/summer": ["beach.txt", "mountain.txt"],
        "photos/2023/winter": ["ski.txt", "snowman.txt"],
        "docs/reports": ["q1.md", "q2.md", "summary.md"],
        "logs/app/server": ["2024-01.log", "2024-02.log", "2024-03.log"],
        "data/json": ["users.json", "inventory.json"],
    }
    file_count = 0
    dir_count = 0
    total_bytes = 0
    root.mkdir(parents=True, exist_ok=True)
    for relative_dir, files in structure.items():
        dir_path = root / relative_dir
        dir_path.mkdir(parents=True, exist_ok=True)
        dir_count += 1
        for filename in files:
            file_path = dir_path / filename
            content = (
                f"Sample data for {filename}\n"
                f"Directory: {relative_dir}\n"
                "Generated by migrate_v2.py --test\n"
            )
            file_path.write_text(content, encoding="utf-8")
            file_count += 1
            total_bytes += file_path.stat().st_size
    return file_count, dir_count, total_bytes


def _manifest_directory(root: Path):
    """Return a manifest of files and hashed contents for validation."""
    manifest = {}
    for file_path in sorted(root.rglob("*")):
        if file_path.is_file():
            hasher = hashlib.sha256()
            hasher.update(file_path.read_bytes())
            manifest[file_path.relative_to(root).as_posix()] = hasher.hexdigest()
    return manifest


def run_smoke_test():
    """Create sample data, back it up, delete it, and report results."""
    print("\n" + "=" * 70)
    print("RUNNING LOCAL SMOKE TEST")
    print("=" * 70)
    temp_dir = Path(tempfile.mkdtemp(prefix="migrate_v2_test_"))
    source_dir = temp_dir / "source_data"
    backup_dir = temp_dir / "backup_data"
    should_cleanup = True
    try:
        files_created, dirs_created, total_bytes = _materialize_sample_tree(source_dir)
        print(
            f"Created {dirs_created} directories and {files_created} files ({total_bytes} bytes)."
        )
        print(f"Source directory: {source_dir}")
        manifest_before = _manifest_directory(source_dir)
        shutil.copytree(source_dir, backup_dir)
        print(f"Backed up data to: {backup_dir}")
        manifest_after = _manifest_directory(backup_dir)
        if manifest_before != manifest_after:
            raise RuntimeError("Backup verification failed - manifests do not match")
        shutil.rmtree(source_dir)
        print("Deleted source data after verified backup.")
        shutil.rmtree(backup_dir)
        print("Deleted backup data to keep workspace clean.")
        print("\nSmoke test completed successfully!")
        print("=" * 70)
        print("SMOKE TEST REPORT")
        print("=" * 70)
        print(f"Files processed : {files_created}")
        print(f"Directories used: {dirs_created}")
        print(f"Total data      : {total_bytes} bytes")
        print("Flow            : create -> backup -> verify -> delete -> cleanup")
        print("=" * 70)
    except Exception as exc:  # pragma: no cover - diagnostic helper
        should_cleanup = False
        print("\nSmoke test failed!")
        print(f"Reason: {exc}")
        print(f"Temporary files retained at: {temp_dir}")
        raise
    finally:
        if should_cleanup:
            shutil.rmtree(temp_dir, ignore_errors=True)


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
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run a local smoke test that simulates the backup workflow",
    )
    args = parser.parse_args()
    if args.test:
        run_smoke_test()
        return
    migrator = create_migrator()
    if args.command == "status":
        migrator.show_status()
    elif args.command == "reset":
        migrator.reset()
    else:
        migrator.run()


if __name__ == "__main__":
    main()
