"""
Cleanup temporary artifacts package.

Scan backup trees for disposable cache/temp artifacts and optionally delete them.
"""

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
    "build_categories",
    "load_candidates_from_db",
]
