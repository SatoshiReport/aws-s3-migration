"""Additional tests for migration_sync.py edge cases."""

from __future__ import annotations

from unittest import mock

from migration_sync import BucketSyncer


def test_multiple_sync_calls_share_base_dir(tmp_path):
    """BucketSyncer can sync multiple buckets into base path."""
    fake_s3 = mock.Mock()
    fake_s3.get_paginator.return_value.paginate.return_value = [{"Contents": []}]
    syncer = BucketSyncer(fake_s3, mock.Mock(), tmp_path)

    syncer.sync_bucket("bucket-a")
    syncer.sync_bucket("bucket-b")

    assert (tmp_path / "bucket-a").exists()
    assert (tmp_path / "bucket-b").exists()
