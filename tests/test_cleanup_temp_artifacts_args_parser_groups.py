"""Tests for cleanup_temp_artifacts/args_parser.py argument group functions."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

from cleanup_temp_artifacts import args_parser  # pylint: disable=no-name-in-module
from tests.assertions import assert_equal

_add_action_arguments = args_parser._add_action_arguments  # pylint: disable=protected-access
_add_cache_arguments = args_parser._add_cache_arguments  # pylint: disable=protected-access
_add_filter_arguments = args_parser._add_filter_arguments  # pylint: disable=protected-access
_add_output_arguments = args_parser._add_output_arguments  # pylint: disable=protected-access
_add_parser_arguments = args_parser._add_parser_arguments  # pylint: disable=protected-access
_add_path_arguments = args_parser._add_path_arguments  # pylint: disable=protected-access


def test_add_path_arguments_with_default():
    """Test _add_path_arguments adds correct arguments with default path."""
    parser = argparse.ArgumentParser()

    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", Path("/test/path")):
        _add_path_arguments(parser)

    args = parser.parse_args([])

    assert_equal(args.base_path, "/test/path")
    assert args.db_path is not None


def test_add_path_arguments_without_default():
    """Test _add_path_arguments adds correct arguments without default path."""
    parser = argparse.ArgumentParser()

    with patch("cleanup_temp_artifacts.args_parser.DEFAULT_BASE_PATH", None):
        _add_path_arguments(parser)

    args = parser.parse_args([])

    assert args.base_path is None
    assert args.db_path is not None


def test_add_path_arguments_with_custom_paths():
    """Test _add_path_arguments with custom path overrides."""
    parser = argparse.ArgumentParser()
    _add_path_arguments(parser)

    args = parser.parse_args(["--base-path", "/custom/base", "--db-path", "/custom/db.sqlite"])

    assert_equal(args.base_path, "/custom/base")
    assert_equal(args.db_path, "/custom/db.sqlite")


def test_add_filter_arguments_defaults():
    """Test _add_filter_arguments sets correct defaults."""
    parser = argparse.ArgumentParser()
    categories = {"cat-a": "Category A", "cat-b": "Category B"}

    _add_filter_arguments(parser, categories)
    args = parser.parse_args([])

    assert_equal(sorted(args.categories), ["cat-a", "cat-b"])
    assert args.older_than is None
    assert args.min_size is None
    assert args.limit is None
    assert_equal(args.sort, "path")


def test_add_filter_arguments_with_values():
    """Test _add_filter_arguments with custom filter values."""
    parser = argparse.ArgumentParser()
    categories = {"cat-a": "Category A", "cat-b": "Category B", "cat-c": "Category C"}

    _add_filter_arguments(parser, categories)
    args = parser.parse_args(
        [
            "--categories",
            "cat-a",
            "cat-c",
            "--older-than",
            "30",
            "--min-size",
            "100M",
            "--limit",
            "50",
            "--sort",
            "size",
        ]
    )

    assert_equal(args.categories, ["cat-a", "cat-c"])
    assert_equal(args.older_than, 30)
    assert_equal(args.min_size, "100M")
    assert_equal(args.limit, 50)
    assert_equal(args.sort, "size")


def test_add_action_arguments():
    """Test _add_action_arguments adds delete and state db reset flags."""
    parser = argparse.ArgumentParser()

    _add_action_arguments(parser)
    args = parser.parse_args([])

    assert args.delete is False

    args_with_delete = parser.parse_args(["--delete"])
    assert args_with_delete.delete is True


def test_add_output_arguments_defaults():
    """Test _add_output_arguments sets correct defaults."""
    parser = argparse.ArgumentParser()

    _add_output_arguments(parser)
    args = parser.parse_args([])

    assert args.report_json is None
    assert args.report_csv is None
    assert args.list_categories is False
    assert args.verbose is False


def test_add_output_arguments_with_values():
    """Test _add_output_arguments with custom output settings."""
    parser = argparse.ArgumentParser()

    _add_output_arguments(parser)
    args = parser.parse_args(
        [
            "--report-json",
            "/tmp/report.json",
            "--report-csv",
            "/tmp/report.csv",
            "--list-categories",
            "--verbose",
        ]
    )

    assert_equal(args.report_json, Path("/tmp/report.json"))
    assert_equal(args.report_csv, Path("/tmp/report.csv"))
    assert args.list_categories is True
    assert args.verbose is True


def test_add_cache_arguments_defaults():
    """Test _add_cache_arguments sets correct defaults."""
    parser = argparse.ArgumentParser()

    _add_cache_arguments(parser)
    args = parser.parse_args([])

    assert args.cache_dir is None
    assert_equal(args.cache_ttl, 43200)
    assert args.refresh_cache is False
    assert args.no_cache is False


def test_add_cache_arguments_with_values():
    """Test _add_cache_arguments with custom cache settings."""
    parser = argparse.ArgumentParser()

    _add_cache_arguments(parser)
    args = parser.parse_args(
        [
            "--cache-dir",
            "/tmp/cache",
            "--cache-ttl",
            "7200",
            "--refresh-cache",
            "--no-cache",
        ]
    )

    assert_equal(args.cache_dir, Path("/tmp/cache"))
    assert_equal(args.cache_ttl, 7200)
    assert args.refresh_cache is True
    assert args.no_cache is True


def test_add_parser_arguments():
    """Test _add_parser_arguments adds all argument groups."""
    parser = argparse.ArgumentParser()
    categories = {"test-cat": "Test Category"}

    _add_parser_arguments(parser, categories)

    args = parser.parse_args([])

    assert hasattr(args, "base_path")
    assert hasattr(args, "categories")
    assert hasattr(args, "delete")
    assert hasattr(args, "report_json")
    assert hasattr(args, "cache_dir")
