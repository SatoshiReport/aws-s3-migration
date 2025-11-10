"""Tests for migrate_v2_smoke_shared helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

import migrate_v2_smoke_shared as shared


class _FakeS3:
    def __init__(self):
        self.objects = []

    def put_object(self, **kwargs):
        """Store object metadata."""
        self.objects.append(kwargs)

    def __repr__(self):
        return f"_FakeS3(objects={len(self.objects)})"


def test_materialize_tree_and_manifest(tmp_path):
    """Test materialize_sample_tree creates files and returns metrics."""
    file_count, dir_count, total_bytes = shared.materialize_sample_tree(tmp_path)
    assert file_count > 0
    assert dir_count > 0
    assert total_bytes > 0
    manifest = shared.manifest_directory(tmp_path)
    assert len(manifest) == file_count


def test_create_sample_objects_in_s3_matches_structure(tmp_path):
    """Test create_sample_objects_in_s3 creates objects matching structure."""
    fake_s3 = _FakeS3()
    manifest, files_created, dirs_created, total_bytes = shared.create_sample_objects_in_s3(
        fake_s3, "test-bucket"
    )
    assert fake_s3.objects  # ensures calls were made
    assert len(manifest) == files_created
    assert dirs_created == len({Path(obj["Key"]).parent for obj in fake_s3.objects})
    assert total_bytes > 0


def test_ensure_matching_manifests_detects_mismatch():
    """Test ensure_matching_manifests detects mismatches."""
    base_manifest = {"foo.txt": "abc"}
    shared.ensure_matching_manifests(base_manifest, dict(base_manifest))
    with pytest.raises(shared.BackupVerificationError):
        shared.ensure_matching_manifests(base_manifest, {"foo.txt": "def"})
