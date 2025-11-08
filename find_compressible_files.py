#!/usr/bin/env python3
"""Locate large locally downloaded objects that should compress well with xz and optionally compress them with verification."""
# ruff: noqa: TRY003 - CLI emits user-focused errors with contextual messages

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterator, Sequence

# Ensure the repository root is importable even when this script is run via an absolute path.
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from config import LOCAL_BASE_PATH, STATE_DB_PATH
except ImportError as exc:  # pragma: no cover - failure is fatal for this CLI
    raise SystemExit(f"Unable to import config module: {exc}") from exc

try:  # Shared helper for resetting migrate_v2 state DB.
    from .state_db_admin import reseed_state_db_from_local_drive
except ImportError:  # pragma: no cover - direct script execution
    from state_db_admin import reseed_state_db_from_local_drive  # type: ignore

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

BYTES_PER_UNIT = 1024
DEFAULT_MIN_SIZE = 512 * 1024 * 1024  # 512 MiB


@dataclass
class CandidateFile:
    bucket: str
    key: str
    size_bytes: int
    path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan the SQLite migration database for large, locally downloaded files that are "
            "likely to compress well with xz -9. Images, videos, and already compressed files "
            "are automatically skipped."
        )
    )
    parser.add_argument(
        "--db-path",
        default=STATE_DB_PATH,
        help=f"Path to migration SQLite database (default: {STATE_DB_PATH})",
    )
    parser.add_argument(
        "--base-path",
        default=LOCAL_BASE_PATH,
        help=f"Base path of the external drive (default: {LOCAL_BASE_PATH})",
    )
    parser.add_argument(
        "--min-size",
        type=parse_size,
        default=DEFAULT_MIN_SIZE,
        help="Minimum file size to consider (accepts suffixes like 512M, 2G). Default: 512M",
    )
    parser.add_argument(
        "--bucket",
        action="append",
        dest="buckets",
        default=[],
        help="Optional bucket filter. Repeat --bucket for multiple buckets.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after reporting this many candidates (0 means no limit).",
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        help="Compress each reported file in-place using `xz -9e`. Disabled by default.",
    )
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
    return parser.parse_args()


def parse_size(value: str) -> int:
    """Parse human-friendly sizes like 512M or 2G into bytes."""
    raw = value.strip().lower()
    if not raw:
        raise argparse.ArgumentTypeError("Size cannot be empty")
    multipliers = {
        "k": BYTES_PER_UNIT,
        "m": BYTES_PER_UNIT**2,
        "g": BYTES_PER_UNIT**3,
        "t": BYTES_PER_UNIT**4,
    }
    suffix = raw[-1]
    if suffix in multipliers:
        number = raw[:-1]
        try:
            base = float(number)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid size value: {value}") from exc
        return int(base * multipliers[suffix])
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - arg parsing
        raise argparse.ArgumentTypeError(f"Invalid size value: {value}") from exc


def format_size(num: int) -> str:
    """Return a human-friendly size string."""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if num < BYTES_PER_UNIT or unit == "TiB":
            return f"{num:,.2f} {unit}"
        num /= BYTES_PER_UNIT
    return f"{num:,.2f} PiB"


def suffix_tokens(name: str) -> Sequence[str]:
    """Return lower-case suffix tokens without dots (handles multi-suffix files)."""
    return [suffix.lstrip(".").lower() for suffix in PurePosixPath(name).suffixes if suffix]


def should_skip_by_suffix(*names: str) -> str | None:  # noqa: C901, PLR0912
    """Return a reason string if the file should be skipped based on suffix."""
    tokens: list[str] = []
    for name in names:
        for token in suffix_tokens(name):
            if token not in tokens:
                tokens.append(token)
    for token in tokens:
        if token in IMAGE_EXTENSIONS:
            return "image"
    for token in tokens:
        if token in VIDEO_EXTENSIONS:
            return "video"
    for token in tokens:
        if token in ALREADY_COMPRESSED_EXTENSIONS:
            return "compressed"
    for token in tokens:
        if token and token[-1].isdigit():
            return "numeric_extension"
    return None


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


def compress_with_xz(path: Path) -> Path:
    """Compress `path` using xz -9e while keeping the original for verification."""
    cmd = ["xz", "--keep", "-9e", str(path)]
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("xz binary not found. Install xz-utils to enable compression.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"xz failed for {path} (exit {exc.returncode}). stderr: {exc.stderr.strip()}"
        ) from exc
    return Path(str(path) + ".xz")


def verify_compressed_file(path: Path) -> None:
    """Run `xz -t` to verify the compressed output."""
    cmd = ["xz", "-t", str(path)]
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - same binary as compress
        raise SystemExit("xz binary not found. Install xz-utils to enable compression.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"xz verification failed for {path} (exit {exc.returncode}). stderr: {exc.stderr.strip()}"
        ) from exc


def main() -> None:  # noqa: C901, PLR0912, PLR0915
    args = parse_args()
    base_path = Path(args.base_path).expanduser()
    if not base_path.exists():
        raise SystemExit(f"Base path does not exist: {base_path}")
    if args.buckets:
        buckets = sorted(set(args.buckets))
    else:
        buckets = []

    db_path = Path(args.db_path).expanduser()
    reset_confirmed = False
    if args.reset_state_db:
        if args.yes:
            reset_confirmed = True
        else:
            resp = (
                input(
                    f"Reset migrate_v2 state database at {db_path}? "
                    "This deletes cached migration metadata. [y/N] "
                )
                .strip()
                .lower()
            )
            reset_confirmed = resp in {"y", "yes"}
            if not reset_confirmed:
                print("State database reset cancelled; continuing without reset.")
    if reset_confirmed:
        db_path, file_count, total_bytes = reseed_state_db_from_local_drive(base_path, db_path)
        print(
            f"✓ Recreated migrate_v2 state database at {db_path} "
            f"({file_count:,} files, {format_size(total_bytes)}). Continuing."
        )
    if not db_path.exists():
        raise SystemExit(f"State DB not found at {db_path}. Run migrate_v2 first.")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    stats: Counter = Counter()

    try:
        all_candidates = sorted(
            find_candidates(
                conn=conn,
                base_path=base_path,
                min_size=args.min_size,
                buckets=buckets,
                stats=stats,
            ),
            key=lambda item: item.size_bytes,
            reverse=True,
        )
    finally:
        conn.close()

    if args.limit:
        reported_candidates = all_candidates[: args.limit]
    else:
        reported_candidates = all_candidates

    total_reported = len(reported_candidates)
    index_width = max(2, len(str(total_reported))) if total_reported else 2
    total_bytes = sum(candidate.size_bytes for candidate in reported_candidates)

    compressed_files = 0
    compression_failures = 0
    total_original_space = 0
    total_compressed_space = 0
    reported_extensions: set[str] = set()

    for idx, candidate in enumerate(reported_candidates, start=1):
        prefix = f"{idx:>{index_width}}."
        ext = candidate.path.suffix.lstrip(".").lower()
        if not ext:
            stats["skipped_no_extension"] += 1
            continue
        reported_extensions.add(ext)
        print(
            f"{prefix} {format_size(candidate.size_bytes):>12}  {candidate.path}  "
            f"(bucket={candidate.bucket})"
        )
        if not args.compress:
            continue
        total_original_space += candidate.size_bytes
        compressed_path: Path | None = None
        try:
            compressed_path = compress_with_xz(candidate.path)
            verify_compressed_file(compressed_path)
            compressed_size = compressed_path.stat().st_size
            candidate.path.unlink()
        except RuntimeError as exc:
            compression_failures += 1
            if compressed_path and compressed_path.exists():
                compressed_path.unlink(missing_ok=True)
            print(f"    ! Compression failed: {exc}", file=sys.stderr)
            continue
        except OSError as exc:
            compression_failures += 1
            if compressed_path and compressed_path.exists():
                compressed_path.unlink(missing_ok=True)
            print(
                f"    ! Unable to finalize compression for {candidate.path}: {exc}", file=sys.stderr
            )
            continue

        compressed_files += 1
        total_compressed_space += compressed_size
        savings = candidate.size_bytes - compressed_size
        print(
            f"    → Compressed to {compressed_path} (saved {format_size(savings)}, "
            f"verified with xz -t)"
        )

    print("\nScan summary")
    print("============")
    print(f"Local base:      {base_path}")
    print(f"Database:        {db_path}")
    print(f"Rows examined:   {stats['rows_examined']:,}")
    print(f"Candidates:      {stats['candidates_found']:,}")
    print(f"Reported (desc): {total_reported:,}")
    print(f"Total size:      {format_size(total_bytes)}")
    print(f"Missing files:   {stats['missing_local_files']:,}")
    print(f"Skipped images:  {stats['skipped_image']:,}")
    print(f"Skipped videos:  {stats['skipped_video']:,}")
    print(f"Skipped archive: {stats['skipped_compressed']:,}")
    print(f"Already .xz:     {stats['skipped_already_xz']:,}")
    print(f"Path issues:     {stats['skipped_invalid_path']:,}")
    print(f"Non-files:       {stats['skipped_non_file']:,}")
    print(f"Too small now:   {stats['skipped_now_below_threshold']:,}")
    print(f"Numeric ext:     {stats['skipped_numeric_extension']:,}")
    print(f"No extension:    {stats['skipped_no_extension']:,}")
    sorted_exts = ", ".join(sorted(reported_extensions)) if reported_extensions else "(none)"
    print(f"Extensions:      {sorted_exts}")
    if args.compress:
        print("\nCompression summary")
        print("===================")
        print(f"Files compressed: {compressed_files:,}")
        print(f"Total original:   {format_size(total_original_space)}")
        print(f"Compressed size:  {format_size(total_compressed_space)}")
        space_saved = total_original_space - total_compressed_space
        pct = (space_saved / total_original_space) * 100 if total_original_space > 0 else 0.0
        print(f"Space saved:      {format_size(space_saved)} ({pct:.2f}% reduction)")
        print(f"Failures:         {compression_failures:,}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # pragma: no cover - manual abort
        raise SystemExit("\nAborted by user.")
