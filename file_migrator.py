"""
File migration handler: downloads, verifies, and manages S3 file transfers.
"""
import os
import time
import boto3
from botocore.exceptions import ClientError
from boto3.s3.transfer import TransferConfig
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional
from pathlib import Path
from migration_state import MigrationState, FileState
import config


class FileMigrator:
    """
    Handles downloading files from S3, verifying integrity, and tracking state.
    """

    def __init__(self, state: MigrationState):
        self.state = state
        self.s3 = boto3.client('s3')
        self.base_path = Path(config.LOCAL_BASE_PATH)

        # Configure S3 Transfer Manager for optimized downloads
        self.transfer_config = TransferConfig(
            multipart_threshold=config.MULTIPART_THRESHOLD,
            multipart_chunksize=config.MULTIPART_CHUNKSIZE,
            max_concurrency=config.MAX_CONCURRENCY,
            use_threads=config.USE_THREADS
        )

        # AWS throttle detection
        self.throttle_count = 0
        self.backoff_until = 0
        self.last_throttle_warning = 0

    def download_file(self, file_info: Dict) -> bool:
        """
        Download a file from S3 to local storage with AWS throttle detection.

        Args:
            file_info: File information from state database

        Returns:
            True if download successful, False otherwise
        """
        bucket = file_info['bucket']
        key = file_info['key']

        # Check if we're in backoff period
        if time.time() < self.backoff_until:
            return False  # Skip this file, will retry later

        # Build local path: base_path/bucket/key
        local_path = self.base_path / bucket / key
        local_dir = local_path.parent

        try:
            # Mark as downloading
            self.state.update_state(bucket, key, FileState.DOWNLOADING)

            # Create directory if needed
            local_dir.mkdir(parents=True, exist_ok=True)

            # Download file with optimized transfer config
            self.s3.download_file(
                Bucket=bucket,
                Key=key,
                Filename=str(local_path),
                Config=self.transfer_config
            )

            # Success - reset throttle counter
            self.throttle_count = 0

            # Mark as downloaded
            self.state.update_state(
                bucket, key, FileState.DOWNLOADED,
                local_path=str(local_path)
            )

            return True

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')

            # Detect AWS throttling
            if error_code in ['SlowDown', 'RequestLimitExceeded', '503']:
                self.throttle_count += 1
                backoff_seconds = min(60, 2 ** self.throttle_count)
                self.backoff_until = time.time() + backoff_seconds

                # Print warning (but not too frequently)
                current_time = time.time()
                if current_time - self.last_throttle_warning > 10:
                    print(f"\n⚠️  AWS THROTTLING DETECTED!")
                    print(f"   Error: {error_code}")
                    print(f"   Backing off for {backoff_seconds} seconds")
                    print(f"   Throttle count: {self.throttle_count}")
                    self.last_throttle_warning = current_time

                # Reset file state to discovered so it will be retried
                self.state.update_state(bucket, key, FileState.DISCOVERED)
                return False

            # Other AWS errors
            error_msg = f"Download failed: {error_code} - {str(e)}"
            print(f"  ERROR: {bucket}/{key}: {error_msg}")
            self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
            return False

        except Exception as e:
            # Non-AWS errors
            error_msg = f"Download failed: {str(e)}"
            print(f"  ERROR: {bucket}/{key}: {error_msg}")
            self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
            return False

    def verify_file(self, file_info: Dict) -> bool:
        """
        Verify downloaded file matches S3 object.

        boto3 already verifies integrity during download using checksums.
        We just verify size to catch any disk write issues.

        Args:
            file_info: File information from state database

        Returns:
            True if verification successful, False otherwise
        """
        bucket = file_info['bucket']
        key = file_info['key']
        local_path = file_info['local_path']
        expected_size = file_info['size']

        if not local_path or not os.path.exists(local_path):
            error_msg = "Local file not found for verification"
            self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
            return False

        try:
            # Verify file size (boto3 already verified integrity during download)
            actual_size = os.path.getsize(local_path)
            if actual_size != expected_size:
                error_msg = f"Size mismatch: expected {expected_size}, got {actual_size}"
                print(f"  ERROR: {bucket}/{key}: {error_msg}")
                self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
                # Delete corrupted file
                if os.path.exists(local_path):
                    os.remove(local_path)
                return False

            # Verification passed - size matches and boto3 verified integrity during download
            self.state.update_state(
                bucket, key, FileState.VERIFIED,
                checksum=f"size-verified-{expected_size}"
            )
            return True

        except Exception as e:
            error_msg = f"Verification failed: {str(e)}"
            print(f"  ERROR: {bucket}/{key}: {error_msg}")
            self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
            return False

    def delete_from_s3(self, file_info: Dict) -> bool:
        """
        Delete file from S3 after successful verification with throttle detection.

        Args:
            file_info: File information from state database

        Returns:
            True if deletion successful, False otherwise
        """
        bucket = file_info['bucket']
        key = file_info['key']

        # Check if we're in backoff period
        if time.time() < self.backoff_until:
            return False  # Skip this file, will retry later

        try:
            self.s3.delete_object(Bucket=bucket, Key=key)
            self.throttle_count = 0  # Reset on success
            self.state.update_state(bucket, key, FileState.DELETED)
            return True

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')

            # Detect AWS throttling
            if error_code in ['SlowDown', 'RequestLimitExceeded', '503']:
                self.throttle_count += 1
                backoff_seconds = min(60, 2 ** self.throttle_count)
                self.backoff_until = time.time() + backoff_seconds

                # Print warning (but not too frequently)
                current_time = time.time()
                if current_time - self.last_throttle_warning > 10:
                    print(f"\n⚠️  AWS THROTTLING DETECTED (DELETE)!")
                    print(f"   Error: {error_code}")
                    print(f"   Backing off for {backoff_seconds} seconds")
                    print(f"   Throttle count: {self.throttle_count}")
                    self.last_throttle_warning = current_time

                # Keep in VERIFIED state so deletion will be retried
                return False

            # Other AWS errors
            error_msg = f"S3 deletion failed: {error_code} - {str(e)}"
            print(f"  ERROR: {bucket}/{key}: {error_msg}")
            self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
            return False

        except Exception as e:
            # Non-AWS errors
            error_msg = f"S3 deletion failed: {str(e)}"
            print(f"  ERROR: {bucket}/{key}: {error_msg}")
            self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
            return False


    def process_file(self, file_info: Dict) -> bool:
        """
        Complete workflow: download, verify, delete.

        Args:
            file_info: File information from state database

        Returns:
            True if entire process successful, False otherwise
        """
        bucket = file_info['bucket']
        key = file_info['key']

        # Download
        if not self.download_file(file_info):
            return False

        # Need to refresh file_info after download
        file_info = self.state.get_file(bucket, key)

        # Verify
        if not self.verify_file(file_info):
            return False

        # Delete from S3
        if not self.delete_from_s3(file_info):
            return False

        return True
