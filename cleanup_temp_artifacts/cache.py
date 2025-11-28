"""
Cache management functions for cleanup_temp_artifacts.

Handles loading and writing cached scan results to avoid rescanning large databases.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .core_scanner import Candidate

if TYPE_CHECKING:
    from .categories import Category
    from .db_loader import DatabaseInfo

CACHE_VERSION = 2


class CacheConfigError(RuntimeError):
    """Raised when cache directory cannot be determined."""


def _default_cache_dir() -> Path:
    """Determine the default cache directory.

    Uses XDG_CACHE_HOME if set, otherwise uses ~/.cache as per XDG Base Directory spec.
    This follows the XDG spec where ~/.cache is the default when XDG_CACHE_HOME is not set.
    """
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        base = Path(xdg_cache).expanduser()
    else:
        # Per XDG spec, ~/.cache is the standard default location
        base = Path.home() / ".cache"
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


class CacheReadError(RuntimeError):
    """Raised when cache file cannot be read."""


class CacheValidationError(RuntimeError):
    """Raised when cache fails validation."""


def load_cache(
    cache_path: Path,
    scan_params: dict[str, object],
    category_map: dict[str, Category],
) -> tuple[list[Candidate], dict]:
    """Load cached scan results and validate against current scan parameters.

    Raises:
        CacheReadError: If cache file cannot be read
        CacheValidationError: If cache version or parameters don't match
    """
    try:
        payload = json.loads(cache_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CacheReadError(f"Failed to read cache {cache_path}: {exc}") from exc
    if payload.get("version") != CACHE_VERSION:
        raise CacheValidationError(
            f"Cache version mismatch: expected {CACHE_VERSION}, got {payload.get('version')}"
        )
    if payload.get("scan_params") != scan_params:
        raise CacheValidationError("Cache scan parameters don't match current parameters")
    metadata = {
        "generated_at": payload.get("generated_at"),
        "rowcount": payload.get("rowcount"),
        "max_rowid": payload.get("max_rowid"),
        "db_mtime_ns": payload.get("db_mtime_ns"),
    }
    if "candidates" not in payload:
        raise CacheValidationError("Cache missing 'candidates' key")
    items = payload["candidates"]
    candidates: list[Candidate] = []
    for item in items:
        if "category" not in item:
            raise CacheValidationError("Cache item missing 'category' key")
        cat_name = item["category"]
        if cat_name not in category_map:
            raise CacheValidationError(f"Unknown category '{cat_name}' in cached data")
        if "path" not in item:
            raise CacheValidationError("Cache item missing 'path' key")
        if "mtime" not in item:
            raise CacheValidationError("Cache item missing 'mtime' key")
        candidates.append(
            Candidate(
                path=Path(item["path"]),
                category=category_map[cat_name],
                size_bytes=item.get("size_bytes"),
                mtime=item["mtime"],
            )
        )
    return candidates, metadata


def write_cache(
    cache_path: Path,
    candidates: list[Candidate],
    *,
    scan_params: dict[str, object],
    base_path: Path,
    db_info: "DatabaseInfo",
) -> None:
    """Write scan results and metadata to cache file."""
    payload = {
        "version": CACHE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_path": str(base_path),
        "db_path": str(db_info.db_path),
        "rowcount": db_info.total_files,
        "max_rowid": db_info.max_rowid,
        "db_mtime_ns": db_info.db_stat.st_mtime_ns,
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


def cache_is_valid(
    metadata: dict,
    *,
    ttl_seconds: int,
    rowcount: int,
    max_rowid: int,
    db_mtime_ns: int,
) -> bool:
    """Check if cached metadata is still valid based on TTL and database state."""
    # Check database state consistency
    if (
        metadata.get("rowcount") != rowcount
        or metadata.get("max_rowid") != max_rowid
        or metadata.get("db_mtime_ns") != db_mtime_ns
    ):
        return False

    # Check TTL if enabled
    if ttl_seconds > 0:
        generated_at = metadata.get("generated_at")
        if not generated_at:
            raise CacheValidationError("Cache metadata missing 'generated_at' timestamp")
        try:
            generated_dt = datetime.fromisoformat(generated_at)
            age = (datetime.now(timezone.utc) - generated_dt).total_seconds()
        except ValueError as exc:
            raise CacheValidationError(
                f"Cache has malformed 'generated_at' timestamp: {generated_at}"
            ) from exc
        return age <= ttl_seconds
    return True
