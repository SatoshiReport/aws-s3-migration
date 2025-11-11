"""
Cleanup temporary artifacts package.

Scan backup trees for disposable cache/temp artifacts and optionally delete them.
"""

from cleanup_temp_artifacts import args_parser, cache, categories, config, reports, scanner
from cleanup_temp_artifacts.categories import Category, build_categories
from cleanup_temp_artifacts.scanner import (
    Candidate,
    CandidateLoadError,
    CandidateLoadResult,
    load_candidates_from_db,
)

__all__ = [
    "Category",
    "Candidate",
    "CandidateLoadError",
    "CandidateLoadResult",
    "args_parser",
    "build_categories",
    "cache",
    "categories",
    "config",
    "load_candidates_from_db",
    "reports",
    "scanner",
]
