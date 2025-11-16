"""Tests for cleanup_temp_artifacts/cli.py module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cleanup_temp_artifacts.cli import (  # pylint: disable=no-name-in-module
    _handle_deletion,
    _setup_paths,
    main,
)
from cost_toolkit.common.cli_utils import handle_state_db_reset


def test_maybe_reset_state_db_no_reset():
    """Test handle_state_db_reset when reset is not requested."""
    db_path = Path("/tmp/test.db")
    mock_reseed = MagicMock()
    result = handle_state_db_reset(
        Path("/tmp/base"),
        db_path,
        False,  # should_reset
        False,  # skip_prompt
        mock_reseed,
    )
    assert result == db_path
    mock_reseed.assert_not_called()


def test_maybe_reset_state_db_with_auto_confirm(tmp_path):
    """Test handle_state_db_reset with skip_prompt=True."""
    base_path = tmp_path / "base"
    base_path.mkdir()
    db_path = tmp_path / "test.db"

    mock_reseed = MagicMock()
    mock_reseed.return_value = (db_path, 100, 1000000)

    result = handle_state_db_reset(
        base_path,
        db_path,
        True,  # should_reset
        True,  # skip_prompt
        mock_reseed,
    )

    assert result == db_path
    mock_reseed.assert_called_once_with(base_path, db_path)


def test_maybe_reset_state_db_user_confirms(tmp_path):
    """Test handle_state_db_reset when user confirms."""
    base_path = tmp_path / "base"
    base_path.mkdir()
    db_path = tmp_path / "test.db"

    mock_reseed = MagicMock()
    mock_reseed.return_value = (db_path, 100, 1000000)

    with patch("builtins.input", return_value="y"):
        result = handle_state_db_reset(
            base_path,
            db_path,
            True,  # should_reset
            False,  # skip_prompt
            mock_reseed,
        )

        assert result == db_path
        mock_reseed.assert_called_once_with(base_path, db_path)


def test_maybe_reset_state_db_user_declines(tmp_path, capsys):
    """Test handle_state_db_reset when user declines."""
    db_path = tmp_path / "test.db"

    mock_reseed = MagicMock()

    with patch("builtins.input", return_value="n"):
        result = handle_state_db_reset(
            tmp_path / "base",
            db_path,
            True,  # should_reset
            False,  # skip_prompt
            mock_reseed,
        )

        assert result == db_path
        mock_reseed.assert_not_called()
        captured = capsys.readouterr()
        assert "cancelled" in captured.out


def test_setup_paths_base_not_exists(tmp_path):
    """Test _setup_paths when base path doesn't exist."""
    args = MagicMock()
    args.base_path = str(tmp_path / "nonexistent")
    args.reset_state_db = False
    args.yes = False

    result = _setup_paths(args)
    assert result == 1


def test_setup_paths_db_not_exists(tmp_path):
    """Test _setup_paths when database doesn't exist."""
    base_path = tmp_path / "base"
    base_path.mkdir()

    args = MagicMock()
    args.base_path = str(base_path)
    args.db_path = str(tmp_path / "nonexistent.db")
    args.reset_state_db = False
    args.yes = False

    result = _setup_paths(args)
    assert result == 1


def test_setup_paths_success(tmp_path):
    """Test _setup_paths with valid paths."""
    base_path = tmp_path / "base"
    base_path.mkdir()
    db_path = tmp_path / "test.db"
    db_path.touch()

    args = MagicMock()
    args.base_path = str(base_path)
    args.db_path = str(db_path)
    args.reset_state_db = False
    args.yes = False

    result = _setup_paths(args)
    assert isinstance(result, tuple)
    assert len(result) == 3


def test_handle_deletion_dry_run(tmp_path):
    """Test _handle_deletion in dry run mode."""
    args = MagicMock()
    args.delete = False

    result = _handle_deletion(args, [], tmp_path)
    assert result == 0


def test_handle_deletion_user_aborts(tmp_path):
    """Test _handle_deletion when user aborts."""
    args = MagicMock()
    args.delete = True
    args.yes = False

    with patch("builtins.input", return_value="n"):
        result = _handle_deletion(args, ["item1"], tmp_path)
        assert result == 0


def test_handle_deletion_with_yes_flag(tmp_path):
    """Test _handle_deletion with --yes flag."""
    args = MagicMock()
    args.delete = True
    args.yes = True

    with patch("cleanup_temp_artifacts.cli.delete_paths") as mock_delete:
        mock_delete.return_value = []

        result = _handle_deletion(args, ["item1"], tmp_path)
        assert result == 0
        mock_delete.assert_called_once()


def test_handle_deletion_with_errors(tmp_path):
    """Test _handle_deletion when deletion has errors."""
    args = MagicMock()
    args.delete = True
    args.yes = True

    with patch("cleanup_temp_artifacts.cli.delete_paths") as mock_delete:
        mock_delete.return_value = ["error1", "error2"]

        result = _handle_deletion(args, ["item1"], tmp_path)
        assert result == 2


def test_main_with_invalid_base_path(tmp_path):
    """Test main with invalid base path."""
    with patch("cleanup_temp_artifacts.cli.parse_args") as mock_parse:
        args = MagicMock()
        args.base_path = str(tmp_path / "nonexistent")
        args.verbose = False
        args.reset_state_db = False
        args.yes = False
        mock_parse.return_value = args

        result = main([])
        assert result == 1


def test_main_dry_run_no_candidates(tmp_path):
    """Test main in dry run mode with no candidates."""
    base_path = tmp_path / "base"
    base_path.mkdir()
    db_path = tmp_path / "test.db"
    db_path.touch()

    with patch("cleanup_temp_artifacts.cli.parse_args") as mock_parse:
        with patch("cleanup_temp_artifacts.cli.load_candidates_from_db") as mock_load:
            args = MagicMock()
            args.base_path = str(base_path)
            args.db_path = str(db_path)
            args.verbose = False
            args.reset_state_db = False
            args.yes = False
            args.delete = False
            args.categories = []
            args.older_than = None
            args.min_size_bytes = 0
            args.cache_enabled = False
            args.cache_dir = None
            args.refresh_cache = False
            args.cache_ttl = 0
            args.limit = 0
            args.sort = "size"
            args.report_json = None
            args.report_csv = None

            mock_parse.return_value = args

            load_result = MagicMock()
            load_result.candidates = []
            load_result.total_files = 0
            load_result.max_rowid = 0
            load_result.cache_path = None
            load_result.cache_used = False
            mock_load.return_value = load_result

            result = main([])
            assert result == 0
