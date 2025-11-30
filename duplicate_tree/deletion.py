"""Directory deletion logic for duplicate trees."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Sequence

from cost_toolkit.common.cli_utils import confirm_action

from .analysis import (
    ClusterRow,
    NodeRow,
    format_bytes,
    path_on_disk,
    sort_node_rows,
)

MIN_DUPLICATE_NODES = 2


def build_deletion_groups(
    cluster_rows: Sequence[ClusterRow],
) -> tuple[List[tuple[int, NodeRow, List[NodeRow]]], int, int]:
    """Build list of deletion groups with keep/delete nodes and calculate totals."""
    deletion_groups = []
    total_bytes = 0
    total_dirs = 0
    for idx, cluster in enumerate(cluster_rows, start=1):
        nodes = sort_node_rows(cluster["nodes"])
        if len(nodes) < MIN_DUPLICATE_NODES:
            continue
        keep_node = nodes[0]
        delete_nodes = nodes[1:]
        deletion_groups.append((idx, keep_node, delete_nodes))
        total_bytes += sum(node["total_size"] for node in delete_nodes)
        total_dirs += len(delete_nodes)
    return deletion_groups, total_bytes, total_dirs


def print_deletion_plan(
    deletion_groups: Sequence[tuple[int, NodeRow, List[NodeRow]]], base_path: Path
):
    """Display deletion plan showing which directories will be kept and deleted."""
    print("\nDeletion plan (keeping the first directory shown per cluster):")
    for cluster_idx, keep_node, delete_nodes in deletion_groups:
        keep_path = path_on_disk(base_path, tuple(keep_node["path"]))
        print(f"[{cluster_idx}] Keep {keep_path}")
        for node in delete_nodes:
            delete_path = path_on_disk(base_path, tuple(node["path"]))
            print(f"    delete {format_bytes(node['total_size']):>12}  {delete_path}")
        print()


def confirm_deletion(total_dirs: int, total_bytes: int) -> bool:
    """Prompt user to confirm deletion of directories. Delegates to canonical implementation."""
    prompt = f"Delete {total_dirs} directories ({format_bytes(total_bytes)})? [y/N]: "
    return confirm_action(prompt)


def perform_deletions(
    deletion_groups: Sequence[tuple[int, NodeRow, List[NodeRow]]], base_path: Path
) -> List[tuple[Path, Exception]]:
    """Execute deletion of duplicate directories, returning any errors encountered."""
    errors: List[tuple[Path, Exception]] = []
    for _, _, delete_nodes in deletion_groups:
        for node in delete_nodes:
            path = path_on_disk(base_path, tuple(node["path"]))
            if not path.exists():
                print(f"Skipping missing directory: {path}")
                continue
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink()
                else:
                    shutil.rmtree(path)
                print(f"Deleted {path}")
            except (OSError, PermissionError) as exc:
                errors.append((path, exc))
                print(f"Error deleting {path}: {exc}")
    return errors


def delete_duplicate_directories(cluster_rows: Sequence[ClusterRow], base_path: Path):
    """Delete every duplicate directory except the first entry in each cluster."""
    deletion_groups, total_bytes, total_dirs = build_deletion_groups(cluster_rows)

    if not deletion_groups:
        print("No duplicate directories meet the delete criteria.")
        return

    print_deletion_plan(deletion_groups, base_path)

    if not confirm_deletion(total_dirs, total_bytes):
        print("Deletion cancelled.")
        return

    errors = perform_deletions(deletion_groups, base_path)

    if errors:
        print(f"Completed with {len(errors)} error(s).")
    else:
        print("Deletion complete.")
