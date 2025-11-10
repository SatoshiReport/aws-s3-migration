"""
Core scanning logic for cleanup_temp_artifacts.

Provides the core candidate scanning functionality without database or cache dependencies.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterator

from cleanup_temp_artifacts.categories import Category

PROGRESS_UPDATE_INTERVAL_SECONDS = 0.5


@dataclass
class Candidate:
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
    candidates: list[Candidate]
    cache_path: Path | None
    cache_used: bool
    total_files: int
    max_rowid: int


class CandidateLoadError(RuntimeError):
    """Raised when the migration database cannot be queried."""


def derive_local_path(base_path: Path, bucket: str, key: str) -> Path | None:
    """Convert a bucket/key pair into the expected local filesystem path."""
    candidate = base_path / bucket
    for part in PurePosixPath(key).parts:
        if part in ("", "."):
            continue
        if part == "..":
            return None
        candidate /= part
    try:
        candidate.relative_to(base_path)
    except ValueError:
        return None
    return candidate


def iter_relevant_dirs(file_path: Path, base_path: Path) -> Iterator[Path]:
    """Yield ancestor directories under base_path (excluding base_path itself)."""
    try:
        file_path.relative_to(base_path)
    except ValueError:
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


class ProgressTracker:
    """Minimal progress indicator for long-running scans."""

    def __init__(self, total: int, label: str):
        self.total = total
        self.label = label
        self.start = time.time()
        self.last_print = 0.0

    def update(self, current: int):
        """Update progress display if update interval has elapsed."""
        now = time.time()
        if current == self.total or now - self.last_print >= PROGRESS_UPDATE_INTERVAL_SECONDS:
            if self.total:
                pct = (current / self.total) * 100
                status = f"{current:,}/{self.total:,} ({pct:5.1f}%)"
            else:
                status = f"{current:,}"
            print(f"\r{self.label}: {status}", end="", flush=True)
            self.last_print = now

    def finish(self):
        """Print final newline to complete progress display."""
        print()


def match_category(path: Path, is_dir: bool, categories: list[Category]) -> Category | None:
    """Find matching category for a given path using category matchers."""
    for category in categories:
        try:
            if category.matcher(path, is_dir):
                return category
        # Defensive: user-provided matchers may raise any exception; log and continue
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logging.warning("Matcher %s failed on %s: %s", category.name, path, exc)
    return None


def _process_parent_directory(
    parent: Path,
    file_size: int,
    candidates: dict[Path, Candidate],
    non_matching: set[Path],
    categories: list[Category],
    cutoff_ts: float | None,
) -> None:
    """Process a single parent directory for inclusion in candidates."""
    try:
        canonical = parent.resolve()
    except OSError:
        return

    entry = candidates.get(canonical)
    if entry:
        entry.size_bytes = (entry.size_bytes or 0) + file_size
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
        size_bytes = candidate.size_bytes or 0
        if min_size_bytes is not None and size_bytes < min_size_bytes:
            continue
        candidate.size_bytes = size_bytes
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
    progress = ProgressTracker(total_files, "Scanning migration database")
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
        file_size = row["size"] or 0
        for parent in iter_relevant_dirs(local_file, base_path):
            _process_parent_directory(
                parent, file_size, candidates, non_matching, categories, cutoff_ts
            )
    progress.finish()
    return _filter_candidates_by_size(candidates, min_size_bytes)
