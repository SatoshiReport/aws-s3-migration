"""Tests for cleanup_temp_artifacts/categories.py module."""

from __future__ import annotations

from pathlib import Path

from cleanup_temp_artifacts.categories import (  # pylint: disable=no-name-in-module
    Category,
    _match_generic_dot_cache,
    _match_go_module_cache,
    _match_maven_cache,
    _match_npm_cache,
    _match_python_bytecode,
    _match_python_test_cache,
    _match_python_tox_cache,
    _match_vscode_remote,
    build_categories,
)
from tests.assertions import assert_equal


def test_category_dataclass():
    """Test Category dataclass creation."""

    def dummy_matcher(path: Path, is_dir: bool) -> bool:  # pylint: disable=unused-argument
        return True

    category = Category(
        name="test-category",
        description="Test description",
        matcher=dummy_matcher,
        prune=True,
    )

    assert_equal(category.name, "test-category")
    assert_equal(category.description, "Test description")
    assert category.matcher is dummy_matcher
    assert category.prune is True


def test_match_python_bytecode():
    """Test _match_python_bytecode matcher."""
    assert _match_python_bytecode(Path("/tmp/__pycache__"), is_dir=True) is True
    assert _match_python_bytecode(Path("/tmp/dir/__pycache__"), is_dir=True) is True
    assert _match_python_bytecode(Path("/tmp/__pycache__"), is_dir=False) is False
    assert _match_python_bytecode(Path("/tmp/other"), is_dir=True) is False


def test_match_python_test_cache():
    """Test _match_python_test_cache matcher."""
    assert _match_python_test_cache(Path("/tmp/.pytest_cache"), is_dir=True) is True
    assert _match_python_test_cache(Path("/tmp/.mypy_cache"), is_dir=True) is True
    assert _match_python_test_cache(Path("/tmp/.hypothesis"), is_dir=True) is True
    assert _match_python_test_cache(Path("/tmp/.pytest_cache"), is_dir=False) is False
    assert _match_python_test_cache(Path("/tmp/other"), is_dir=True) is False


def test_match_python_tox_cache():
    """Test _match_python_tox_cache matcher."""
    assert _match_python_tox_cache(Path("/tmp/.tox"), is_dir=True) is True
    assert _match_python_tox_cache(Path("/tmp/.nox"), is_dir=True) is True
    assert _match_python_tox_cache(Path("/tmp/.ruff_cache"), is_dir=True) is True
    assert _match_python_tox_cache(Path("/tmp/.tox"), is_dir=False) is False
    assert _match_python_tox_cache(Path("/tmp/other"), is_dir=True) is False


def test_match_generic_dot_cache():
    """Test _match_generic_dot_cache matcher."""
    assert _match_generic_dot_cache(Path("/tmp/.cache"), is_dir=True) is True
    assert _match_generic_dot_cache(Path("/tmp/dir/.cache"), is_dir=True) is True
    assert _match_generic_dot_cache(Path("/tmp/.cache"), is_dir=False) is False
    assert _match_generic_dot_cache(Path("/tmp/cache"), is_dir=True) is False


def test_match_vscode_remote():
    """Test _match_vscode_remote matcher."""
    assert _match_vscode_remote(Path("/home/user/.vscode-server/extensions/node_modules"), is_dir=True) is True
    assert _match_vscode_remote(Path("/home/user/.vscode-server/data/extensions"), is_dir=True) is True
    assert _match_vscode_remote(Path("/home/user/.vscode-server/bin/server"), is_dir=True) is True
    assert _match_vscode_remote(Path("/home/user/.vscode-server/other"), is_dir=True) is False
    assert _match_vscode_remote(Path("/home/user/.vscode-server/node_modules"), is_dir=False) is False


def test_match_go_module_cache():
    """Test _match_go_module_cache matcher."""
    assert _match_go_module_cache(Path("/home/user/go/pkg/mod/cache"), is_dir=True) is True
    assert _match_go_module_cache(Path("/home/user/go/pkg/cache"), is_dir=True) is False
    assert _match_go_module_cache(Path("/home/user/cache"), is_dir=True) is False
    assert _match_go_module_cache(Path("/home/user/go/pkg/mod/cache"), is_dir=False) is False


def test_match_maven_cache():
    """Test _match_maven_cache matcher."""
    assert _match_maven_cache(Path("/home/user/.m2/repository/.cache"), is_dir=True) is True
    assert _match_maven_cache(Path("/home/user/.m2/repository/.cache-test"), is_dir=True) is True
    assert _match_maven_cache(Path("/home/user/.m2/.cache"), is_dir=True) is False
    assert _match_maven_cache(Path("/home/user/.cache"), is_dir=True) is False
    assert _match_maven_cache(Path("/home/user/.m2/repository/.cache"), is_dir=False) is False


def test_match_npm_cache():
    """Test _match_npm_cache matcher."""
    assert _match_npm_cache(Path("/home/user/.npm/_cacache"), is_dir=True) is True
    assert _match_npm_cache(Path("/home/user/.yarn/cache"), is_dir=True) is True
    assert _match_npm_cache(Path("/home/user/.npm/other"), is_dir=True) is False
    assert _match_npm_cache(Path("/home/user/_cacache"), is_dir=True) is False
    assert _match_npm_cache(Path("/home/user/.npm/_cacache"), is_dir=False) is False


def test_build_categories():
    """Test build_categories returns all categories."""
    categories = build_categories()

    assert isinstance(categories, dict)

    # Check all expected categories are present
    expected_categories = [
        "python-bytecode",
        "python-test-cache",
        "python-tox-cache",
        "generic-dot-cache",
        "vscode-remote",
        "go-module-cache",
        "maven-cache",
        "npm-cache",
    ]
    for cat_name in expected_categories:
        assert cat_name in categories

    # Verify all are Category instances with correct attributes
    for name, category in categories.items():
        assert isinstance(category, Category)
        assert_equal(category.name, name)
        assert isinstance(category.description, str)
        assert callable(category.matcher)
        assert isinstance(category.prune, bool)
