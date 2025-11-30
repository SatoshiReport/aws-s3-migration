"""Smoke tests for cost_toolkit to ensure packages remain importable."""

from __future__ import annotations

from pathlib import Path

# Import the cost_toolkit script packages to mark them as used
import cost_toolkit.scripts.audit
import cost_toolkit.scripts.billing
import cost_toolkit.scripts.cleanup
import cost_toolkit.scripts.management
import cost_toolkit.scripts.migration
import cost_toolkit.scripts.optimization
import cost_toolkit.scripts.rds
import cost_toolkit.scripts.setup


def test_cost_toolkit_packages_importable():
    """Verify cost_toolkit script packages can be imported."""
    assert cost_toolkit.scripts.audit is not None
    assert cost_toolkit.scripts.billing is not None
    assert cost_toolkit.scripts.cleanup is not None
    assert cost_toolkit.scripts.management is not None
    assert cost_toolkit.scripts.migration is not None
    assert cost_toolkit.scripts.optimization is not None
    assert cost_toolkit.scripts.rds is not None
    assert cost_toolkit.scripts.setup is not None


def test_all_script_subdirs_have_init_files():
    """Verify all cost_toolkit script subdirectories have __init__.py files."""
    repo_root = Path(__file__).parent.parent
    cost_toolkit_scripts = repo_root / "cost_toolkit" / "scripts"

    for category_dir in cost_toolkit_scripts.iterdir():
        if category_dir.is_dir() and not category_dir.name.startswith("__"):
            init_file = category_dir / "__init__.py"
            assert init_file.exists(), f"{category_dir.name} should have an __init__.py file"


def test_cli_scripts_have_main_guard():
    """Verify CLI scripts use if __name__ == '__main__' pattern."""
    repo_root = Path(__file__).parent.parent
    cost_toolkit_scripts = repo_root / "cost_toolkit" / "scripts"

    excluded = {"__init__.py", "public_ip_common.py"}
    script_files = []
    for category_dir in cost_toolkit_scripts.iterdir():
        if category_dir.is_dir() and not category_dir.name.startswith("__"):
            script_files.extend([f for f in category_dir.glob("*.py") if f.name not in excluded])

    assert len(script_files) > 0, "Should find at least some CLI scripts"

    for script_file in script_files:
        content = script_file.read_text(encoding="utf-8")
        assert (
            'if __name__ == "__main__"' in content
        ), f"{script_file.name} should use 'if __name__ == \"__main__\"' guard"
