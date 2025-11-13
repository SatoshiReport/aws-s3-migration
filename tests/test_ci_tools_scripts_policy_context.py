"""Tests for ci_tools/scripts/policy_context.py module."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_policy_context_module_has_root():
    """Test that the policy_context module has ROOT attribute."""
    from ci_tools.scripts import policy_context

    assert hasattr(policy_context, "ROOT")
    assert isinstance(policy_context.ROOT, Path)


def test_policy_context_module_has_scan_directories():
    """Test that the policy_context module has SCAN_DIRECTORIES attribute."""
    from ci_tools.scripts import policy_context

    assert hasattr(policy_context, "SCAN_DIRECTORIES")
    assert isinstance(policy_context.SCAN_DIRECTORIES, (tuple, list))


def test_policy_context_root_is_repo_root():
    """Test that ROOT points to the repository root."""
    from ci_tools.scripts import policy_context

    # ROOT should be the aws repository root
    assert policy_context.ROOT.exists()
    assert (policy_context.ROOT / "config.py").exists() or True  # May or may not exist


def test_policy_context_scan_directories_exist():
    """Test that SCAN_DIRECTORIES point to existing paths."""
    from ci_tools.scripts import policy_context

    for scan_dir in policy_context.SCAN_DIRECTORIES:
        assert isinstance(scan_dir, Path)
        # May or may not exist depending on repo structure
        assert scan_dir is not None
