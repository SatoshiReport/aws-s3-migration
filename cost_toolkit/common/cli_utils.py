"""
Shared CLI utilities for common command-line patterns.

This module provides common CLI patterns used across multiple scripts.
"""


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
