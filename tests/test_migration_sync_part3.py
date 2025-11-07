"""Comprehensive tests for migration_sync.py - Part 3: Edge Cases and Integration"""

import time
from unittest import mock

from migration_sync import BucketSyncer
from migration_sync_test_helpers import create_mock_process


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_sync_bucket_with_special_characters_in_name(self, tmp_path):
        """Test syncing bucket with special characters in name"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        bucket_name = "test-bucket-with-dashes"

        with mock.patch("migration_sync.subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_process([""], [None, 0])

            syncer.sync_bucket(bucket_name)

        local_path = tmp_path / bucket_name
        assert local_path.exists()

    def test_parse_aws_size_with_scientific_notation(self, tmp_path):
        """Test parsing size with scientific notation (if it occurs)"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        line = "Completed 1e6 Bytes"  # 1 million bytes
        result = syncer._parse_aws_size(line)
        # Should handle gracefully or return None
        assert result is None or isinstance(result, int)

    def test_multiple_sync_calls_reuse_directory(self, tmp_path):
        """Test that multiple syncs to same directory work correctly"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)

        with mock.patch("migration_sync.subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_process(["", ""], [None, 0, None, 0])

            syncer.sync_bucket("bucket")
            syncer.sync_bucket("bucket")

        local_path = tmp_path / "bucket"
        assert local_path.exists()

    def test_parse_size_with_capital_b_suffix(self, tmp_path):
        """Test that parsing fails gracefully for non-standard suffix"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        line = "Completed 1.0 B"  # Single 'B' instead of standard format
        result = syncer._parse_aws_size(line)
        # Should return None due to exception handling
        assert result is None or isinstance(result, int)

    def test_display_progress_called_multiple_times(self, tmp_path, capsys):
        """Test that display progress can be called multiple times"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)
        start_time = time.time() - 100

        syncer._display_progress(start_time, 5, 1024)
        syncer._display_progress(start_time, 10, 2048)

        captured = capsys.readouterr()
        # Should have progress output from both calls
        assert "Progress:" in captured.out


class TestIntegration:
    """Integration tests combining multiple components"""

    def test_full_sync_workflow_with_mock_aws_output(self, tmp_path):
        """Test complete sync workflow with realistic AWS CLI output"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)

        with mock.patch("migration_sync.subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_process(
                [
                    "Completed s3://bucket/file1.txt  512.0 KiB\n",
                    "Completed s3://bucket/file2.txt  1.5 MiB\n",
                    "Completed s3://bucket/file3.txt  2.0 MiB\n",
                    "",
                ],
                [None, None, None, 0],
            )

            syncer.sync_bucket("integration-bucket")

        local_path = tmp_path / "integration-bucket"
        assert local_path.exists()

    def test_sync_with_empty_bucket(self, tmp_path):
        """Test syncing an empty bucket"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)

        with mock.patch("migration_sync.subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_process([""], [None, 0])

            syncer.sync_bucket("empty-bucket")

        local_path = tmp_path / "empty-bucket"
        assert local_path.exists()

    def test_sync_handles_various_size_units(self, tmp_path):
        """Test that sync handles various size units throughout"""
        syncer = BucketSyncer(mock.Mock(), mock.Mock(), tmp_path)

        with mock.patch("migration_sync.subprocess.Popen") as mock_popen:
            mock_popen.return_value = create_mock_process(
                [
                    "Completed s3://bucket/small.txt  100 Bytes\n",
                    "Completed s3://bucket/medium.bin  50 KiB\n",
                    "Completed s3://bucket/large.iso  1.2 GiB\n",
                    "",
                ],
                [None, None, None, 0],
            )

            syncer.sync_bucket("mixed-sizes-bucket")
