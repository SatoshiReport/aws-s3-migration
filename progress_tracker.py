"""
Progress tracking and display for S3 migration.
Shows elapsed time, ETA, current progress, and throughput.
"""
import time
from datetime import datetime, timedelta
from typing import Optional
from migration_state import MigrationState


class ProgressTracker:
    """
    Tracks and displays migration progress with ETA calculations.
    """

    def __init__(self, state: MigrationState):
        self.state = state
        self.session_start_time = time.time()  # When THIS session started
        self.last_update = time.time()
        self.last_completed_bytes = 0
        self.last_completed_files = 0

    def display_progress(self):
        """Display current progress with statistics"""
        from datetime import datetime, timezone

        completed_files, total_files, completed_bytes, total_bytes = self.state.get_progress()

        # Calculate percentages
        file_percent = (completed_files / total_files * 100) if total_files > 0 else 0
        byte_percent = (completed_bytes / total_bytes * 100) if total_bytes > 0 else 0

        # Get migration runtime info
        runtime_info = self.state.get_migration_runtime_info()

        # Calculate session elapsed time
        session_elapsed = time.time() - self.session_start_time
        session_elapsed_str = self._format_duration(session_elapsed)

        # Calculate total elapsed time from migration start (not database creation)
        migration_start_time = runtime_info.get('migration_start_time')
        if migration_start_time:
            start_dt = datetime.fromisoformat(migration_start_time)
            # Make timezone-aware if it's naive
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            total_elapsed = (now_dt - start_dt).total_seconds()
            total_elapsed_str = self._format_duration(total_elapsed)
        else:
            total_elapsed = session_elapsed
            total_elapsed_str = session_elapsed_str

        # Calculate throughput and ETA
        current_time = time.time()
        time_delta = current_time - self.last_update

        if time_delta > 0:
            bytes_delta = completed_bytes - self.last_completed_bytes
            throughput = bytes_delta / time_delta

            if throughput > 0 and completed_bytes < total_bytes:
                remaining_bytes = total_bytes - completed_bytes
                eta_seconds = remaining_bytes / throughput
                eta_str = self._format_duration(eta_seconds)
            else:
                eta_str = "calculating..."
        else:
            throughput = 0
            eta_str = "calculating..."

        # Update last values
        self.last_update = current_time
        self.last_completed_bytes = completed_bytes
        self.last_completed_files = completed_files

        # Get state statistics
        stats = self.state.get_statistics()

        # Display progress
        print(f"\n{'='*70}")
        print(f"MIGRATION PROGRESS")
        print(f"{'='*70}")

        # Only show total elapsed if migration has started
        if migration_start_time:
            print(f"Total Elapsed:   {total_elapsed_str} (since migration started)")
        print(f"Session Time:    {session_elapsed_str} (this run)")

        if migration_start_time:
            print(f"ETA:             {eta_str}")
        print(f"")

        # Calculate files/data remaining
        files_remaining = total_files - completed_files
        bytes_remaining = total_bytes - completed_bytes

        print(f"Files:           {completed_files:,} / {total_files:,} ({file_percent:.1f}%)")
        print(f"  Completed:     {completed_files:,} files")
        print(f"  Remaining:     {files_remaining:,} files")
        print(f"")
        print(f"Data:            {self._format_size(completed_bytes)} / {self._format_size(total_bytes)} ({byte_percent:.1f}%)")
        print(f"  Downloaded:    {self._format_size(completed_bytes)}")
        print(f"  Remaining:     {self._format_size(bytes_remaining)}")

        if migration_start_time:
            print(f"")
            print(f"Throughput:      {self._format_size(throughput)}/s (current session)")

        # Show overall average throughput
        if migration_start_time and total_elapsed > 0 and completed_bytes > 0:
            overall_throughput = completed_bytes / total_elapsed
            print(f"Overall Avg:     {self._format_size(overall_throughput)}/s (since start)")

            # Calculate files per second
            if total_elapsed > 0:
                files_per_sec = completed_files / total_elapsed
                print(f"File Rate:       {files_per_sec:.2f} files/sec (overall)")

        print(f"")
        print(f"Status Breakdown:")

        state_order = [
            'discovered',
            'glacier_restore_requested',
            'glacier_restoring',
            'downloading',
            'downloaded',
            'verified',
            'deleted',
            'error'
        ]

        for state_name in state_order:
            if state_name in stats:
                state_info = stats[state_name]
                count = state_info['count']
                size = state_info['size']
                print(f"  {state_name.replace('_', ' ').title():25} {count:6,} files  {self._format_size(size):>12}")

        # Show storage class breakdown for discovered files (fast query)
        from migration_state import FileState
        discovered_breakdown = self.state.get_storage_class_breakdown(FileState.DISCOVERED)
        if discovered_breakdown:
            print(f"")
            print(f"  Discovered files by storage class:")

            # Show each storage class with its count
            for storage_class in sorted(discovered_breakdown.keys()):
                info = discovered_breakdown[storage_class]
                count = info['count']
                size = info['size']

                # Mark Glacier storage classes
                if storage_class in ['GLACIER', 'DEEP_ARCHIVE']:
                    marker = " (needs restore)"
                else:
                    marker = " (ready)"

                print(f"    {storage_class:25}{marker:20} {count:6,} files  {self._format_size(size):>12}")

        print(f"{'='*70}\n")

    def display_summary(self):
        """Display final summary"""
        from datetime import datetime, timezone

        completed_files, total_files, completed_bytes, total_bytes = self.state.get_progress()
        session_elapsed = time.time() - self.session_start_time
        session_elapsed_str = self._format_duration(session_elapsed)

        # Get migration runtime info
        runtime_info = self.state.get_migration_runtime_info()

        # Calculate total elapsed time from migration start (not database creation)
        migration_start_time = runtime_info.get('migration_start_time')
        if migration_start_time:
            start_dt = datetime.fromisoformat(migration_start_time)
            # Make timezone-aware if it's naive
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            total_elapsed = (now_dt - start_dt).total_seconds()
            total_elapsed_str = self._format_duration(total_elapsed)
        else:
            total_elapsed = session_elapsed
            total_elapsed_str = session_elapsed_str

        session_throughput = completed_bytes / session_elapsed if session_elapsed > 0 else 0
        overall_throughput = completed_bytes / total_elapsed if total_elapsed > 0 else 0

        print(f"\n{'='*70}")
        print(f"MIGRATION COMPLETE")
        print(f"{'='*70}")
        print(f"Total Time:             {total_elapsed_str} (since migration started)")
        print(f"Session Time:           {session_elapsed_str} (this run)")
        print(f"Files Migrated:         {completed_files:,} / {total_files:,}")
        print(f"Data Migrated:          {self._format_size(completed_bytes)} / {self._format_size(total_bytes)}")
        print(f"Session Throughput:     {self._format_size(session_throughput)}/s")
        print(f"Overall Avg Throughput: {self._format_size(overall_throughput)}/s")
        print(f"{'='*70}\n")

    def print_current_status(self):
        """Print simple one-line status"""
        completed_files, total_files, completed_bytes, total_bytes = self.state.get_progress()
        file_percent = (completed_files / total_files * 100) if total_files > 0 else 0
        byte_percent = (completed_bytes / total_bytes * 100) if total_bytes > 0 else 0

        print(f"Progress: {completed_files:,}/{total_files:,} files ({file_percent:.1f}%), "
              f"{self._format_size(completed_bytes)}/{self._format_size(total_bytes)} ({byte_percent:.1f}%)")

    @staticmethod
    def _format_size(bytes_size: float) -> str:
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
