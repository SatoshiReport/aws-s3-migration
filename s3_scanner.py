"""
S3 bucket scanner for discovering all files across all buckets.
"""
import boto3
import time
from typing import List, Callable, Optional
from migration_state import MigrationState


class S3Scanner:
    """
    Scans S3 buckets and builds inventory in state database.
    """

    def __init__(self, state: MigrationState, progress_callback: Optional[Callable] = None):
        self.s3 = boto3.client('s3')
        self.state = state
        self.progress_callback = progress_callback

    def scan_all_buckets(self, bucket_names: Optional[List[str]] = None):
        """
        Scan all buckets (or specified buckets) and add files to state database.

        Args:
            bucket_names: Optional list of specific buckets to scan.
                         If None, scans all buckets in account.
        """
        if bucket_names is None:
            # Get all buckets
            response = self.s3.list_buckets()
            bucket_names = [b['Name'] for b in response['Buckets']]

        # Skip akiaiw6gwdirbsbuzqiq-arq-1 bucket
        bucket_names = [b for b in bucket_names if b != 'akiaiw6gwdirbsbuzqiq-arq-1']

        # Check which buckets are already scanned
        already_scanned = [b for b in bucket_names if self.state.is_bucket_scanned(b)]
        to_scan = [b for b in bucket_names if not self.state.is_bucket_scanned(b)]

        if already_scanned:
            print(f"Skipping {len(already_scanned)} already-scanned bucket(s):")
            for bucket in already_scanned:
                print(f"  ✓ {bucket}")
            print()

        if not to_scan:
            print("All buckets already scanned!")
            return

        print(f"Scanning {len(to_scan)} bucket(s)...\n")

        cumulative_files = 0
        cumulative_size = 0

        scanned_count = 0
        for idx, bucket in enumerate(to_scan, 1):
            print(f"[{idx}/{len(to_scan)}] Scanning bucket: {bucket}")
            bucket_files, bucket_size = self._scan_bucket(bucket)

            # Mark bucket as scanned
            self.state.mark_bucket_scanned(bucket, bucket_files, bucket_size)

            # Ignore empty buckets
            if bucket_files == 0:
                print(f"  → Empty bucket (ignored)\n")
                continue

            cumulative_files += bucket_files
            cumulative_size += bucket_size
            scanned_count += 1

            # Show running totals after each bucket
            print(f"  → Cumulative: {cumulative_files:,} files, {self._format_size(cumulative_size)} " +
                  f"across {scanned_count} buckets\n")

        print(f"All buckets scanned!")
        print(f"Total discovered in this scan: {cumulative_files:,} files, {self._format_size(cumulative_size)}")

    def _scan_bucket(self, bucket: str):
        """
        Scan a single bucket and add all files to state database.

        Args:
            bucket: Bucket name to scan

        Returns:
            tuple: (file_count, total_size) discovered in this bucket
        """
        paginator = self.s3.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=bucket)

        file_count = 0
        total_size = 0
        last_progress_update = time.time()

        try:
            for page in page_iterator:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    key = obj['Key']
                    size = obj['Size']
                    etag = obj['ETag'].strip('"')
                    storage_class = obj.get('StorageClass', 'STANDARD')
                    last_modified = obj['LastModified'].isoformat()

                    # Add to state database (idempotent)
                    self.state.add_file(
                        bucket=bucket,
                        key=key,
                        size=size,
                        etag=etag,
                        storage_class=storage_class,
                        last_modified=last_modified
                    )

                    file_count += 1
                    total_size += size

                    # Show progress every 5 seconds
                    current_time = time.time()
                    if current_time - last_progress_update >= 5:
                        print(f"  Scanning... {file_count:,} files found ({self._format_size(total_size)})")
                        last_progress_update = current_time

            print(f"  ✓ Found {file_count:,} files ({self._format_size(total_size)}) in this bucket")

        except Exception as e:
            print(f"  ✗ Error scanning bucket {bucket}: {e}")

        return file_count, total_size

    @staticmethod
    def _format_size(bytes_size: int) -> str:
        """Format bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} PB"

    def rescan_bucket(self, bucket: str):
        """
        Rescan a specific bucket.
        Useful if new files were added during migration.

        Args:
            bucket: Bucket name to rescan

        Returns:
            tuple: (file_count, total_size) discovered in the bucket
        """
        print(f"Rescanning bucket: {bucket}")
        return self._scan_bucket(bucket)
