"""Tests for migration_sync.py streaming downloads."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from migration_sync import BucketSyncer, SyncInterrupted


class _FakeBody:
    def __init__(self, payload: bytes):
        self._payload = payload

    def iter_chunks(self, chunk_size=8192):
        stream = BytesIO(self._payload)
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            yield chunk


class _FakePaginator:
    def __init__(self, contents):
        self._contents = contents

    def paginate(self, **_kwargs):
        yield {"Contents": self._contents}


class _FakeS3:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    def get_paginator(self, _name):
        contents = [{"Key": key, "Size": len(data)} for key, data in self.objects.items()]
        return _FakePaginator(contents)

    def get_object(self, Bucket, Key):  # noqa: N803 - boto3 casing
        data = self.objects.get(Key)
        if data is None:
            raise RuntimeError("Missing object")
        return {"Body": _FakeBody(data)}


def test_sync_bucket_downloads_files(tmp_path):
    """BucketSyncer writes downloaded objects to disk."""
    fake_s3 = _FakeS3({"file1.txt": b"hello", "dir/file2.bin": b"data"})
    syncer = BucketSyncer(fake_s3, mock.Mock(), tmp_path)

    syncer.sync_bucket("my-bucket")

    assert (tmp_path / "my-bucket" / "file1.txt").read_bytes() == b"hello"
    assert (tmp_path / "my-bucket" / "dir" / "file2.bin").read_bytes() == b"data"


def test_sync_bucket_respects_interrupt(tmp_path):
    """Sync stops when interrupted flag is set."""
    fake_s3 = _FakeS3({"file1.txt": b"hello", "file2.txt": b"data"})
    syncer = BucketSyncer(fake_s3, mock.Mock(), tmp_path)
    syncer.interrupted = True

    # Should not raise but also not download files
    syncer.sync_bucket("bucket")
    assert not (tmp_path / "bucket" / "file1.txt").exists()
