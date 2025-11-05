"""Bucket deletion helpers for migration verification."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, List

try:  # Prefer package-relative imports for tooling like pylint
    from .migration_utils import ProgressTracker, calculate_eta_items, format_duration
    from .migration_verify_common import BucketNotEmptyError
except ImportError:  # pragma: no cover - allow running as standalone script
    from migration_utils import ProgressTracker, calculate_eta_items, format_duration
    from migration_verify_common import BucketNotEmptyError

if TYPE_CHECKING:
    try:
        from .migration_state_v2 import MigrationStateV2
    except ImportError:  # pragma: no cover
        from migration_state_v2 import MigrationStateV2


class BucketDeleter:  # pylint: disable=too-few-public-methods
    """Handles deleting bucket contents from S3."""

    def __init__(self, s3, state: "MigrationStateV2"):
        self.s3 = s3
        self.state = state

    @staticmethod
    def _collect_objects_to_delete(page) -> List[dict]:
        """Collect all object versions and delete markers from a page."""
        objects_to_delete = []
        if "Versions" in page:
            for version in page["Versions"]:
                objects_to_delete.append({"Key": version["Key"], "VersionId": version["VersionId"]})
        if "DeleteMarkers" in page:
            for marker in page["DeleteMarkers"]:
                objects_to_delete.append({"Key": marker["Key"], "VersionId": marker["VersionId"]})
        return objects_to_delete

    def _abort_multipart_uploads(self, bucket: str) -> None:
        """Abort any in-progress multipart uploads for the bucket."""
        paginator = self.s3.get_paginator("list_multipart_uploads")
        aborted = 0
        for page in paginator.paginate(Bucket=bucket):
            uploads = page.get("Uploads", [])
            for upload in uploads:
                self.s3.abort_multipart_upload(
                    Bucket=bucket,
                    Key=upload["Key"],
                    UploadId=upload["UploadId"],
                )
                aborted += 1
        if aborted:
            print(f"  Aborted {aborted:,} multipart uploads before final delete")

    def _bucket_has_contents(self, bucket: str) -> bool:
        """Return True if any versions/delete markers remain in the bucket."""
        paginator = self.s3.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=bucket, PaginationConfig={"MaxItems": 1}):
            if page.get("Versions") or page.get("DeleteMarkers"):
                return True
        return False

    def delete_bucket(self, bucket: str) -> None:  # pylint: disable=too-many-locals
        """Delete a bucket and all its contents from S3 (including all versions)."""
        bucket_info = self.state.get_bucket_info(bucket)
        total_objects = bucket_info["file_count"]
        print(f"  Deleting {total_objects:,} objects from S3 (including all versions)...")
        print()

        paginator = self.s3.get_paginator("list_object_versions")
        deleted_count = 0
        start_time = time.time()
        progress = ProgressTracker(update_interval=2.0)

        for page in paginator.paginate(Bucket=bucket):
            objects_to_delete = self._collect_objects_to_delete(page)

            if objects_to_delete:
                response = self.s3.delete_objects(
                    Bucket=bucket, Delete={"Objects": objects_to_delete}
                )
                errors = response.get("Errors", [])
                if errors:
                    print("\n  Encountered delete errors:")
                    for error in errors:
                        print(
                            f"    Key={error.get('Key')} VersionId={error.get('VersionId')} "
                            f"Code={error.get('Code')} Message={error.get('Message')}"
                        )
                deleted_count += len(objects_to_delete) - len(errors)
                if progress.should_update() or deleted_count % 1000 == 0:
                    elapsed = time.time() - start_time
                    pct = (deleted_count / total_objects * 100) if total_objects > 0 else 0
                    eta_str = calculate_eta_items(elapsed, deleted_count, total_objects)
                    progress_str = (
                        f"Progress: {deleted_count:,} deleted ({pct:.1f}%), ETA: {eta_str}  "
                    )
                    print(f"\r  {progress_str}", end="", flush=True)

        print()
        duration = format_duration(time.time() - start_time)
        print(f"  ✓ Deleted {deleted_count:,} objects/versions in {duration}")
        print()
        self._abort_multipart_uploads(bucket)

        if self._bucket_has_contents(bucket):
            raise BucketNotEmptyError()

        print("  Deleting empty bucket...")
        self.s3.delete_bucket(Bucket=bucket)


__all__ = ["BucketDeleter"]
