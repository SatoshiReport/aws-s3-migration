"""
Shared CLI utilities for common command-line patterns.

This module provides common CLI patterns used across multiple scripts.
"""


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
