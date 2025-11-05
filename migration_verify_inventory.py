"""Local inventory helpers for migration verification."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

try:  # Prefer package-relative imports for tooling like pylint
    from .migration_utils import ProgressTracker
    from .migration_verify_common import MAX_ERROR_DISPLAY, should_ignore_key
except ImportError:  # pragma: no cover - allow running as standalone script
    from migration_utils import ProgressTracker
    from migration_verify_common import MAX_ERROR_DISPLAY, should_ignore_key

if TYPE_CHECKING:
    try:
        from .migration_state_v2 import MigrationStateV2
    except ImportError:  # pragma: no cover
        from migration_state_v2 import MigrationStateV2


def _load_expected_file_map(state: "MigrationStateV2", bucket: str) -> Dict[str, Dict]:
    print("  Loading file metadata from database...")
    expected_file_map: Dict[str, Dict] = {}
    with state.db_conn.get_connection() as conn:
        cursor = conn.execute("SELECT key, size, etag FROM files WHERE bucket = ?", (bucket,))
        for row in cursor:
            normalized_key = row["key"].replace("\\", "/")
            expected_file_map[normalized_key] = {"size": row["size"], "etag": row["etag"]}
    print(f"  Loaded {len(expected_file_map):,} file records")
    print()
    return expected_file_map


def _scan_local_directory(base_path: Path, bucket: str, expected_files: int) -> Dict[str, Path]:
    print("  Scanning local files...")
    local_path = base_path / bucket
    local_files: Dict[str, Path] = {}
    scan_count = 0
    progress = ProgressTracker(update_interval=2.0)
    for file_path in local_path.rglob("*"):
        if not file_path.is_file():
            continue
        relative_path = file_path.relative_to(local_path)
        s3_key = str(relative_path).replace("\\", "/")
        local_files[s3_key] = file_path
        scan_count += 1
        if progress.should_update() or scan_count % 10000 == 0:
            pct = (scan_count / expected_files * 100) if expected_files > 0 else 0
            status = f"Scanned: {scan_count:,} files ({pct:.1f}%)  "
            print(f"\r  {status}", end="", flush=True)
    print(f"\r  Found {len(local_files):,} local files" + " " * 30)
    print()
    return local_files


def _partition_inventory(
    expected_keys: Set[str], local_keys: Set[str]
) -> Tuple[Set[str], Set[str], int]:
    missing_files = expected_keys - local_keys
    extra_files_raw = local_keys - expected_keys
    extra_files = {key for key in extra_files_raw if not should_ignore_key(key)}
    ignored_count = len(extra_files_raw) - len(extra_files)
    return missing_files, extra_files, ignored_count


def _inventory_error_messages(missing_files: Set[str], extra_files: Set[str]) -> List[str]:
    errors: List[str] = []
    for key in list(missing_files)[:MAX_ERROR_DISPLAY]:
        errors.append(f"Missing file: {key}")
    if len(missing_files) > MAX_ERROR_DISPLAY:
        errors.append(f"... and {len(missing_files) - MAX_ERROR_DISPLAY} more missing files")
    for key in list(extra_files)[:MAX_ERROR_DISPLAY]:
        errors.append(f"Extra file (not in S3): {key}")
    if len(extra_files) > MAX_ERROR_DISPLAY:
        errors.append(f"... and {len(extra_files) - MAX_ERROR_DISPLAY} more extra files")
    return errors


def _validate_inventory(expected_keys: Set[str], local_keys: Set[str]) -> List[str]:
    print("  Checking file inventory...")
    missing_files, extra_files, ignored_count = _partition_inventory(expected_keys, local_keys)
    if ignored_count > 0:
        print(f"  ℹ Ignoring {ignored_count} system metadata file(s) (.DS_Store, Thumbs.db, etc.)")
    errors = _inventory_error_messages(missing_files, extra_files)
    if errors:
        print("  ✗ File inventory mismatch:")
        for error in errors:
            print(f"    - {error}")
        print()
        msg = f"File inventory check failed: {len(missing_files)} missing, {len(extra_files)} extra"
        raise ValueError(msg)
    return errors


class FileInventoryChecker:  # pylint: disable=too-few-public-methods
    """Checks local file inventory against expected files."""

    def __init__(self, state: "MigrationStateV2", base_path: Path):
        self.state = state
        self.base_path = base_path

    def load_expected_files(self, bucket: str) -> Dict[str, Dict]:
        """Load expected file metadata for the requested bucket."""
        return _load_expected_file_map(self.state, bucket)

    def scan_local_files(self, bucket: str, expected_files: int) -> Dict[str, Path]:
        """Scan the on-disk directory for the bucket and return discovered files."""
        return _scan_local_directory(self.base_path, bucket, expected_files)

    def check_inventory(self, expected_keys: Set[str], local_keys: Set[str]) -> List[str]:
        """Compare inventory results and raise when they differ."""
        return _validate_inventory(expected_keys, local_keys)


__all__ = ["FileInventoryChecker"]
