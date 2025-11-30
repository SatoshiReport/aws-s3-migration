"""Shared confirmation prompts for bulk cleanup workflows."""

from __future__ import annotations

from cost_toolkit.common.cli_utils import confirm_action


def confirm_bulk_deletion() -> bool:
    """Prompt for confirming snapshot bulk deletion."""
    return confirm_action(
        "Type 'DELETE ALL SNAPSHOTS' to confirm bulk deletion: ",
        exact_match="DELETE ALL SNAPSHOTS",
    )


def confirm_deregistration() -> bool:
    """Prompt for confirming AMI deregistration."""
    return confirm_action(
        "Type 'DEREGISTER ALL AMIS' to confirm bulk deregistration: ",
        exact_match="DEREGISTER ALL AMIS",
    )


def confirm_snapshot_deletion() -> bool:
    """Prompt for confirming freed snapshot deletion."""
    return confirm_action(
        "Type 'DELETE FREED SNAPSHOTS' to confirm deletion: ",
        exact_match="DELETE FREED SNAPSHOTS",
    )
