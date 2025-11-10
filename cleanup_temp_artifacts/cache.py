"""
Cache management functions for cleanup_temp_artifacts.

Handles loading and writing cached scan results to avoid rescanning large databases.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cleanup_temp_artifacts.categories import Category
    from cleanup_temp_artifacts.scanner import Candidate

CACHE_VERSION = 2


def _default_cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")).expanduser()
    return base / "cleanup_temp_artifacts"


def build_scan_params(
    categories: list[Category],
    older_than: int | None,
    min_size_bytes: int | None,
) -> dict[str, object]:
    """Build scan parameters dictionary from filter criteria."""
    return {
        "categories": [cat.name for cat in categories],
        "older_than": older_than,
        "min_size_bytes": min_size_bytes,
    }


def build_cache_key(base_path: Path, db_path: Path, scan_params: dict[str, object]) -> str:
    """Generate SHA256 cache key from base path, db path, and scan parameters."""
    payload = {
        "base_path": str(base_path),
        "db_path": str(db_path),
        "scan_params": scan_params,
    }
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_cache(
    cache_path: Path,
    scan_params: dict[str, object],
    category_map: dict[str, Category],
) -> tuple[list[Candidate], dict] | None:
    """Load cached scan results and validate against current scan parameters."""
    from cleanup_temp_artifacts.scanner import Candidate

    try:
        payload = json.loads(cache_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Failed to read cache %s: %s", cache_path, exc)
        return None
    if payload.get("version") != CACHE_VERSION:
        return None
    if payload.get("scan_params") != scan_params:
        return None
    metadata = {
        "generated_at": payload.get("generated_at"),
        "rowcount": payload.get("rowcount"),
        "max_rowid": payload.get("max_rowid"),
        "db_mtime_ns": payload.get("db_mtime_ns"),
    }
    items = payload.get("candidates", [])
    candidates: list[Candidate] = []
    for item in items:
        cat_name = item.get("category")
        if cat_name not in category_map:
            return None
        candidates.append(
            Candidate(
                path=Path(item["path"]),
                category=category_map[cat_name],
                size_bytes=item.get("size_bytes"),
                mtime=item.get("mtime", 0),
            )
        )
    return candidates, metadata


def write_cache(  # noqa: PLR0913 - function arguments reflect cache metadata requirements
    cache_path: Path,
    candidates: list[Candidate],
    *,
    scan_params: dict[str, object],
    base_path: Path,
    db_path: Path,
    rowcount: int,
    max_rowid: int,
    db_mtime_ns: int,
) -> None:
    """Write scan results and metadata to cache file."""
    payload = {
        "version": CACHE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_path": str(base_path),
        "db_path": str(db_path),
        "rowcount": rowcount,
        "max_rowid": max_rowid,
        "db_mtime_ns": db_mtime_ns,
        "scan_params": scan_params,
        "candidates": [
            {
                "path": str(c.path),
                "category": c.category.name,
                "size_bytes": c.size_bytes,
                "mtime": c.mtime,
            }
            for c in candidates
        ],
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2))


def cache_is_valid(  # noqa: PLR0911 - explicit guard clauses improve readability
    metadata: dict,
    *,
    ttl_seconds: int,
    rowcount: int,
    max_rowid: int,
    db_mtime_ns: int,
) -> bool:
    """Check if cached metadata is still valid based on TTL and database state."""
    if metadata.get("rowcount") != rowcount:
        return False
    if metadata.get("max_rowid") != max_rowid:
        return False
    if metadata.get("db_mtime_ns") != db_mtime_ns:
        return False
    generated_at = metadata.get("generated_at")
    if ttl_seconds > 0:
        if not generated_at:
            return False
        try:
            generated_dt = datetime.fromisoformat(generated_at)
        except ValueError:
            return False
        age = (datetime.now(timezone.utc) - generated_dt).total_seconds()
        if age > ttl_seconds:
            return False
    return True
