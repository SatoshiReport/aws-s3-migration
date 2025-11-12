"""
Argument parsing for cleanup_temp_artifacts CLI.

Handles command-line argument definition, parsing, and validation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .cache import _default_cache_dir
from .categories import build_categories
from .config import DEFAULT_BASE_PATH, DEFAULT_DB_PATH
from .reports import parse_size


def _add_path_arguments(parser: argparse.ArgumentParser) -> None:
    """Add path-related arguments."""
    base_help = "Local base path containing migrated bucket folders."
    if DEFAULT_BASE_PATH:
        base_help += f" Default: {DEFAULT_BASE_PATH}."
    parser.add_argument(
        "--base-path",
        default=str(DEFAULT_BASE_PATH) if DEFAULT_BASE_PATH else None,
        help=base_help,
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to migration SQLite database (default: {DEFAULT_DB_PATH}).",
    )


def _add_filter_arguments(parser: argparse.ArgumentParser, categories: dict[str, str]) -> None:
    """Add filtering and sorting arguments."""
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=sorted(categories),
        default=sorted(categories),
        help="Categories to include (default: all).",
    )
    parser.add_argument(
        "--older-than", type=int, metavar="DAYS", help="Only include entries older than DAYS."
    )
    parser.add_argument(
        "--min-size",
        type=str,
        help="Only include entries >= SIZE (e.g. 500M).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of entries acted on (heaviest first when sorting by size).",
    )
    parser.add_argument(
        "--sort",
        choices={"path", "size"},
        default="path",
        help="Order used when reporting/deleting.",
    )


def _add_action_arguments(parser: argparse.ArgumentParser) -> None:
    """Add action and confirmation arguments."""
    parser.add_argument(
        "--reset-state-db",
        action="store_true",
        help="Delete and recreate the migrate_v2 state DB before scanning.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the matched entries. Default is dry-run/report only.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts for destructive actions (deletes, DB reset).",
    )


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    """Add output and reporting arguments."""
    parser.add_argument(
        "--report-json", type=Path, help="Optional path to write the full candidate list as JSON."
    )
    parser.add_argument("--report-csv", type=Path, help="Optional path to write the report as CSV.")
    parser.add_argument(
        "--list-categories", action="store_true", help="List available categories and exit."
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")


def _add_cache_arguments(parser: argparse.ArgumentParser) -> None:
    """Add caching-related arguments."""
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Directory for cached scan results (default: ~/.cache/cleanup_temp_artifacts).",
    )
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=43200,
        help=(
            "Reuse cached scans younger than TTL seconds (default: 43200). "
            "Set <=0 to disable TTL expiration."
        ),
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Force a fresh scan even if cache metadata matches the database.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache reads and writes entirely.",
    )


def _add_parser_arguments(parser: argparse.ArgumentParser, categories: dict[str, str]) -> None:
    """Add all command-line arguments to the parser."""
    _add_path_arguments(parser)
    _add_filter_arguments(parser, categories)
    _add_action_arguments(parser)
    _add_output_arguments(parser)
    _add_cache_arguments(parser)


def _validate_and_transform_args(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    categories: dict,
) -> None:
    """Validate and transform parsed arguments."""
    if args.list_categories:
        for cat in categories.values():
            print(f"{cat.name:20} {cat.description}")
        sys.exit(0)
    if not args.base_path:
        parser.error("--base-path is required when no default could be determined.")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive.")
    args.min_size_bytes = parse_size(args.min_size) if args.min_size else None
    args.categories = [categories[name] for name in args.categories]
    args.cache_dir = Path(args.cache_dir).expanduser() if args.cache_dir else _default_cache_dir()
    args.cache_enabled = not args.no_cache


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse and process command-line arguments for cleanup_temp_artifacts."""
    categories = build_categories()
    parser = argparse.ArgumentParser(
        description=(
            "Scan backup trees for disposable cache/temp artifacts and optionally delete them."
        )
    )
    _add_parser_arguments(parser, categories)
    args = parser.parse_args(argv)
    _validate_and_transform_args(args, parser, categories)
    return args
