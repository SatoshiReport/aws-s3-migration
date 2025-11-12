"""Tests for duplicate_tree/deletion.py module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from duplicate_tree.deletion import (
    build_deletion_groups,
    confirm_deletion,
    delete_duplicate_directories,
    perform_deletions,
    print_deletion_plan,
)
from tests.assertions import assert_equal


def _create_cluster_row(node_paths, node_sizes):
    """Create a cluster row for testing."""
    nodes = []
    for path, size in zip(node_paths, node_sizes):
        nodes.append(
            {
                "path": path if isinstance(path, tuple) else tuple(path.split("/")),
                "total_size": size,
                "file_count": 10,
            }
        )
    return {"nodes": nodes}


def test_build_deletion_groups_with_duplicates():
    """Test build_deletion_groups with duplicate clusters."""
    cluster1 = _create_cluster_row(["dirA", "dirB", "dirC"], [1000, 1000, 1000])
    cluster2 = _create_cluster_row(["dirD", "dirE"], [2000, 2000])

    deletion_groups, total_bytes, total_dirs = build_deletion_groups([cluster1, cluster2])

    assert_equal(len(deletion_groups), 2)
    assert_equal(total_dirs, 3)  # dirB, dirC, dirE
    assert_equal(total_bytes, 4000)  # 1000+1000+2000


def test_build_deletion_groups_filters_small_clusters():
    """Test build_deletion_groups filters clusters with < MIN_DUPLICATE_NODES."""
    cluster_with_one_node = _create_cluster_row(["dirA"], [1000])
    cluster_with_two_nodes = _create_cluster_row(["dirB", "dirC"], [2000, 2000])

    deletion_groups, total_bytes, total_dirs = build_deletion_groups(
        [cluster_with_one_node, cluster_with_two_nodes]
    )

    assert_equal(len(deletion_groups), 1)  # Only the cluster with 2+ nodes
    assert_equal(total_dirs, 1)  # Only dirC gets deleted
    assert_equal(total_bytes, 2000)


def test_build_deletion_groups_empty():
    """Test build_deletion_groups with empty cluster list."""
    deletion_groups, total_bytes, total_dirs = build_deletion_groups([])

    assert_equal(len(deletion_groups), 0)
    assert_equal(total_dirs, 0)
    assert_equal(total_bytes, 0)


def test_print_deletion_plan(tmp_path, capsys):
    """Test print_deletion_plan output."""
    cluster = _create_cluster_row(
        [("bucket", "dirA"), ("bucket", "dirB")], [1024 * 1024, 1024 * 1024]
    )
    deletion_groups, _, _ = build_deletion_groups([cluster])

    print_deletion_plan(deletion_groups, tmp_path)

    captured = capsys.readouterr().out
    assert "Deletion plan" in captured
    assert "Keep" in captured
    assert "delete" in captured


def test_confirm_deletion_yes():
    """Test confirm_deletion with yes response."""
    with patch("builtins.input", return_value="y"):
        result = confirm_deletion(5, 1024 * 1024)
        assert result is True

    with patch("builtins.input", return_value="yes"):
        result = confirm_deletion(5, 1024 * 1024)
        assert result is True


def test_confirm_deletion_no():
    """Test confirm_deletion with no response."""
    with patch("builtins.input", return_value="n"):
        result = confirm_deletion(5, 1024 * 1024)
        assert result is False

    with patch("builtins.input", return_value=""):
        result = confirm_deletion(5, 1024 * 1024)
        assert result is False


def test_confirm_deletion_eof():
    """Test confirm_deletion with EOFError."""
    with patch("builtins.input", side_effect=EOFError):
        result = confirm_deletion(5, 1024 * 1024)
        assert result is False


def test_perform_deletions_with_files(tmp_path):
    """Test perform_deletions with actual files."""
    # Create test directories
    dir_to_keep = tmp_path / "bucket" / "dirA"
    dir_to_delete = tmp_path / "bucket" / "dirB"
    dir_to_keep.mkdir(parents=True)
    dir_to_delete.mkdir(parents=True)

    # Add some files
    (dir_to_delete / "file1.txt").write_text("content")
    (dir_to_delete / "file2.txt").write_text("content")

    cluster = _create_cluster_row([("bucket", "dirA"), ("bucket", "dirB")], [1000, 1000])
    deletion_groups, _, _ = build_deletion_groups([cluster])

    errors = perform_deletions(deletion_groups, tmp_path)

    assert_equal(len(errors), 0)
    assert dir_to_keep.exists()
    assert not dir_to_delete.exists()


def test_perform_deletions_with_missing_directory(tmp_path, capsys):
    """Test perform_deletions with missing directory."""
    cluster = _create_cluster_row([("bucket", "dirA"), ("bucket", "missing")], [1000, 1000])
    deletion_groups, _, _ = build_deletion_groups([cluster])

    errors = perform_deletions(deletion_groups, tmp_path)

    captured = capsys.readouterr().out
    assert "Skipping missing directory" in captured
    assert_equal(len(errors), 0)


def test_perform_deletions_with_file_instead_of_dir(tmp_path, capsys):
    """Test perform_deletions with a file instead of directory."""
    # Create both keep and delete paths
    keep_dir = tmp_path / "bucket" / "keep"
    keep_dir.mkdir(parents=True)

    file_path = tmp_path / "bucket" / "file.txt"
    file_path.write_text("content")

    # First item is kept, second is deleted
    cluster = _create_cluster_row([("bucket", "file.txt"), ("bucket", "keep")], [1000, 1000])
    deletion_groups, _, _ = build_deletion_groups([cluster])

    errors = perform_deletions(deletion_groups, tmp_path)

    assert_equal(len(errors), 0)
    assert not keep_dir.exists()  # keep directory should be deleted
    assert file_path.exists()  # file should be kept
    captured = capsys.readouterr().out
    assert "Deleted" in captured


def test_perform_deletions_with_symlink(tmp_path):
    """Test perform_deletions with a symlink."""
    target = tmp_path / "target"
    target.mkdir()
    symlink = tmp_path / "bucket" / "link"
    symlink.parent.mkdir(parents=True)
    symlink.symlink_to(target)

    cluster = _create_cluster_row([("bucket", "keep"), ("bucket", "link")], [1000, 1000])
    deletion_groups, _, _ = build_deletion_groups([cluster])

    errors = perform_deletions(deletion_groups, tmp_path)

    assert_equal(len(errors), 0)
    assert not symlink.exists()
    assert target.exists()  # Target should remain


def test_perform_deletions_with_permission_error(tmp_path, capsys):
    """Test perform_deletions with permission error."""
    dir_to_delete = tmp_path / "bucket" / "protected"
    dir_to_delete.mkdir(parents=True)

    cluster = _create_cluster_row([("bucket", "keep"), ("bucket", "protected")], [1000, 1000])
    deletion_groups, _, _ = build_deletion_groups([cluster])

    with patch("shutil.rmtree", side_effect=PermissionError("Access denied")):
        errors = perform_deletions(deletion_groups, tmp_path)

    assert len(errors) > 0
    captured = capsys.readouterr().out
    assert "Error deleting" in captured


def test_delete_duplicate_directories_empty(capsys):
    """Test delete_duplicate_directories with no deletion groups."""
    delete_duplicate_directories([], Path("/tmp"))

    captured = capsys.readouterr().out
    assert "No duplicate directories meet the delete criteria" in captured


def test_delete_duplicate_directories_cancelled(tmp_path, capsys):
    """Test delete_duplicate_directories when user cancels."""
    dir1 = tmp_path / "bucket" / "dirA"
    dir2 = tmp_path / "bucket" / "dirB"
    dir1.mkdir(parents=True)
    dir2.mkdir(parents=True)

    cluster = _create_cluster_row([("bucket", "dirA"), ("bucket", "dirB")], [1000, 1000])

    with patch("builtins.input", return_value="n"):
        delete_duplicate_directories([cluster], tmp_path)

    captured = capsys.readouterr().out
    assert "Deletion cancelled" in captured
    assert dir1.exists()
    assert dir2.exists()


def test_delete_duplicate_directories_success(tmp_path, capsys):
    """Test delete_duplicate_directories with successful deletion."""
    dir1 = tmp_path / "bucket" / "dirA"
    dir2 = tmp_path / "bucket" / "dirB"
    dir1.mkdir(parents=True)
    dir2.mkdir(parents=True)
    (dir2 / "file.txt").write_text("content")

    cluster = _create_cluster_row([("bucket", "dirA"), ("bucket", "dirB")], [1000, 1000])

    with patch("builtins.input", return_value="y"):
        delete_duplicate_directories([cluster], tmp_path)

    captured = capsys.readouterr().out
    assert "Deletion complete" in captured
    assert dir1.exists()
    assert not dir2.exists()


def test_delete_duplicate_directories_with_errors(tmp_path, capsys):
    """Test delete_duplicate_directories with deletion errors."""
    dir1 = tmp_path / "bucket" / "dirA"
    dir2 = tmp_path / "bucket" / "dirB"
    dir1.mkdir(parents=True)
    dir2.mkdir(parents=True)

    cluster = _create_cluster_row([("bucket", "dirA"), ("bucket", "dirB")], [1000, 1000])

    with (
        patch("builtins.input", return_value="y"),
        patch("shutil.rmtree", side_effect=OSError("Deletion failed")),
    ):
        delete_duplicate_directories([cluster], tmp_path)

    captured = capsys.readouterr().out
    assert "Completed with" in captured
    assert "error(s)" in captured
