"""
Database scanning and candidate processing for cleanup_temp_artifacts.

This module provides backward compatibility by re-exporting from core_scanner and db_loader.
"""

from .core_scanner import (
    Candidate,
    CandidateLoadError,
    CandidateLoadResult,
    ProgressTracker,
    derive_local_path,
    iter_relevant_dirs,
    match_category,
    scan_candidates_from_db,
)
from .db_loader import (
    CacheConfig,
    DatabaseInfo,
    load_candidates_from_db,
    write_cache_if_needed,
)

__all__ = [
    "CacheConfig",
    "Candidate",
    "CandidateLoadError",
    "CandidateLoadResult",
    "DatabaseInfo",
    "ProgressTracker",
    "derive_local_path",
    "iter_relevant_dirs",
    "load_candidates_from_db",
    "match_category",
    "scan_candidates_from_db",
    "write_cache_if_needed",
]
