"""
Core scanning logic for cleanup_temp_artifacts.

Provides the core candidate scanning functionality without database or cache dependencies.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from migration_utils import ProgressTracker, derive_local_path

from .categories import Category

PROGRESS_UPDATE_INTERVAL_SECONDS = 0.5


@dataclass
class Candidate:
    """Represents a candidate directory or file for cleanup."""

    path: Path
    category: Category
    size_bytes: int | None
    mtime: float

    @property
    def iso_mtime(self) -> str:
        """Return modification time as ISO format string."""
        return datetime.fromtimestamp(self.mtime, tz=timezone.utc).isoformat()


@dataclass
class CandidateLoadResult:
    """Result of loading cleanup candidates from database or cache."""

    candidates: list[Candidate]
    cache_path: Path | None
    cache_used: bool
    total_files: int
    max_rowid: int


class CandidateLoadError(RuntimeError):
    """Raised when the migration database cannot be queried."""


def iter_relevant_dirs(file_path: Path, base_path: Path) -> Iterator[Path]:
    """Yield ancestor directories under base_path (excluding base_path itself).

    Note:
        Silently yields nothing if file_path is outside base_path.
        This is intentional to allow callers to iterate without checking paths first.
    """
    try:
        file_path.relative_to(base_path)
    except ValueError:
        # file_path is outside base_path - yield nothing
        return
    current = file_path.parent
    while True:
        try:
            current.relative_to(base_path)
        except ValueError:
            break
        if current == base_path:
            break
        yield current
        current = current.parent


class MatcherError(RuntimeError):
    """Raised when a category matcher fails."""


def match_category(path: Path, is_dir: bool, categories: list[Category]) -> Category | None:
    """Find matching category for a given path using category matchers.

    Raises:
        MatcherError: If a category matcher raises an exception
    """
    for category in categories:
        try:
            if category.matcher(path, is_dir):
                return category
        except Exception as exc:
            raise MatcherError(f"Matcher {category.name} failed on {path}: {exc}") from exc
    return None


def _process_parent_directory(
    parent: Path,
    file_size: int,
    candidates: dict[Path, Candidate],
    non_matching: set[Path],
    *,
    categories: list[Category],
    cutoff_ts: float | None,
) -> None:
    """Process a single parent directory for inclusion in candidates.

    Note:
        Silently returns if the directory cannot be resolved (e.g., deleted during scan).
        This allows batch processing to continue for remaining directories.
    """
    try:
        canonical = parent.resolve()
    except OSError:
        # Directory may have been deleted during scan
        return

    entry = candidates.get(canonical)
    if entry:
        if entry.size_bytes is None:
            entry.size_bytes = file_size
        else:
            entry.size_bytes = entry.size_bytes + file_size
        return

    if canonical in non_matching:
        return

    category = match_category(parent, True, categories)
    if not category:
        non_matching.add(canonical)
        return

    try:
        stat = parent.stat()
    except OSError as exc:
        logging.warning("Unable to stat %s: %s", parent, exc)
        non_matching.add(canonical)
        return

    if cutoff_ts is not None and stat.st_mtime > cutoff_ts:
        non_matching.add(canonical)
        return

    candidates[canonical] = Candidate(
        path=parent,
        category=category,
        size_bytes=file_size,
        mtime=stat.st_mtime,
    )


def _filter_candidates_by_size(
    candidates: dict[Path, Candidate], min_size_bytes: int | None
) -> list[Candidate]:
    """Filter candidates by minimum size requirement."""
    results: list[Candidate] = []
    for candidate in candidates.values():
        if candidate.size_bytes is None:
            candidate.size_bytes = 0
        if min_size_bytes is not None and candidate.size_bytes < min_size_bytes:
            continue
        results.append(candidate)
    return results


def scan_candidates_from_db(
    conn: sqlite3.Connection,
    base_path: Path,
    categories: list[Category],
    *,
    cutoff_ts: float | None,
    min_size_bytes: int | None,
    total_files: int,
) -> list[Candidate]:
    """Inspect the migration SQLite database and find directories worth pruning."""
    base_path = base_path.resolve()
    progress = ProgressTracker(
        total=total_files,
        label="Scanning migration database",
        update_interval=PROGRESS_UPDATE_INTERVAL_SECONDS,
    )
    candidates: dict[Path, Candidate] = {}
    non_matching: set[Path] = set()

    if total_files == 0:
        progress.update(0)

    cursor = conn.execute("SELECT bucket, key, size FROM files")
    for idx, row in enumerate(cursor, start=1):
        progress.update(idx)
        local_file = derive_local_path(base_path, row["bucket"], row["key"])
        if local_file is None:
            continue
        file_size = row["size"] if row["size"] is not None else 0
        for parent in iter_relevant_dirs(local_file, base_path):
            _process_parent_directory(
                parent,
                file_size,
                candidates,
                non_matching,
                categories=categories,
                cutoff_ts=cutoff_ts,
            )
    progress.finish()
    return _filter_candidates_by_size(candidates, min_size_bytes)
