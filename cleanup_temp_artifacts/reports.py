"""
Report generation and output functions for cleanup_temp_artifacts.

Handles JSON and CSV report generation, candidate summarization, and display.
"""

from __future__ import annotations

import csv
import json
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cleanup_temp_artifacts.scanner import Candidate

BYTES_PER_KIB = 1024
BYTES_PER_MIB = BYTES_PER_KIB**2
BYTES_PER_GIB = BYTES_PER_KIB**3
BYTES_PER_TIB = BYTES_PER_KIB**4


def parse_size(text: str) -> int:
    """Parse human-readable size strings (e.g. 10G, 512M) into bytes."""
    text = text.strip().upper()
    multiplier = 1
    if text.endswith("K"):
        multiplier = BYTES_PER_KIB
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = BYTES_PER_MIB
        text = text[:-1]
    elif text.endswith("G"):
        multiplier = BYTES_PER_GIB
        text = text[:-1]
    elif text.endswith("T"):
        multiplier = BYTES_PER_TIB
        text = text[:-1]
    return int(float(text) * multiplier)


def format_size(num_bytes: int | None) -> str:
    """Convert byte count to human-readable format (B, KB, MB, GB, etc)."""
    if num_bytes is None:
        return "n/a"
    suffixes = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(num_bytes)
    for suffix in suffixes:
        if value < BYTES_PER_KIB or suffix == suffixes[-1]:
            return f"{value:.1f}{suffix}"
        value /= BYTES_PER_KIB
    return f"{value:.1f}PB"


def summarise(candidates: list[Candidate]) -> list[tuple[str, int, int]]:
    """Return per-category summary of (name, count, total_size)."""
    summary: dict[str, tuple[int, int]] = {}
    for candidate in candidates:
        count, total_size = summary.get(candidate.category.name, (0, 0))
        summary[candidate.category.name] = (count + 1, total_size + (candidate.size_bytes or 0))
    return sorted((name, cnt, size) for name, (cnt, size) in summary.items())


def write_reports(
    candidates: list[Candidate],
    *,
    json_path: Path | None,
    csv_path: Path | None,
) -> None:
    """Write candidate list to JSON and/or CSV report files."""
    rows = [
        {
            "path": str(c.path),
            "category": c.category.name,
            "size_bytes": c.size_bytes,
            "size_human": format_size(c.size_bytes),
            "mtime": c.iso_mtime,
        }
        for c in candidates
    ]
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(rows, indent=2))
    if csv_path:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["path", "category", "size_bytes", "size_human", "mtime"]
            )
            writer.writeheader()
            writer.writerows(rows)


def order_candidates(
    candidates: list[Candidate],
    *,
    order: str,
) -> list[Candidate]:
    """Sort candidates by size or path based on order parameter."""
    if order == "size":
        return sorted(candidates, key=lambda c: c.size_bytes or 0, reverse=True)
    return sorted(candidates, key=lambda c: str(c.path))


def delete_paths(candidates: list[Candidate], *, root: Path) -> list[tuple[Candidate, Exception]]:
    """Delete files and directories, returning list of (candidate, error) for failures."""
    errors: list[tuple[Candidate, Exception]] = []
    for candidate in candidates:
        resolved = candidate.path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            errors.append((candidate, ValueError(f"{resolved} escapes root {root}")))
            continue
        try:
            if resolved.is_dir():
                shutil.rmtree(resolved)
            else:
                resolved.unlink()
        except (OSError, shutil.Error) as exc:
            logging.exception("Failed to delete %s", resolved)
            errors.append((candidate, exc))
        else:
            logging.info("Deleted %s", resolved)
    return errors


def print_candidates_report(
    candidates: list[Candidate],
    acted_upon: list[Candidate],
    base_path: Path,
) -> None:
    """Print candidate list and summary."""
    print(
        f"Identified {len(candidates)} candidate(s) (showing {len(acted_upon)}) under {base_path}:"
    )
    for candidate in acted_upon:
        size_str = format_size(candidate.size_bytes)
        print(
            f"- [{candidate.category.name}] {candidate.path} "
            f"(mtime {candidate.iso_mtime}, size {size_str})"
        )

    summary = summarise(candidates)
    print("\nPer-category totals:")
    for name, count, size in summary:
        print(f"  {name:20} count={count:6d} size={format_size(size)}")
