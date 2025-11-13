"""Tests for cleanup_temp_artifacts/args_parser.py validation and parse_args."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from cleanup_temp_artifacts.args_parser import (  # pylint: disable=no-name-in-module
    _validate_and_transform_args,
    parse_args,
)
from cleanup_temp_artifacts.categories import (  # pylint: disable=no-name-in-module
    Category,
    build_categories,
)
from tests.assertions import assert_equal


def test_validate_and_transform_args_list_categories():
    """Test _validate_and_transform_args exits when --list-categories is set."""
    parser = argparse.ArgumentParser()
    categories = build_categories()

    args = argparse.Namespace(
        list_categories=True,
        base_path="/test/path",
    )

    with pytest.raises(SystemExit) as exc_info:
        _validate_and_transform_args(args, parser, categories)

    assert_equal(exc_info.value.code, 0)


def test_validate_and_transform_args_missing_base_path():
    """Test _validate_and_transform_args errors when base_path is missing."""
    parser = argparse.ArgumentParser()
    categories = build_categories()

    args = argparse.Namespace(
        list_categories=False,
        base_path=None,
    )

    with pytest.raises(SystemExit) as exc_info:
        _validate_and_transform_args(args, parser, categories)

    assert_equal(exc_info.value.code, 2)


def test_validate_and_transform_args_invalid_limit_zero():
    """Test _validate_and_transform_args errors when limit is zero."""
    parser = argparse.ArgumentParser()
    categories = build_categories()

    args = argparse.Namespace(
        list_categories=False,
        base_path="/test/path",
        limit=0,
    )

    with pytest.raises(SystemExit) as exc_info:
        _validate_and_transform_args(args, parser, categories)

    assert_equal(exc_info.value.code, 2)


def test_validate_and_transform_args_invalid_limit_negative():
    """Test _validate_and_transform_args errors when limit is negative."""
    parser = argparse.ArgumentParser()
    categories = build_categories()

    args = argparse.Namespace(
        list_categories=False,
        base_path="/test/path",
        limit=-5,
    )

    with pytest.raises(SystemExit) as exc_info:
        _validate_and_transform_args(args, parser, categories)

    assert_equal(exc_info.value.code, 2)


def test_validate_and_transform_args_success_no_min_size():
    """Test _validate_and_transform_args successful transformation without min_size."""
    parser = argparse.ArgumentParser()
    categories = build_categories()
    category_names = list(categories.keys())[:2]

    args = argparse.Namespace(
        list_categories=False,
        base_path="/test/path",
        limit=10,
        min_size=None,
        categories=category_names,
        cache_dir=None,
        no_cache=False,
    )

    _validate_and_transform_args(args, parser, categories)

    assert args.min_size_bytes is None  # pylint: disable=no-member
    assert_equal(len(args.categories), 2)
    assert all(isinstance(cat, Category) for cat in args.categories)
    assert args.cache_dir is not None
    assert args.cache_enabled is True  # pylint: disable=no-member


def test_validate_and_transform_args_success_with_min_size():
    """Test _validate_and_transform_args successful transformation with min_size."""
    parser = argparse.ArgumentParser()
    categories = build_categories()
    category_names = list(categories.keys())

    args = argparse.Namespace(
        list_categories=False,
        base_path="/test/path",
        limit=None,
        min_size="500M",
        categories=category_names,
        cache_dir=Path("/custom/cache"),
        no_cache=False,
    )

    _validate_and_transform_args(args, parser, categories)

    assert args.min_size_bytes == 524288000  # pylint: disable=no-member
    assert_equal(len(args.categories), len(categories))
    assert_equal(args.cache_dir, Path("/custom/cache"))
    assert args.cache_enabled is True  # pylint: disable=no-member


def test_validate_and_transform_args_cache_disabled():
    """Test _validate_and_transform_args with cache disabled."""
    parser = argparse.ArgumentParser()
    categories = build_categories()

    args = argparse.Namespace(
        list_categories=False,
        base_path="/test/path",
        limit=None,
        min_size=None,
        categories=list(categories.keys()),
        cache_dir=None,
        no_cache=True,
    )

    _validate_and_transform_args(args, parser, categories)

    assert args.cache_enabled is False  # pylint: disable=no-member


def test_validate_and_transform_args_cache_dir_expansion():
    """Test _validate_and_transform_args expands cache_dir with tilde."""
    parser = argparse.ArgumentParser()
    categories = build_categories()

    args = argparse.Namespace(
        list_categories=False,
        base_path="/test/path",
        limit=None,
        min_size=None,
        categories=list(categories.keys()),
        cache_dir=Path("~/custom/cache"),
        no_cache=False,
    )

    _validate_and_transform_args(args, parser, categories)

    assert not str(args.cache_dir).startswith("~")


def test_parse_args_defaults():
    """Test parse_args with minimal arguments (defaults)."""
    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        args = parse_args([])

    assert_equal(args.base_path, "/default/path")
    assert args.categories is not None
    assert_equal(args.sort, "path")
    assert args.delete is False
    assert args.cache_enabled is True


def test_parse_args_with_custom_values():
    """Test parse_args with custom command-line values."""
    categories = build_categories()
    category_names = list(categories.keys())[:3]

    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        args = parse_args(
            [
                "--base-path",
                "/custom/base",
                "--db-path",
                "/custom/db.sqlite",
                "--categories",
                *category_names,
                "--older-than",
                "14",
                "--min-size",
                "1G",
                "--limit",
                "100",
                "--sort",
                "size",
                "--delete",
                "--report-json",
                "/tmp/report.json",
                "--cache-ttl",
                "3600",
                "--verbose",
            ]
        )

    assert_equal(args.base_path, "/custom/base")
    assert_equal(args.db_path, "/custom/db.sqlite")
    assert_equal(len(args.categories), 3)
    assert_equal(args.older_than, 14)
    assert_equal(args.min_size_bytes, 1073741824)
    assert_equal(args.limit, 100)
    assert_equal(args.sort, "size")
    assert args.delete is True
    assert_equal(args.report_json, Path("/tmp/report.json"))
    assert_equal(args.cache_ttl, 3600)
    assert args.verbose is True


def test_parse_args_list_categories_exits():
    """Test parse_args exits with --list-categories flag."""
    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--list-categories"])

    assert_equal(exc_info.value.code, 0)


def test_parse_args_missing_base_path_exits():
    """Test parse_args exits when base_path is missing and no default exists."""
    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", None):
        with pytest.raises(SystemExit) as exc_info:
            parse_args([])

    assert_equal(exc_info.value.code, 2)


def test_parse_args_invalid_limit_exits():
    """Test parse_args exits when limit is invalid."""
    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--limit", "0"])

    assert_equal(exc_info.value.code, 2)


def test_parse_args_cache_disabled():
    """Test parse_args with cache disabled via --no-cache."""
    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        args = parse_args(["--no-cache"])

    assert args.cache_enabled is False


def test_parse_args_cache_refresh():
    """Test parse_args with cache refresh enabled."""
    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        args = parse_args(["--refresh-cache"])

    assert args.refresh_cache is True


def test_parse_args_all_output_formats():
    """Test parse_args with all output format options enabled."""
    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        args = parse_args(
            [
                "--report-json",
                "/tmp/output.json",
                "--report-csv",
                "/tmp/output.csv",
                "--verbose",
            ]
        )

    assert_equal(args.report_json, Path("/tmp/output.json"))
    assert_equal(args.report_csv, Path("/tmp/output.csv"))
    assert args.verbose is True


def test_parse_args_sort_by_path():
    """Test parse_args with explicit sort by path."""
    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        args = parse_args(["--sort", "path"])

    assert_equal(args.sort, "path")


def test_parse_args_sort_by_size():
    """Test parse_args with sort by size."""
    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        args = parse_args(["--sort", "size"])

    assert_equal(args.sort, "size")


def test_parse_args_multiple_categories():
    """Test parse_args with multiple specific categories."""
    selected = ["python-bytecode", "generic-dot-cache"]

    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        args = parse_args(["--categories"] + selected)

    assert_equal(len(args.categories), 2)
    assert all(cat.name in selected for cat in args.categories)


def test_parse_args_older_than_filter():
    """Test parse_args with --older-than filter."""
    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        args = parse_args(["--older-than", "60"])

    assert_equal(args.older_than, 60)


def test_parse_args_min_size_various_units():
    """Test parse_args with various min_size units."""
    test_cases = [
        ("1K", 1024),
        ("512M", 536870912),
        ("2G", 2147483648),
    ]

    for size_str, expected_bytes in test_cases:
        with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
            result = parse_args(["--min-size", size_str])

        assert_equal(
            result.min_size_bytes,  # pylint: disable=no-member
            expected_bytes,
            message=f"Failed for size {size_str}",
        )


def test_parse_args_integration_dry_run():
    """Test parse_args for typical dry-run scenario."""
    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        args = parse_args(
            [
                "--base-path",
                "/my/backup",
                "--categories",
                "python-bytecode",
                "python-test-cache",
                "--older-than",
                "7",
                "--min-size",
                "100M",
                "--sort",
                "size",
                "--limit",
                "20",
            ]
        )

    assert_equal(args.base_path, "/my/backup")
    assert_equal(len(args.categories), 2)
    assert_equal(args.older_than, 7)
    assert_equal(args.min_size_bytes, 104857600)
    assert_equal(args.sort, "size")
    assert_equal(args.limit, 20)
    assert args.delete is False


def test_parse_args_integration_delete_run():
    """Test parse_args for typical delete scenario."""
    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/default/path")):
        args = parse_args(
            [
                "--base-path",
                "/my/backup",
                "--delete",
                "--older-than",
                "30",
                "--report-json",
                "/tmp/deleted.json",
            ]
        )

    assert_equal(args.base_path, "/my/backup")
    assert args.delete is True
    assert_equal(args.older_than, 30)
    assert_equal(args.report_json, Path("/tmp/deleted.json"))
