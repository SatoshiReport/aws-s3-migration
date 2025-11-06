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

import hashlib
import json
import time
from functools import lru_cache
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Sequence

try:  # Prefer package-local imports when packaged
    from .duplicate_tree_models import (
        ChildSignatureMissingError,
        DirectoryNode,
        DuplicateCluster,
        FileEntry,
        NearDuplicateReport,
        PathTuple,
        ProgressPrinter,
    )
except ImportError:  # pragma: no cover - direct script execution
    from duplicate_tree_models import (  # type: ignore
        ChildSignatureMissingError,
        DirectoryNode,
        DuplicateCluster,
        FileEntry,
        NearDuplicateReport,
        PathTuple,
        ProgressPrinter,
    )


MIN_DUPLICATE_CLUSTER = 2


class DirectoryIndex:
    """Builds directory nodes from file metadata."""

    def __init__(self):
        self.nodes: Dict[PathTuple, DirectoryNode] = {}

    def add_file(self, bucket: str, key: str, size: int, checksum: str):
        """Add a file entry to the proper directory node hierarchy."""
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
            child_signatures: List[tuple[str, str]] = []
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


def find_exact_duplicates(index: DirectoryIndex) -> List[DuplicateCluster]:
    """Group directories by identical signatures."""
    groups: Dict[str, List[DirectoryNode]] = {}
    nodes = list(index.nodes.values())
    total = len(nodes)
    progress = ProgressPrinter(total, "Grouping directories")
    start_time = time.time()
    processed = 0
    try:
        for processed, node in enumerate(nodes, start=1):
            if node.signature is None:
                continue
            groups.setdefault(node.signature, []).append(node)
            progress.update(processed)
    except KeyboardInterrupt:
        print("\n\n✗ Duplicate grouping interrupted by user.")
        raise
    finally:
        elapsed = time.time() - start_time
        progress.finish(
            f"Grouping directories processed {processed:,}/{total:,} entries in {elapsed:.1f}s"
        )
    clusters = []
    for signature, sig_nodes in groups.items():
        if len(sig_nodes) < MIN_DUPLICATE_CLUSTER:
            continue
        sorted_nodes = sorted(sig_nodes, key=lambda n: (len(n.path), n.path))
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
    total = len(nodes)
    progress = ProgressPrinter(total, "Comparing near duplicates")
    start_time = time.time()
    reports: List[NearDuplicateReport] = []
    manifest_cache = _manifest_builder(index)
    processed = 0
    try:
        for idx, node in enumerate(nodes):
            processed = idx + 1
            progress.update(processed)
            for candidate in _candidate_peers(nodes, idx + 1, node, tolerance):
                report = _build_near_duplicate_report(node, candidate, manifest_cache)
                if report:
                    reports.append(report)
    except KeyboardInterrupt:
        print("\n\n✗ Near-duplicate comparison interrupted by user.")
        raise
    finally:
        elapsed = time.time() - start_time
        progress.finish(
            f"Comparing near duplicates processed {processed:,}/{total:,} entries in {elapsed:.1f}s"
        )
    return reports
