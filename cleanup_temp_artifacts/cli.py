"""
Command-line interface and main entry point for cleanup_temp_artifacts.

Handles workflow orchestration and user interaction.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

try:  # Shared state DB utilities.
    from .state_db_admin import reseed_state_db_from_local_drive  # type: ignore
except ImportError:  # pragma: no cover - direct script execution
    from state_db_admin import reseed_state_db_from_local_drive  # type: ignore

from cost_toolkit.common.cli_utils import handle_state_db_reset

from .args_parser import parse_args
from .cache import build_scan_params
from .config import REPO_ROOT
from .reports import (
    delete_paths,
    order_candidates,
    print_candidates_report,
    write_reports,
)
from .scanner import (
    CacheConfig,
    CandidateLoadError,
    DatabaseInfo,
    load_candidates_from_db,
    write_cache_if_needed,
)


def _setup_paths(args: argparse.Namespace) -> tuple[Path, Path, os.stat_result] | int:
    """Set up base and database paths. Returns (base_path, db_path, db_stat) or error code."""
    base_path = Path(args.base_path).expanduser()
    if not base_path.exists():
        logging.error("Base path %s does not exist.", base_path)
        return 1
    base_path = base_path.resolve()

    db_path = Path(args.db_path).expanduser()
    if not db_path.is_absolute():
        db_path = (REPO_ROOT / db_path).resolve()
    else:
        db_path = db_path.resolve()

    db_path = handle_state_db_reset(
        base_path, db_path, args.reset_state_db, args.yes, reseed_state_db_from_local_drive
    )

    if not db_path.exists():
        logging.error("SQLite database %s does not exist.", db_path)
        return 1
    db_path = db_path.resolve()
    db_stat = db_path.stat()

    return base_path, db_path, db_stat


def _handle_deletion(args: argparse.Namespace, acted_upon: list, base_path: Path) -> int:
    """Handle deletion logic. Returns exit code."""
    if not args.delete:
        print("\nDry run only (use --delete --yes to remove the listed entries).")
        return 0

    if not args.yes:
        resp = input(f"\nDelete {len(acted_upon)} entry(ies)? [y/N] ").strip().lower()
        if resp not in {"y", "yes"}:
            print("Aborted by user.")
            return 0

    errors = delete_paths(acted_upon, root=base_path.resolve())
    if errors:
        print(f"Completed with {len(errors)} error(s); see log for details.")
        return 2
    print("Deletion complete.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point for cleanup_temp_artifacts CLI."""
    args = parse_args(argv or sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    setup_result = _setup_paths(args)
    if isinstance(setup_result, int):
        return setup_result
    base_path, db_path, db_stat = setup_result

    cutoff_ts: float | None = None
    if args.older_than:
        cutoff_ts = time.time() - (args.older_than * 86400)

    if not args.delete:
        print("Dry run: no directories will be deleted. Use --delete --yes to remove them.\n")

    scan_params = build_scan_params(args.categories, args.older_than, args.min_size_bytes)
    try:
        load_result = load_candidates_from_db(
            args=args,
            base_path=base_path,
            db_path=db_path,
            db_stat=db_stat,
            cutoff_ts=cutoff_ts,
            scan_params=scan_params,
        )
    except CandidateLoadError:
        logging.exception("Failed to load candidates from database")
        return 1

    cache_config = CacheConfig(
        enabled=args.cache_enabled,
        cache_dir=args.cache_dir,
        refresh_cache=args.refresh_cache,
        cache_ttl=args.cache_ttl,
    )
    db_info = DatabaseInfo(
        db_path=db_path,
        db_stat=db_stat,
        total_files=load_result.total_files,
        max_rowid=load_result.max_rowid,
    )
    write_cache_if_needed(
        cache_config,
        load_result,
        cache_path=load_result.cache_path,
        cache_used=load_result.cache_used,
        base_path=base_path,
        db_info=db_info,
        scan_params=scan_params,
    )

    if not load_result.candidates:
        print("No candidates found for the selected categories.")
        return 0

    ordered = order_candidates(load_result.candidates, order=args.sort)
    acted_upon = ordered[: args.limit] if args.limit else ordered

    print_candidates_report(load_result.candidates, acted_upon, base_path)
    write_reports(ordered, json_path=args.report_json, csv_path=args.report_csv)

    return _handle_deletion(args, acted_upon, base_path)
