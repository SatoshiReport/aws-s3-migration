#!/usr/bin/env python3
"""
Duplicate tree detection leveraging migrate_v2's SQLite metadata.

This script reads the migration state database, reconstructs every directory tree
on the external drive, and reports exact as well as near-duplicate directories.
Exact duplicates require identical hierarchies plus matching file sizes and
checksums. Near duplicates allow a configurable similarity tolerance and explain
the deltas (missing/extra files or checksum mismatches).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

try:  # Prefer package-local config when packaged
    from . import config as config_module  # type: ignore
except ImportError:  # pragma: no cover - direct script execution
    import config as config_module  # type: ignore


PathTuple = Tuple[str, ...]
PROGRESS_MIN_INTERVAL = 0.2
MIN_DUPLICATE_CLUSTER = 2


class ChildSignatureMissingError(RuntimeError):
    """Raised when a directory node lacks a child signature during finalize."""

    def __init__(self, child_path: PathTuple) -> None:
        super().__init__(f"Child {child_path} missing signature during finalize.")


class FilesTableReadError(RuntimeError):
    """Raised when the SQLite files table cannot be read."""

    def __init__(self, db_path: str) -> None:
        super().__init__(
            f"Unable to read files table from {db_path!r}. Ensure migrate_v2 has initialized the database."
        )


@dataclass
class FileEntry:
    """Basic file metadata tracked for duplicate comparison."""

    name: str
    size: int
    checksum: str


@dataclass
class DirectoryNode:
    """Directory representation built from the metadata database."""

    path: PathTuple
    files: List[FileEntry] = field(default_factory=list)
    children: Set[PathTuple] = field(default_factory=set)
    direct_size: int = 0
    direct_files: int = 0
    total_size: int = 0
    total_files: int = 0
    signature: Optional[str] = None


@dataclass
class DuplicateCluster:
    """Exact duplicate cluster."""

    signature: str
    nodes: List[DirectoryNode]


@dataclass
class NearDuplicateReport:
    """Summary of an almost-identical directory pair."""

    primary: DirectoryNode
    secondary: DirectoryNode
    similarity: float
    file_delta: int
    size_delta: int
    differences: Dict[str, List[str]]


class ProgressPrinter:
    """Simple in-place progress bar."""

    def __init__(self, total: int, label: str, width: int = 30):
        self.total = total
        self.label = label
        self.width = width
        self._last_update = 0.0

    def update(self, processed: int, force: bool = False):
        now = time.time()
        if (
            not force
            and processed < self.total
            and (now - self._last_update) < PROGRESS_MIN_INTERVAL
        ):
            return
        self._last_update = now
        percent = (processed / self.total * 100.0) if self.total else 0.0
        filled = int(self.width * percent / 100.0) if self.total else 0
        bar = "#" * filled + "-" * (self.width - filled)
        message = (
            f"\r{self.label}: [{bar}] {percent:5.1f}% ({processed:,}/{self.total:,})"
            if self.total
            else f"\r{self.label}: {processed:,} entries processed"
        )
        print(message, end="", flush=True)
        if processed >= self.total:
            print()


class DirectoryIndex:
    """Builds directory nodes from file metadata."""

    def __init__(self):
        self.nodes: Dict[PathTuple, DirectoryNode] = {}

    def add_file(self, bucket: str, key: str, size: int, checksum: str):
        if not key or key.endswith("/"):  # Ignore directory placeholders
            return
        parts = [p for p in key.split("/") if p]
        if not parts:
            return
        filename = parts[-1]
        dir_parts = (bucket,) + tuple(parts[:-1]) if len(parts) > 1 else (bucket,)
        node = self._ensure_node(dir_parts)
        node.files.append(FileEntry(filename, size, checksum))
        node.direct_size += size
        node.direct_files += 1
        # Register intermediate directories
        for depth in range(1, len(dir_parts)):
            parent = dir_parts[:depth]
            child = dir_parts[: depth + 1]
            parent_node = self._ensure_node(parent)
            parent_node.children.add(child)

    def _ensure_node(self, path: PathTuple) -> DirectoryNode:
        if path not in self.nodes:
            self.nodes[path] = DirectoryNode(path=path)
        return self.nodes[path]

    def finalize(self):
        """Compute aggregate stats and signatures bottom-up."""
        for path in sorted(self.nodes, key=len, reverse=True):
            node = self.nodes[path]
            total_size = node.direct_size
            total_files = node.direct_files
            child_signatures: List[Tuple[str, str]] = []
            for child_path in sorted(node.children):
                child_node = self.nodes[child_path]
                total_size += child_node.total_size
                total_files += child_node.total_files
                if child_node.signature is None:
                    raise ChildSignatureMissingError(child_path)
                child_name = child_path[-1]
                child_signatures.append((child_name, child_node.signature))
            file_entries = sorted((f.name, f.size, f.checksum) for f in node.files)
            payload = json.dumps(
                {"files": file_entries, "dirs": child_signatures},
                separators=(",", ":"),
            )
            node.signature = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            node.total_size = total_size
            node.total_files = total_files


def build_directory_index_from_db(
    db_path: str, progress_label: str = "Scanning files"
) -> DirectoryIndex:
    """Stream the files table and construct the in-memory directory index."""
    index = DirectoryIndex()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        try:
            total_files = conn.execute(
                "SELECT COUNT(*) FROM files WHERE key NOT LIKE '%/'"
            ).fetchone()[0]
        except sqlite3.OperationalError as exc:
            raise FilesTableReadError(db_path) from exc
        progress = ProgressPrinter(total_files, progress_label)
        cursor = conn.execute(
            """
            SELECT bucket, key, size,
                   COALESCE(local_checksum, etag, '') AS checksum
            FROM files
            ORDER BY bucket, key
            """
        )
        for processed, row in enumerate(cursor, start=1):
            checksum = row["checksum"] or ""
            index.add_file(row["bucket"], row["key"], row["size"], checksum)
            progress.update(processed)
        progress.update(total_files, force=True)
    finally:
        conn.close()
    index.finalize()
    return index


def find_exact_duplicates(index: DirectoryIndex) -> List[DuplicateCluster]:
    """Group directories by identical signatures."""
    groups: Dict[str, List[DirectoryNode]] = {}
    for node in index.nodes.values():
        if node.signature is None:
            continue
        groups.setdefault(node.signature, []).append(node)
    clusters = []
    for signature, nodes in groups.items():
        if len(nodes) < MIN_DUPLICATE_CLUSTER:
            continue
        sorted_nodes = sorted(nodes, key=lambda n: (len(n.path), n.path))
        clusters.append(DuplicateCluster(signature=signature, nodes=sorted_nodes))
    return sorted(clusters, key=lambda c: (len(c.nodes[0].path), c.nodes[0].path))


def _similar_enough(a: int, b: int, tolerance: float) -> bool:
    larger = max(a, b) or 1
    ratio = min(a, b) / larger
    return ratio >= tolerance


def _path_tuple_to_str(path: PathTuple) -> str:
    return "/".join(path)


def _format_diff_paths(paths: Iterable[PathTuple], limit: int = 5) -> List[str]:
    formatted = []
    for idx, path in enumerate(paths):
        if idx >= limit:
            formatted.append("...")
            break
        formatted.append("/".join(path))
    return formatted


def _manifest_builder(index: DirectoryIndex):
    @lru_cache(maxsize=None)
    def build(path: PathTuple) -> Dict[PathTuple, FileEntry]:
        node = index.nodes[path]
        manifest: Dict[PathTuple, FileEntry] = {}
        for file_entry in node.files:
            manifest[(file_entry.name,)] = file_entry
        for child in node.children:
            child_manifest = build(child)
            child_name = child[-1]
            for rel_path, entry in child_manifest.items():
                manifest[(child_name,) + rel_path] = entry
        return manifest

    return build


def _compare_manifests(
    manifest_a: Dict[PathTuple, FileEntry],
    manifest_b: Dict[PathTuple, FileEntry],
) -> Dict[str, List[PathTuple]]:
    missing = []
    extra = []
    mismatched = []
    for path, entry in manifest_a.items():
        other = manifest_b.get(path)
        if other is None:
            missing.append(path)
            continue
        if entry.size != other.size or entry.checksum != other.checksum:
            mismatched.append(path)
    for path in manifest_b.keys() - manifest_a.keys():
        extra.append(path)
    return {"missing": missing, "extra": extra, "mismatched": mismatched}


def _candidate_peers(
    nodes: Sequence[DirectoryNode],
    start_idx: int,
    anchor: DirectoryNode,
    tolerance: float,
) -> Iterator[DirectoryNode]:
    """Yield candidate directories with comparable size and file counts."""
    for candidate in nodes[start_idx:]:
        if not _similar_enough(anchor.total_size, candidate.total_size, tolerance):
            break  # sizes only get larger thanks to sorting
        if _similar_enough(anchor.total_files, candidate.total_files, tolerance):
            yield candidate


def _build_near_duplicate_report(
    primary: DirectoryNode,
    secondary: DirectoryNode,
    manifest_cache: Callable[[PathTuple], Dict[PathTuple, FileEntry]],
) -> Optional[NearDuplicateReport]:
    """Return a report describing differences, or None if directories match exactly."""
    manifest_a = manifest_cache(primary.path)
    manifest_b = manifest_cache(secondary.path)
    deltas = _compare_manifests(manifest_a, manifest_b)
    formatted_deltas = {key: _format_diff_paths(paths) for key, paths in deltas.items() if paths}
    if not formatted_deltas:
        return None
    total_delta_bytes = abs(primary.total_size - secondary.total_size)
    total_delta_files = abs(primary.total_files - secondary.total_files)
    size_similarity = min(primary.total_size, secondary.total_size) / (
        max(primary.total_size, secondary.total_size) or 1
    )
    file_similarity = min(primary.total_files, secondary.total_files) / (
        max(primary.total_files, secondary.total_files) or 1
    )
    similarity = min(size_similarity, file_similarity)
    return NearDuplicateReport(
        primary=primary,
        secondary=secondary,
        similarity=similarity,
        file_delta=total_delta_files,
        size_delta=total_delta_bytes,
        differences=formatted_deltas,
    )


def find_near_duplicates(index: DirectoryIndex, tolerance: float) -> List[NearDuplicateReport]:
    """Identify high-similarity directories that differ slightly."""
    nodes = [node for node in index.nodes.values() if node.total_files > 0]
    nodes.sort(key=lambda n: n.total_size)
    reports: List[NearDuplicateReport] = []
    manifest_cache = _manifest_builder(index)
    for idx, node in enumerate(nodes):
        for candidate in _candidate_peers(nodes, idx + 1, node, tolerance):
            report = _build_near_duplicate_report(node, candidate, manifest_cache)
            if report:
                reports.append(report)
    return reports


def _path_on_disk(base_path: Path, node: DirectoryNode) -> Path:
    return base_path.joinpath(*node.path)


def _print_duplicate_clusters(clusters: Sequence[DuplicateCluster], base_path: Path) -> None:
    if not clusters:
        print("No exact duplicate directories found.")
        return
    print()
    print("=" * 70)
    print("EXACT DUPLICATE TREES")
    print("=" * 70)
    for idx, cluster in enumerate(clusters, start=1):
        representative = cluster.nodes[0]
        print(
            f"[{idx}] {representative.total_files:,} files, " f"{representative.total_size:,} bytes"
        )
        for node in cluster.nodes:
            print(f"  - {_path_on_disk(base_path, node)}")
        print()


def _print_near_duplicates(reports: Sequence[NearDuplicateReport], base_path: Path) -> None:
    if not reports:
        print("No near-duplicate directories within tolerance.")
        return
    print("=" * 70)
    print("NEAR DUPLICATES WITH MINOR DELTAS")
    print("=" * 70)
    for idx, report in enumerate(reports, start=1):
        print(
            f"[{idx}] Similarity: {report.similarity*100:.2f}% | "
            f"Δ files: {report.file_delta:,}, Δ bytes: {report.size_delta:,}"
        )
        print(f"  A: {_path_on_disk(base_path, report.primary)}")
        print(f"  B: {_path_on_disk(base_path, report.secondary)}")
        for label, paths in report.differences.items():
            print(f"    {label.capitalize()}: {', '.join(paths)}")
        print()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect duplicate or near-duplicate directory trees on the external drive "
            "using migrate_v2's SQLite metadata."
        )
    )
    parser.add_argument(
        "--db-path",
        default=config_module.STATE_DB_PATH,
        help="Path to migration state SQLite DB (default: %(default)s).",
    )
    parser.add_argument(
        "--base-path",
        default=config_module.LOCAL_BASE_PATH,
        help="Root of the external drive (default: %(default)s).",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.99,
        help="Minimum similarity ratio (0-1) to report near duplicates (default: 0.99).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"State DB not found at {db_path}. Run migrate_v2 first.", file=sys.stderr)
        return 1
    base_path = Path(args.base_path)
    print(f"Using database: {db_path}")
    print(f"Assumed drive root: {base_path}")
    index = build_directory_index_from_db(str(db_path))
    clusters = find_exact_duplicates(index)
    near_duplicates = find_near_duplicates(index, tolerance=args.tolerance)
    _print_duplicate_clusters(clusters, base_path)
    _print_near_duplicates(near_duplicates, base_path)
    print("Done.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
