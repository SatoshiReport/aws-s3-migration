"""Public API for duplicate tree detection plus CLI shim."""

# pylint: disable=import-outside-toplevel

from __future__ import annotations

try:  # Prefer package-relative imports when packaged
    from .duplicate_tree_core import (
        DirectoryIndex,
        DuplicateCluster,
        NearDuplicateReport,
        find_exact_duplicates,
        find_near_duplicates,
    )
except ImportError:  # pragma: no cover - direct script execution
    from duplicate_tree_core import (  # type: ignore
        DirectoryIndex,
        DuplicateCluster,
        NearDuplicateReport,
        find_exact_duplicates,
        find_near_duplicates,
    )

__all__ = [
    "DirectoryIndex",
    "DuplicateCluster",
    "NearDuplicateReport",
    "find_exact_duplicates",
    "find_near_duplicates",
]


def main(argv=None) -> int:
    """Route to the CLI implementation."""
    try:
        from . import (
            duplicate_tree_cli as cli,  # type: ignore  # pylint: disable=import-outside-toplevel
        )
    except ImportError:  # pragma: no cover
        import duplicate_tree_cli as cli  # type: ignore  # pylint: disable=import-outside-toplevel
    return cli.main(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
