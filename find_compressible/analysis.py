"""File analysis and compression eligibility logic."""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterator, Sequence

from migration_utils import derive_local_path

IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "bmp",
    "tiff",
    "tif",
    "webp",
    "heic",
    "heif",
    "svg",
    "ico",
    "dng",
    "cr2",
    "nef",
}

VIDEO_EXTENSIONS = {
    "mp4",
    "m4v",
    "mov",
    "avi",
    "wmv",
    "mkv",
    "flv",
    "webm",
    "mpg",
    "mpeg",
    "3gp",
    "mts",
    "m2ts",
    "ts",
}

ALREADY_COMPRESSED_EXTENSIONS = {
    "xz",
    "gz",
    "gzip",
    "tgz",
    "bz2",
    "tbz",
    "tbz2",
    "zip",
    "rar",
    "zst",
    "lz",
    "lzma",
    "7z",
    "parquet",
    "vmdk",
    "ipa",
    "ipsw",
    "deb",
    "pkg",
    "dmg",
    "pdf",
    "pack",
    "keras",
    "so",
    "cfs",
    "mem",
    "db",
}


@dataclass
class CandidateFile:
    """Represents a file candidate for compression analysis."""

    bucket: str
    key: str
    size_bytes: int
    path: Path


def suffix_tokens(name: str) -> Sequence[str]:
    """Return lower-case suffix tokens without dots (handles multi-suffix files)."""
    return [suffix.lstrip(".").lower() for suffix in PurePosixPath(name).suffixes if suffix]


def _collect_unique_suffix_tokens(*names: str) -> list[str]:
    """Collect unique suffix tokens from all provided names."""
    tokens: list[str] = []
    for name in names:
        for token in suffix_tokens(name):
            if token not in tokens:
                tokens.append(token)
    return tokens


def _check_image_suffix(tokens: Sequence[str]) -> bool:
    """Check if any token matches image extensions."""
    return any(token in IMAGE_EXTENSIONS for token in tokens)


def _check_video_suffix(tokens: Sequence[str]) -> bool:
    """Check if any token matches video extensions."""
    return any(token in VIDEO_EXTENSIONS for token in tokens)


def _check_compressed_suffix(tokens: Sequence[str]) -> bool:
    """Check if any token matches already compressed extensions."""
    return any(token in ALREADY_COMPRESSED_EXTENSIONS for token in tokens)


def _check_numeric_suffix(tokens: Sequence[str]) -> bool:
    """Check if any token ends with a digit."""
    return any(token and token[-1].isdigit() for token in tokens)


def should_skip_by_suffix(*names: str) -> str | None:
    """Return a reason string if the file should be skipped based on suffix."""
    tokens = _collect_unique_suffix_tokens(*names)

    if _check_image_suffix(tokens):
        return "image"
    if _check_video_suffix(tokens):
        return "video"
    if _check_compressed_suffix(tokens):
        return "compressed"
    if _check_numeric_suffix(tokens):
        return "numeric_extension"
    return None


def candidate_rows(
    conn: sqlite3.Connection,
    min_size: int,
    buckets: Sequence[str],
) -> Iterator[sqlite3.Row]:
    """Yield rows that satisfy the coarse size (and optional bucket) filters."""
    sql = "SELECT bucket, key, size FROM files WHERE size >= ?"
    params: list[object] = [min_size]
    if buckets:
        placeholders = ",".join("?" for _ in buckets)
        sql += f" AND bucket IN ({placeholders})"
        params.extend(buckets)
    cursor = conn.execute(sql, params)
    yield from cursor


def find_candidates(
    conn: sqlite3.Connection,
    base_path: Path,
    min_size: int,
    buckets: Sequence[str],
    stats: Counter,
) -> Iterator[CandidateFile]:
    """Stream candidate files that look compressible."""
    for row in candidate_rows(conn, min_size=min_size, buckets=buckets):
        stats["rows_examined"] += 1
        bucket = row["bucket"]
        key = row["key"]
        local_path = derive_local_path(base_path, bucket, key)
        if local_path is None:
            stats["skipped_invalid_path"] += 1
            continue
        if not local_path.exists():
            stats["missing_local_files"] += 1
            continue
        if not local_path.is_file():
            stats["skipped_non_file"] += 1
            continue
        skip_reason = should_skip_by_suffix(key, local_path.name)
        if skip_reason:
            stats[f"skipped_{skip_reason}"] += 1
            continue
        actual_size = local_path.stat().st_size
        if actual_size < min_size:
            stats["skipped_now_below_threshold"] += 1
            continue
        if local_path.suffix.lower() == ".xz" or local_path.name.lower().endswith(".xz"):
            stats["skipped_already_xz"] += 1
            continue
        stats["candidates_found"] += 1
        yield CandidateFile(bucket=bucket, key=key, size_bytes=actual_size, path=local_path)
