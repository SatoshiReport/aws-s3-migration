"""Public API for duplicate tree detection plus CLI shim."""

# pylint: disable=import-outside-toplevel

from __future__ import annotations

from duplicate_tree_core import (
    DirectoryIndex,
    DuplicateCluster,
    find_exact_duplicates,
)

__all__ = [
    "DirectoryIndex",
    "DuplicateCluster",
    "find_exact_duplicates",
]


def main(argv=None) -> int:
    """Route to the CLI implementation."""
    import duplicate_tree_cli as cli  # pylint: disable=import-outside-toplevel

    return cli.main(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
