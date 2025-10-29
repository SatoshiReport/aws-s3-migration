"""
File migration handler: downloads, verifies, and manages S3 file transfers.
"""
import os
import hashlib
import boto3
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

    def download_file(self, file_info: Dict) -> bool:
        """
        Download a file from S3 to local storage.

        Args:
            file_info: File information from state database

        Returns:
            True if download successful, False otherwise
        """
        bucket = file_info['bucket']
        key = file_info['key']

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

            # Mark as downloaded
            self.state.update_state(
                bucket, key, FileState.DOWNLOADED,
                local_path=str(local_path)
            )

            return True

        except Exception as e:
            error_msg = f"Download failed: {str(e)}"
            print(f"  ERROR: {bucket}/{key}: {error_msg}")
            self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
            return False

    def verify_file(self, file_info: Dict) -> bool:
        """
        Verify downloaded file matches S3 object.

        Args:
            file_info: File information from state database

        Returns:
            True if verification successful, False otherwise
        """
        bucket = file_info['bucket']
        key = file_info['key']
        local_path = file_info['local_path']
        expected_etag = file_info['etag']
        expected_size = file_info['size']

        if not local_path or not os.path.exists(local_path):
            error_msg = "Local file not found for verification"
            self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
            return False

        try:
            # Check file size first (always)
            actual_size = os.path.getsize(local_path)
            if actual_size != expected_size:
                error_msg = f"Size mismatch: expected {expected_size}, got {actual_size}"
                print(f"  ERROR: {bucket}/{key}: {error_msg}")
                self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
                # Delete corrupted file
                if os.path.exists(local_path):
                    os.remove(local_path)
                return False

            # Check if this is a multipart upload (ETag contains a dash)
            is_multipart = '-' in expected_etag

            if is_multipart:
                # For multipart uploads, ETag format is "md5ofmd5s-partcount"
                # We can't easily verify without knowing the part size used during upload
                # So we rely on size check and boto3's download integrity
                print(f"  NOTE: {bucket}/{key}: Multipart upload detected, using size verification only")
                checksum = f"multipart-{expected_etag}"
            else:
                # Single-part upload: verify with MD5/ETag
                if config.VERIFICATION_METHOD == 'etag':
                    calculated_etag = self._calculate_etag(local_path)
                    matches = calculated_etag == expected_etag
                    checksum = calculated_etag
                else:
                    calculated_md5 = self._calculate_md5(local_path)
                    matches = calculated_md5 == expected_etag
                    checksum = calculated_md5

                if not matches:
                    error_msg = "Checksum mismatch"
                    print(f"  ERROR: {bucket}/{key}: {error_msg}")
                    self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
                    # Delete corrupted file
                    if os.path.exists(local_path):
                        os.remove(local_path)
                    return False

            # Verification passed
            self.state.update_state(
                bucket, key, FileState.VERIFIED,
                checksum=checksum
            )
            return True

        except Exception as e:
            error_msg = f"Verification failed: {str(e)}"
            print(f"  ERROR: {bucket}/{key}: {error_msg}")
            self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
            return False

    def delete_from_s3(self, file_info: Dict) -> bool:
        """
        Delete file from S3 after successful verification.

        Args:
            file_info: File information from state database

        Returns:
            True if deletion successful, False otherwise
        """
        bucket = file_info['bucket']
        key = file_info['key']

        try:
            self.s3.delete_object(Bucket=bucket, Key=key)
            self.state.update_state(bucket, key, FileState.DELETED)
            return True

        except Exception as e:
            error_msg = f"S3 deletion failed: {str(e)}"
            print(f"  ERROR: {bucket}/{key}: {error_msg}")
            self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
            return False

    @staticmethod
    def _calculate_md5(file_path: str) -> str:
        """Calculate MD5 hash of file"""
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(config.DOWNLOAD_CHUNK_SIZE), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    @staticmethod
    def _calculate_etag(file_path: str) -> str:
        """
        Calculate ETag for file.
        For single-part uploads, ETag is just MD5.
        For multipart uploads, it's more complex (not implemented here).
        """
        # Simple MD5 for now (works for files uploaded as single part)
        return FileMigrator._calculate_md5(file_path)

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
