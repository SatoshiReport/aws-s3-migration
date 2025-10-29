"""
Glacier restore handler for managing archived S3 objects.
"""
import boto3
from typing import Dict, List
from migration_state import MigrationState, FileState
import config


class GlacierHandler:
    """
    Manages Glacier restore operations for archived S3 objects.
    """

    # Glacier storage classes that require restore
    # Note: GLACIER_IR (Instant Retrieval) does NOT require restore - it's immediately accessible
    GLACIER_CLASSES = {
        'GLACIER',
        'DEEP_ARCHIVE'
    }

    def __init__(self, state: MigrationState):
        self.state = state
        self.s3 = boto3.client('s3')

    def is_glacier_storage(self, storage_class: str) -> bool:
        """Check if storage class is Glacier"""
        return storage_class in self.GLACIER_CLASSES

    def request_restore(self, file_info: Dict) -> bool:
        """
        Request restore for a Glacier object.

        Args:
            file_info: File information from state database

        Returns:
            True if restore requested successfully, False otherwise
        """
        bucket = file_info['bucket']
        key = file_info['key']
        storage_class = file_info['storage_class']

        try:
            # Check if already being restored
            try:
                response = self.s3.head_object(Bucket=bucket, Key=key)
                restore_status = response.get('Restore')

                if restore_status:
                    if 'ongoing-request="false"' in restore_status:
                        # Already restored and available
                        print(f"  Already restored: {bucket}/{key}")
                        self.state.update_state(bucket, key, FileState.DISCOVERED)
                        return True
                    else:
                        # Restore already in progress
                        print(f"  Restore already in progress: {bucket}/{key}")
                        self.state.mark_glacier_restore_requested(bucket, key)
                        return True
            except Exception:
                pass

            # Determine restore tier based on storage class
            if storage_class == 'DEEP_ARCHIVE':
                restore_tier = 'Standard'  # Deep Archive only supports Standard or Bulk
            else:
                restore_tier = config.GLACIER_RESTORE_TIER

            # Request restore
            self.s3.restore_object(
                Bucket=bucket,
                Key=key,
                RestoreRequest={
                    'Days': config.GLACIER_RESTORE_DAYS,
                    'GlacierJobParameters': {
                        'Tier': restore_tier
                    }
                }
            )

            print(f"  Restore requested: {bucket}/{key} (tier: {restore_tier})")
            self.state.mark_glacier_restore_requested(bucket, key)
            return True

        except self.s3.exceptions.RestoreAlreadyInProgress:
            print(f"  Restore already in progress: {bucket}/{key}")
            self.state.mark_glacier_restore_requested(bucket, key)
            return True

        except Exception as e:
            error_msg = f"Restore request failed: {str(e)}"
            print(f"  ERROR: {bucket}/{key}: {error_msg}")
            self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
            return False

    def check_restore_status(self, file_info: Dict) -> str:
        """
        Check if Glacier restore is complete.

        Args:
            file_info: File information from state database

        Returns:
            'available' if restored, 'in_progress' if still restoring, 'failed' on error
        """
        bucket = file_info['bucket']
        key = file_info['key']

        try:
            response = self.s3.head_object(Bucket=bucket, Key=key)
            restore_status = response.get('Restore')

            if not restore_status:
                # No restore status - restore hasn't been requested or expired
                # Don't mark as failed, keep in current state for retry
                print(f"  WARNING: No restore status for {bucket}/{key}")
                return 'in_progress'

            if 'ongoing-request="false"' in restore_status:
                # Restore complete
                self.state.update_state(bucket, key, FileState.DISCOVERED)
                return 'available'
            else:
                # Still restoring
                self.state.update_state(bucket, key, FileState.GLACIER_RESTORING)
                return 'in_progress'

        except Exception as e:
            error_msg = f"Status check failed: {str(e)}"
            print(f"  ERROR: {bucket}/{key}: {error_msg}")
            self.state.update_state(bucket, key, FileState.ERROR, error_message=error_msg)
            return 'failed'

    def process_glacier_files(self) -> Dict[str, int]:
        """
        Process Glacier files: request restores and check status.

        Returns:
            Dictionary with counts of requested, available, in_progress
        """
        stats = {
            'requested': 0,
            'available': 0,
            'in_progress': 0,
            'failed': 0
        }

        # Get files that need restore requests
        discovered_glacier = self.state.get_files_by_state(FileState.DISCOVERED)
        glacier_files = [
            f for f in discovered_glacier
            if self.is_glacier_storage(f['storage_class'])
        ]

        # Request restores (up to MAX_GLACIER_RESTORES)
        to_request = glacier_files[:config.MAX_GLACIER_RESTORES]
        for file_info in to_request:
            if self.request_restore(file_info):
                stats['requested'] += 1

        # Check status of files being restored
        restoring_files = self.state.get_glacier_files_to_check()
        for file_info in restoring_files:
            status = self.check_restore_status(file_info)
            if status == 'available':
                stats['available'] += 1
            elif status == 'in_progress':
                stats['in_progress'] += 1
            elif status == 'failed':
                stats['failed'] += 1

        return stats

    def get_glacier_summary(self) -> Dict:
        """Get summary of Glacier files"""
        stats = self.state.get_statistics()

        # Count Glacier files in discovered state
        discovered = self.state.get_files_by_state(FileState.DISCOVERED)
        glacier_discovered = sum(
            1 for f in discovered
            if self.is_glacier_storage(f['storage_class'])
        )

        return {
            'discovered': glacier_discovered,
            'restore_requested': stats.get(FileState.GLACIER_RESTORE_REQUESTED, {}).get('count', 0),
            'restoring': stats.get(FileState.GLACIER_RESTORING, {}).get('count', 0)
        }
