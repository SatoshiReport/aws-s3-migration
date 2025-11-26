"""Simulated smoke-test flow for migrate_v2."""

# pylint: disable=duplicate-code,missing-function-docstring,too-few-public-methods,too-many-instance-attributes

from __future__ import annotations

import builtins
import hashlib
import shutil
import subprocess
import tempfile
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3

AWS_SYNC_MIN_ARGS = 4

try:
    from .migrate_v2_smoke_shared import (
        SmokeTestDeps,
        ensure_matching_manifests,
        manifest_directory,
        materialize_sample_tree,
    )
except ImportError:
    from migrate_v2_smoke_shared import (  # type: ignore[no-redef]
        SmokeTestDeps,
        ensure_matching_manifests,
        manifest_directory,
        materialize_sample_tree,
    )


def run_simulated_smoke_test(deps: SmokeTestDeps):
    """Offline smoke test used when MIGRATE_V2_SMOKE_FAKE_S3=1."""
    ctx = _SimulatedSmokeContext.create(deps)
    try:
        stats = _seed_simulated_bucket(ctx)
        _install_simulated_hooks(ctx, stats.object_entries)
        _run_simulated_workflow(ctx, stats.manifest_before)
        _cleanup_simulated_data(ctx)
        _print_simulated_report(ctx, stats)
    except Exception:  # pragma: no cover - diagnostic helper
        ctx.should_cleanup = False
        print("\nSmoke test failed!")
        print(f"Temporary files retained at: {ctx.temp_dir}")
        raise
    finally:
        ctx.restore()


class _SimulatedS3Client:
    """Minimal S3 client that serves the generated sample data."""

    def __init__(self, bucket_name: str, object_entries):
        self.bucket_name = bucket_name
        self.object_entries = object_entries

    def list_buckets(self):
        return {"Buckets": [{"Name": self.bucket_name}]}

    def get_paginator(self, operation_name: str):
        if operation_name == "list_objects_v2":
            return _SimulatedListObjectsPaginator(self.bucket_name, self.object_entries)
        if operation_name in {"list_object_versions", "list_multipart_uploads"}:
            return _EmptyPaginator()
        raise NotImplementedError(f"Unsupported paginator: {operation_name}")


class _SimulatedListObjectsPaginator:
    """Paginator that yields the simulated bucket contents."""

    def __init__(self, bucket_name: str, object_entries):
        self.bucket_name = bucket_name
        self.object_entries = object_entries

    def paginate(self, Bucket: str):  # pylint: disable=invalid-name
        if Bucket != self.bucket_name:
            return
        yield {"Contents": list(self.object_entries)}


class _EmptyPaginator:
    """Paginator that yields a single empty page."""

    def paginate(self, **_kwargs):  # pylint: disable=keyword-arg-before-vararg
        yield {}


class _Stream:
    """Simple file-like stream for fake subprocess pipes."""

    def __init__(self, lines=None):
        if lines is None:
            lines = []
        self._lines = deque(lines)
        self._buffer = "\n".join(lines)

    def readline(self):
        if self._lines:
            return self._lines.popleft() + "\n"
        return ""

    def read(self):
        return self._buffer

    def has_lines(self):
        return bool(self._lines)


class _FakeAwsSyncProcess:
    """Fake aws s3 sync process that copies from the simulated bucket."""

    def __init__(self, source_bucket_path: Path, local_bucket_path: Path, object_entries):
        self._stdout_lines = []
        for entry in object_entries:
            src = source_bucket_path / entry["Key"]
            dst = local_bucket_path / entry["Key"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            size = entry["Size"]
            if size >= 1024 * 1024:
                value = size / (1024 * 1024)
                suffix = "MiB"
            else:
                value = max(size / 1024, 0.01)
                suffix = "KiB"
            self._stdout_lines.append(f"Completed {value:.2f}{suffix}")
        self.stdout = _Stream(self._stdout_lines.copy())
        self.stderr = _Stream([])
        self.returncode = 0

    def poll(self):
        return None if self.stdout.has_lines() else 0


@dataclass
class _SimulatedSmokeContext:
    """Tracks resources allocated for the simulated smoke test."""

    deps: SmokeTestDeps
    temp_dir: Path
    bucket_name: str
    simulated_bucket_path: Path
    external_drive_root: Path
    local_bucket_path: Path
    backup_state_db: Path
    should_cleanup: bool
    original_boto_client: Any
    original_popen: Any
    original_input: Any
    original_state_db: str
    original_exclusions: list[str]

    @classmethod
    def create(cls, deps: SmokeTestDeps):
        temp_dir = Path(tempfile.mkdtemp(prefix="migrate_v2_test_"))
        bucket_name = f"smoke-test-{uuid.uuid4().hex[:8]}"
        simulated_bucket_path = temp_dir / "simulated_s3" / bucket_name
        external_drive_root = Path(deps.config.LOCAL_BASE_PATH)
        drive_checker = deps.drive_checker_cls(external_drive_root)
        drive_checker.check_available()
        local_bucket_path = external_drive_root / bucket_name
        if local_bucket_path.exists():
            msg = "Smoke-test bucket path already exists on external drive: " f"{local_bucket_path}"
            raise RuntimeError(msg)
        backup_state_db = Path(temp_dir / "smoke_state.db")
        return cls(
            deps=deps,
            temp_dir=temp_dir,
            bucket_name=bucket_name,
            simulated_bucket_path=simulated_bucket_path,
            external_drive_root=external_drive_root,
            local_bucket_path=local_bucket_path,
            backup_state_db=backup_state_db,
            should_cleanup=True,
            original_boto_client=boto3.client,
            original_popen=subprocess.Popen,
            original_input=builtins.input,
            original_state_db=deps.config.STATE_DB_PATH,
            original_exclusions=list(deps.config.EXCLUDED_BUCKETS),
        )

    def restore(self):
        boto3.client = self.original_boto_client
        subprocess.Popen = self.original_popen
        builtins.input = self.original_input
        self.deps.config.STATE_DB_PATH = self.original_state_db
        self.deps.config.EXCLUDED_BUCKETS = self.original_exclusions
        if self.should_cleanup:
            shutil.rmtree(self.temp_dir, ignore_errors=True)


@dataclass(frozen=True)
class _SimulatedBucketStats:
    """Captures the generated sample data for the simulated smoke test."""

    files_created: int
    dirs_created: int
    total_bytes: int
    manifest_before: dict[str, Any]
    object_entries: list[dict[str, Any]]


def _seed_simulated_bucket(ctx: _SimulatedSmokeContext) -> _SimulatedBucketStats:
    """Create local sample data to mimic an S3 bucket."""
    print("Step 1/3: Creating sample files in simulated S3...")
    files_created, dirs_created, total_bytes = materialize_sample_tree(ctx.simulated_bucket_path)
    object_entries = _build_object_entries(ctx.simulated_bucket_path)
    manifest_before = manifest_directory(ctx.simulated_bucket_path)
    print(
        f"Seeded 's3://{ctx.bucket_name}' with {files_created} files "
        f"({total_bytes} bytes across {dirs_created} directories)."
    )
    return _SimulatedBucketStats(
        files_created=files_created,
        dirs_created=dirs_created,
        total_bytes=total_bytes,
        manifest_before=manifest_before,
        object_entries=object_entries,
    )


def _build_object_entries(simulated_bucket_path: Path) -> list[dict[str, Any]]:
    """Enumerate simulated files and produce S3-like metadata."""
    object_entries: list[dict[str, Any]] = []
    for file_path in sorted(simulated_bucket_path.rglob("*")):
        if not file_path.is_file():
            continue
        stat_info = file_path.stat()
        file_bytes = file_path.read_bytes()
        try:
            etag = hashlib.md5(file_bytes, usedforsecurity=False).hexdigest()
        except TypeError:  # pragma: no cover - fallback for Python<3.9
            # Legacy Python lacks usedforsecurity flag; MD5 still matches simulated S3 ETags.
            etag = hashlib.md5(file_bytes).hexdigest()  # nosec
        object_entries.append(
            {
                "Key": file_path.relative_to(simulated_bucket_path).as_posix(),
                "Size": stat_info.st_size,
                "ETag": etag,
                "StorageClass": "STANDARD",
                "LastModified": datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc),
            }
        )
    return object_entries


def _install_simulated_hooks(ctx: _SimulatedSmokeContext, object_entries: list[dict[str, Any]]):
    """Monkeypatch AWS/boto/subprocess plumbing to use simulated data."""
    simulated_s3_client = _SimulatedS3Client(ctx.bucket_name, object_entries)

    def _fake_boto3_client(service_name, *args, **kwargs):
        if service_name == "s3":
            return simulated_s3_client
        return ctx.original_boto_client(service_name, *args, **kwargs)

    def _fake_popen(cmd, *popen_args, **popen_kwargs):
        if len(cmd) >= AWS_SYNC_MIN_ARGS and cmd[:3] == ["aws", "s3", "sync"]:
            s3_url = cmd[3]
            if not s3_url.startswith("s3://"):
                msg = f"Unexpected sync source: {s3_url}"
                raise RuntimeError(msg)
            target_bucket = s3_url[5:].strip("/").split("/")[0]
            if target_bucket != ctx.bucket_name:
                msg = f"Smoke test only supports bucket {ctx.bucket_name}"
                raise RuntimeError(msg)
            dest_path = Path(cmd[4].rstrip("/"))
            return _FakeAwsSyncProcess(ctx.simulated_bucket_path, dest_path, object_entries)
        return ctx.original_popen(cmd, *popen_args, **popen_kwargs)

    boto3.client = _fake_boto3_client
    subprocess.Popen = _fake_popen
    builtins.input = lambda _prompt="": "no"
    ctx.deps.config.STATE_DB_PATH = str(ctx.backup_state_db)
    ctx.deps.config.EXCLUDED_BUCKETS = []


def _run_simulated_workflow(ctx: _SimulatedSmokeContext, manifest_before):
    """Execute the real migrator against the simulated bucket."""
    print()
    print("Step 2/3: Running full migrate_v2 workflow...")
    migrator = ctx.deps.create_migrator()
    migrator.run()
    manifest_after = manifest_directory(ctx.local_bucket_path)
    ensure_matching_manifests(manifest_before, manifest_after)
    print("Verified downloaded files on the external drive.")


def _cleanup_simulated_data(ctx: _SimulatedSmokeContext):
    """Remove the temporary files copied during the smoke test."""
    print()
    print("Step 3/3: Removing local files moved for the smoke test...")
    shutil.rmtree(ctx.local_bucket_path, ignore_errors=True)
    print("Deleted smoke-test data from external drive.")
    shutil.rmtree(ctx.simulated_bucket_path, ignore_errors=True)
    print("Deleted simulated S3 data.")


def _print_simulated_report(ctx: _SimulatedSmokeContext, stats: _SimulatedBucketStats):
    """Display the final simulated smoke-test report."""
    print("\nSmoke test completed successfully!")
    print("=" * 70)
    print("SMOKE TEST REPORT")
    print("=" * 70)
    print(f"Simulated bucket : s3://{ctx.bucket_name}")
    print(f"Files processed  : {stats.files_created}")
    print(f"Directories used : {stats.dirs_created}")
    print(f"Total data       : {stats.total_bytes} bytes")
    print("External drive   :", ctx.external_drive_root)
    print("Flow             : create files -> run prod script -> delete local data")
    print("=" * 70)


__all__ = ["run_simulated_smoke_test"]
