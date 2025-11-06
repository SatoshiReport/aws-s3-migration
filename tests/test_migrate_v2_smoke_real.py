"""Tests for migrate_v2_smoke_real helpers."""

from __future__ import annotations

import builtins
from pathlib import Path
from types import SimpleNamespace

import pytest

import migrate_v2_smoke_real as real
from migrate_v2_smoke_shared import SmokeTestDeps, materialize_sample_tree


class _FakeWaiter:
    def __init__(self):
        self.calls = []

    def wait(self, **kwargs):
        self.calls.append(kwargs)


class _FakePaginator:
    def paginate(self, **kwargs):
        yield {"Versions": [], "DeleteMarkers": []}


class _FakeS3:
    def __init__(self):
        self.meta = SimpleNamespace(region_name="us-west-2")
        self.created = []
        self.waiters = []
        self.put_calls = []
        self.bucket_name = "alpha"

    def create_bucket(self, **kwargs):
        self.created.append(kwargs)

    def get_waiter(self, name):
        assert name == "bucket_exists"
        waiter = _FakeWaiter()
        self.waiters.append(waiter)
        return waiter

    def list_buckets(self):
        return {"Buckets": [{"Name": "alpha"}, {"Name": self.bucket_name}]}

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)

    def get_paginator(self, name):
        assert name in {"list_object_versions"}
        return _FakePaginator()

    def delete_objects(self, **_kwargs):
        return {}

    def delete_bucket(self, **_kwargs):
        return {}


class _FakeDriveChecker:
    def __init__(self, path):
        self.path = path
        self.checked = False

    def check_available(self):
        self.checked = True


class _FakeMigrator:
    def __init__(self):
        self.ran = False

    def run(self):
        self.ran = True


def _make_deps(tmp_path, fake_s3, monkeypatch):
    base_path = tmp_path / "drive"
    base_path.mkdir()
    config = SimpleNamespace(
        LOCAL_BASE_PATH=str(base_path),
        STATE_DB_PATH=str(tmp_path / "state.db"),
        EXCLUDED_BUCKETS=["keep-me"],
    )
    migrator = _FakeMigrator()

    class _FakeSession:
        region_name = "us-west-2"

        def client(self, service_name):
            assert service_name == "s3"
            return fake_s3

    monkeypatch.setattr(real, "Session", _FakeSession)
    deps = SmokeTestDeps(
        config=config,
        drive_checker_cls=_FakeDriveChecker,
        create_migrator=lambda: migrator,
    )
    return deps, migrator


def test_seed_real_bucket_updates_config(monkeypatch, tmp_path):
    fake_s3 = _FakeS3()
    deps, _ = _make_deps(tmp_path, fake_s3, monkeypatch)
    ctx = real._RealSmokeContext.create(deps)
    fake_s3.bucket_name = ctx.bucket_name
    original_input = builtins.input
    try:
        stats = real._seed_real_bucket(ctx)
    finally:
        builtins.input = original_input
    assert stats.files_created > 0
    assert deps.config.STATE_DB_PATH == str(ctx.state_db_path)
    assert ctx.bucket_name not in deps.config.EXCLUDED_BUCKETS
    assert fake_s3.put_calls  # ensure uploads occurred


def test_run_real_workflow_removes_local_data(monkeypatch, tmp_path):
    fake_s3 = _FakeS3()
    deps, migrator = _make_deps(tmp_path, fake_s3, monkeypatch)
    ctx = real._RealSmokeContext.create(deps)
    fake_s3.bucket_name = ctx.bucket_name
    original_input = builtins.input
    try:
        stats = real._seed_real_bucket(ctx)
    finally:
        builtins.input = original_input
    ctx.local_bucket_path.mkdir(parents=True, exist_ok=True)
    materialize_sample_tree(ctx.local_bucket_path)
    real._run_real_workflow(ctx, stats)
    assert migrator.ran
    assert not ctx.local_bucket_path.exists()


def test_print_real_report_outputs_sections(capsys, monkeypatch, tmp_path):
    fake_s3 = _FakeS3()
    deps, _ = _make_deps(tmp_path, fake_s3, monkeypatch)
    ctx = real._RealSmokeContext.create(deps)
    stats = real._RealSmokeStats(
        files_created=1, dirs_created=1, total_bytes=10, manifest_expected={}
    )
    real._print_real_report(ctx, stats)
    output = capsys.readouterr().out
    assert "SMOKE TEST REPORT" in output
    assert "Files processed" in output


def test_context_restore_resets_state(tmp_path):
    temp_dir = tmp_path / "ctx"
    temp_dir.mkdir()
    original_input = builtins.input
    config = SimpleNamespace(
        STATE_DB_PATH="state.db",
        EXCLUDED_BUCKETS=["x"],
    )
    ctx = real._RealSmokeContext(
        deps=SmokeTestDeps(
            config=config,
            drive_checker_cls=_FakeDriveChecker,
            create_migrator=lambda: _FakeMigrator(),
        ),
        temp_dir=temp_dir,
        bucket_name="bucket",
        state_db_path=Path("new_state.db"),
        external_drive_root=Path(temp_dir),
        local_bucket_path=temp_dir / "bucket",
        original_state_db="state.db",
        original_exclusions=["orig"],
        original_input=original_input,
        s3=_FakeS3(),
        region="us-west-2",
        should_cleanup=True,
        bucket_created=False,
    )
    config.STATE_DB_PATH = "changed.db"
    config.EXCLUDED_BUCKETS = ["changed"]
    builtins.input = lambda _prompt=None: "modified"
    ctx.restore()
    assert config.STATE_DB_PATH == "state.db"
    assert config.EXCLUDED_BUCKETS == ["orig"]
    assert builtins.input == original_input
    assert not temp_dir.exists()
