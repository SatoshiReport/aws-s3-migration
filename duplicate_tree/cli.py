"""CLI workflow for duplicate tree analysis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

try:  # Prefer package-relative imports when packaged
    import config as config_module
    from cost_toolkit.common.cli_utils import confirm_reset_state_db
    from duplicate_tree.analysis import (
        MIN_REPORT_BYTES,
        MIN_REPORT_FILES,
        build_directory_index_from_db,
        format_bytes,
        recompute_clusters_for_deletion,
    )
    from duplicate_tree.deletion import delete_duplicate_directories
    from duplicate_tree.workflow import (
        DuplicateAnalysisContext,
        load_or_compute_duplicates,
    )
    from state_db_admin import reseed_state_db_from_local_drive
except ImportError:  # pragma: no cover - execution as standalone script
    import config as config_module  # type: ignore[import]

    from analysis import (  # type: ignore[import]
        MIN_REPORT_BYTES,
        MIN_REPORT_FILES,
        build_directory_index_from_db,
        format_bytes,
        recompute_clusters_for_deletion,
    )
    from cost_toolkit.common.cli_utils import confirm_reset_state_db  # type: ignore[import]
    from deletion import delete_duplicate_directories  # type: ignore[import]
    from state_db_admin import reseed_state_db_from_local_drive  # type: ignore[import]
    from workflow import (  # type: ignore[import]
        DuplicateAnalysisContext,
        load_or_compute_duplicates,
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments controlling database path, base path, and tolerance."""
    parser = argparse.ArgumentParser(
        description=(
            "Detect exact duplicate directory trees on the external drive "
            "using migrate_v2's SQLite metadata."
        )
    )
    parser.add_argument(
        "--db-path",
        default=config_module.STATE_DB_PATH,
        help="Path to migration state SQLite DB (default: %(default)s).",
    )
    parser.add_argument(
        "--base-path",
        default=config_module.LOCAL_BASE_PATH,
        help="Root of the external drive (default: %(default)s).",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore cached duplicate analysis and recompute from scratch.",
    )
    parser.add_argument(
        "--min-files",
        type=int,
        default=MIN_REPORT_FILES,
        help="Minimum files per directory to include (default: %(default)s).",
    )
    parser.add_argument(
        "--min-size-gb",
        type=float,
        default=MIN_REPORT_BYTES / (1024**3),
        help="Minimum directory size (GiB) to include (default: %(default).2f).",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help=(
            "After reporting duplicates, delete every directory except the first entry "
            "in each cluster (requires confirmation)."
        ),
    )
    parser.add_argument(
        "--reset-state-db",
        action="store_true",
        help="Delete and recreate the migrate_v2 state DB before scanning.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation when using --reset-state-db.",
    )
    return parser.parse_args(argv)


def confirm_state_db_reset(db_path: Path, skip_prompt: bool) -> bool:
    """Prompt user to confirm state DB reset unless skip_prompt is True."""
    return confirm_reset_state_db(str(db_path), skip_prompt)


def handle_state_db_reset(
    base_path: Path, db_path: Path, should_reset: bool, skip_prompt: bool
) -> Path:
    """Reset state DB if requested and confirmed."""
    if not should_reset:
        return db_path
    if not confirm_state_db_reset(db_path, skip_prompt):
        print("State database reset cancelled; continuing without reset.")
        return db_path
    db_path, file_count, total_bytes = reseed_state_db_from_local_drive(base_path, db_path)
    print(
        f"✓ Recreated migrate_v2 state database at {db_path} "
        f"({file_count:,} files, {format_bytes(total_bytes)}). Continuing."
    )
    return db_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the duplicate tree report workflow."""
    args = parse_args(argv)
    base_path = Path(args.base_path).expanduser()
    db_path = Path(args.db_path).expanduser()

    db_path = handle_state_db_reset(base_path, db_path, args.reset_state_db, args.yes)

    if not db_path.exists():
        print(f"State DB not found at {db_path}. Run migrate_v2 first.", file=sys.stderr)
        return 1

    min_files = max(0, args.min_files)
    min_bytes = max(0, int(args.min_size_gb * (1024**3)))
    print(f"Using database: {db_path}")
    print(f"Assumed drive root: {base_path}")

    index, fingerprint = build_directory_index_from_db(str(db_path))
    base_path_str = str(base_path)
    can_cache_results = args.min_files == MIN_REPORT_FILES and min_bytes == MIN_REPORT_BYTES
    use_cache = (not args.refresh_cache) and can_cache_results

    context = DuplicateAnalysisContext(
        db_path=str(db_path),
        base_path=base_path,
        base_path_str=base_path_str,
        min_files=min_files,
        min_bytes=min_bytes,
        use_cache=use_cache,
        can_cache_results=can_cache_results,
    )

    cluster_rows, report_text = load_or_compute_duplicates(index, fingerprint, context)

    if report_text:
        print(report_text, end="" if report_text.endswith("\n") else "\n")

    if args.delete:
        if cluster_rows is None:
            print(
                "Cached report lacks structured duplicate data. "
                "Recomputing duplicates to prepare deletion plan..."
            )
            cluster_rows = recompute_clusters_for_deletion(index, min_files, min_bytes)
        delete_duplicate_directories(cluster_rows or [], base_path)

    print("Done.")
    return 0
