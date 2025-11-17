"""
Shared CLI utilities for common command-line patterns.

This module provides common CLI patterns used across multiple scripts.
"""

import argparse
from typing import Callable, Optional

from cost_toolkit.common.format_utils import format_bytes


def create_migration_cli_parser(
    description: str,
    db_path_default: str,
    base_path_default: str,
    add_custom_args: Optional[Callable[[argparse.ArgumentParser], None]] = None,
) -> argparse.ArgumentParser:
    """
    Create a standard ArgumentParser for migration-related CLI tools.

    This is the canonical factory for CLIs that operate on the migrate_v2 state database.
    It handles common arguments (--db-path, --base-path, --reset-state-db, --yes) and
    allows customization via a callback for module-specific arguments.

    Args:
        description: CLI description for the ArgumentParser
        db_path_default: Default value for --db-path (typically from config.STATE_DB_PATH)
        base_path_default: Default value for --base-path (typically from config.LOCAL_BASE_PATH)
        add_custom_args: Optional callback function that receives the parser and adds
                        module-specific arguments. Called after standard args are added
                        but before add_reset_state_db_args.

    Returns:
        Configured ArgumentParser with standard migration CLI arguments

    Example:
        def add_module_args(parser):
            parser.add_argument("--compress", action="store_true")

        parser = create_migration_cli_parser(
            description="Compress large files",
            db_path_default=STATE_DB_PATH,
            base_path_default=LOCAL_BASE_PATH,
            add_custom_args=add_module_args
        )
        args = parser.parse_args()
    """
    parser = argparse.ArgumentParser(description=description)

    # Add standard migration CLI arguments
    parser.add_argument(
        "--db-path",
        default=db_path_default,
        help=f"Path to migration state SQLite DB (default: {db_path_default}).",
    )
    parser.add_argument(
        "--base-path",
        default=base_path_default,
        help=f"Root of the external drive (default: {base_path_default}).",
    )

    # Allow module-specific arguments to be added
    if add_custom_args is not None:
        add_custom_args(parser)

    # Add state DB reset arguments (common to all migration CLIs)
    add_reset_state_db_args(parser)

    return parser


def confirm_action(message, skip_prompt=False, exact_match=None):
    """
    Prompt user to confirm an action with flexible confirmation patterns.

    Args:
        message: Prompt message to display to the user
        skip_prompt: If True, skip confirmation and return True
        exact_match: If provided, user must type this exact string to confirm
                    If None, accepts 'y' or 'yes' (case-insensitive)

    Returns:
        bool: True if user confirmed or prompt was skipped, False otherwise

    Examples:
        # Simple yes/no confirmation
        if confirm_action("Delete files?"):
            delete_files()

        # Exact match confirmation for dangerous operations
        if confirm_action("Type 'DELETE ALL' to confirm: ", exact_match="DELETE ALL"):
            delete_all()

        # Skip prompt in automated scripts
        if confirm_action("Continue?", skip_prompt=args.yes):
            continue_operation()
    """
    if skip_prompt:
        return True

    try:
        response = input(message).strip()
    except EOFError:
        print("\nConfirmation not received.")
        return False

    if exact_match is not None:
        return response == exact_match

    return response.lower() in {"y", "yes"}


def add_reset_state_db_args(parser):
    """
    Add common --reset-state-db and --yes arguments to an argument parser.

    Args:
        parser: argparse.ArgumentParser instance to add arguments to

    Returns:
        The same parser instance (for chaining)
    """
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
    return parser


def confirm_reset_state_db(db_path, skip_prompt=False):
    """
    Prompt user to confirm resetting the state database.

    Args:
        db_path: Path to the database file
        skip_prompt: If True, skip confirmation and return True

    Returns:
        bool: True if user confirmed or prompt was skipped, False otherwise
    """
    if skip_prompt:
        return True
    resp = (
        input(
            f"Reset migrate_v2 state database at {db_path}? "
            "This deletes cached migration metadata. [y/N] "
        )
        .strip()
        .lower()
    )
    return resp in {"y", "yes"}


def handle_state_db_reset(
    base_path,
    db_path,
    should_reset,
    skip_prompt,
    reseed_function,
):
    """
    Handle state database reset workflow with confirmation.

    This is the canonical implementation used by all scripts that need to reset
    the migrate_v2 state database.

    Args:
        base_path: Path to the base directory to scan
        db_path: Path to the database file
        should_reset: Whether reset was requested
        skip_prompt: If True, skip confirmation prompts
        reseed_function: Function to call for reseeding (takes base_path, db_path)
                        Should return (db_path, file_count, total_bytes)

    Returns:
        Path: The database path (unchanged if reset not performed)
    """
    if not should_reset:
        return db_path

    if not confirm_reset_state_db(str(db_path), skip_prompt):
        print("State database reset cancelled; continuing without reset.")
        return db_path

    new_db_path, file_count, total_bytes = reseed_function(base_path, db_path)
    size_summary = format_bytes(total_bytes, use_comma_separators=True)
    print(
        f"✓ Recreated migrate_v2 state database at {new_db_path} "
        f"({file_count:,} files, {size_summary}). Continuing."
    )
    return new_db_path
