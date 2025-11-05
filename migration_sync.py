"""Bucket syncing using AWS CLI"""

import subprocess
import time
from pathlib import Path

try:  # Prefer package-relative imports for tooling
    from .migration_state_v2 import MigrationStateV2
    from .migration_utils import ProgressTracker, format_duration, format_size
except ImportError:  # pragma: no cover - allow running as standalone script
    from migration_state_v2 import MigrationStateV2
    from migration_utils import ProgressTracker, format_duration, format_size


def check_sync_process_errors(process):
    """Check for sync errors in stderr"""
    stderr_output = process.stderr.read()
    if stderr_output:
        error_lines = [
            line for line in stderr_output.split("\n") if line.strip() and "Completed" not in line
        ]
    else:
        error_lines = []
    if process.returncode != 0:
        error_msg = f"aws s3 sync failed with return code {process.returncode}"
        if error_lines:
            error_msg += "\n\nError details:\n" + "\n".join(error_lines)
        raise RuntimeError(error_msg)


class BucketSyncer:  # pylint: disable=too-few-public-methods
    """Handles syncing a bucket using AWS CLI"""

    def __init__(self, s3, state: MigrationStateV2, base_path: Path):
        self.s3 = s3
        self.state = state
        self.base_path = base_path
        self.interrupted = False

    def sync_bucket(self, bucket: str):
        """Sync bucket from S3 to local using AWS CLI"""
        local_path = self.base_path / bucket
        local_path.mkdir(parents=True, exist_ok=True)
        s3_url = f"s3://{bucket}/"
        local_url = str(local_path) + "/"
        cmd = ["aws", "s3", "sync", s3_url, local_url, "--no-progress"]
        print(f"  Running: aws s3 sync {s3_url} {local_url}")
        print()
        start_time = time.time()
        # pylint: disable=consider-using-with
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        files_done, bytes_done = self._monitor_sync_progress(process, start_time)
        self._check_sync_errors(process)
        self._print_sync_summary(start_time, files_done, bytes_done)

    def _monitor_sync_progress(self, process, start_time):
        """Monitor AWS CLI sync progress and return stats"""
        progress = ProgressTracker(update_interval=1.0)
        files_done = 0
        bytes_done = 0
        while True:
            if self.interrupted:
                process.terminate()
                return files_done, bytes_done
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line and "Completed" in line:
                file_bytes = self._parse_aws_size(line)
                if file_bytes:
                    bytes_done += file_bytes
                    files_done += 1
                if progress.should_update():
                    self._display_progress(start_time, files_done, bytes_done)
        return files_done, bytes_done

    def _check_sync_errors(self, process):
        """Check for sync errors"""
        check_sync_process_errors(process)

    def _parse_aws_size(self, line: str):
        """Parse byte size from AWS CLI output line"""
        try:
            parts = line.split()
            size_str = parts[-1]
            multiplier = 1
            if size_str.endswith("KiB"):
                multiplier = 1024
            elif size_str.endswith("MiB"):
                multiplier = 1024 * 1024
            elif size_str.endswith("GiB"):
                multiplier = 1024 * 1024 * 1024
            size_val = float(size_str.split()[0])
            return int(size_val * multiplier)
        except (ValueError, IndexError, AttributeError):
            return None

    def _display_progress(self, start_time, files_done, bytes_done):
        """Display progress"""
        elapsed = time.time() - start_time
        if elapsed > 0 and bytes_done > 0:
            throughput = bytes_done / elapsed
            progress = (
                f"Progress: {files_done:,} files, {format_size(bytes_done)} "
                f"({format_size(throughput)}/s)  "
            )
            print(f"\r  {progress}", end="", flush=True)

    def _print_sync_summary(self, start_time, files_done, bytes_done):
        """Print sync completion summary"""
        elapsed = time.time() - start_time
        throughput = bytes_done / elapsed if elapsed > 0 else 0
        print(f"\n✓ Completed in {format_duration(elapsed)}")
        print(f"  Downloaded: {files_done:,} files, {format_size(bytes_done)}")
        print(f"  Throughput: {format_size(throughput)}/s")
        print()
