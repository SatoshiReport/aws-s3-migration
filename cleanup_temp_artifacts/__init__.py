"""
Cleanup temporary artifacts package.

Scan backup trees for disposable cache/temp artifacts and optionally delete them.
"""

from . import args_parser, cache, categories, config, core_scanner, db_loader, reports, scanner
from .categories import Category, build_categories
from .scanner import (
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
    "core_scanner",
    "db_loader",
    "load_candidates_from_db",
    "reports",
    "scanner",
]
