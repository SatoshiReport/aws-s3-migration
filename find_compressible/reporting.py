"""Reporting and output formatting for compression analysis."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

from find_compressible.analysis import CandidateFile
from find_compressible.cache import format_size
from find_compressible.compression import compress_with_xz, verify_compressed_file


def _process_single_compression(
    candidate: CandidateFile,
) -> tuple[bool, int, str | None]:
    """Compress a single file and return (success, compressed_size, error)."""
    compressed_path: Path | None = None
    try:
        compressed_path = compress_with_xz(candidate.path)
        verify_compressed_file(compressed_path)
        compressed_size = compressed_path.stat().st_size
        candidate.path.unlink()
        return True, compressed_size, None  # noqa: TRY300 - simpler than else after except
    except (RuntimeError, OSError) as exc:
        if compressed_path and compressed_path.exists():
            compressed_path.unlink(missing_ok=True)
        return False, 0, str(exc)


def report_and_compress_candidates(
    reported_candidates: Sequence[CandidateFile],
    compress_enabled: bool,
    stats: Counter,
) -> tuple[int, int, int, int, set[str]]:
    """Report candidates and optionally compress them."""
    total_reported = len(reported_candidates)
    index_width = max(2, len(str(total_reported))) if total_reported else 2
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
        if not compress_enabled:
            continue

        total_original_space += candidate.size_bytes
        success, compressed_size, error = _process_single_compression(candidate)

        if not success:
            compression_failures += 1
            print(f"    ! Compression failed: {error}", file=sys.stderr)
            continue

        compressed_files += 1
        total_compressed_space += compressed_size
        savings = candidate.size_bytes - compressed_size
        compressed_path = Path(str(candidate.path) + ".xz")
        print(
            f"    → Compressed to {compressed_path} (saved {format_size(savings)}, "
            f"verified with xz -t)"
        )

    return (
        compressed_files,
        compression_failures,
        total_original_space,
        total_compressed_space,
        reported_extensions,
    )


def print_scan_summary(
    base_path: Path,
    db_path: Path,
    stats: Counter,
    *,
    total_reported: int,
    total_bytes: int,
    reported_extensions: set[str],
):
    """Print scan summary statistics."""
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


def print_compression_summary(
    compressed_files: int,
    total_original_space: int,
    total_compressed_space: int,
    compression_failures: int,
):
    """Print compression summary statistics."""
    print("\nCompression summary")
    print("===================")
    print(f"Files compressed: {compressed_files:,}")
    print(f"Total original:   {format_size(total_original_space)}")
    print(f"Compressed size:  {format_size(total_compressed_space)}")
    space_saved = total_original_space - total_compressed_space
    pct = (space_saved / total_original_space) * 100 if total_original_space > 0 else 0.0
    print(f"Space saved:      {format_size(space_saved)} ({pct:.2f}% reduction)")
    print(f"Failures:         {compression_failures:,}")
