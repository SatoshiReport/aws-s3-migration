"""Comprehensive tests for aws_s3_standardization.py - Part 3 (Object Conversion)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.management.aws_s3_standardization import (
    move_objects_to_standard_storage,
)


class TestMoveObjectsToStandardStorageSuccess:
    """Tests for successful object conversion scenarios."""

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_move_objects_to_standard_success(self, mock_create_client, capsys):
        """Test successfully moving objects to standard storage."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        mock_paginator = MagicMock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "file1.txt", "StorageClass": "GLACIER"},
                    {"Key": "file2.txt", "StorageClass": "STANDARD"},
                    {"Key": "file3.txt", "StorageClass": "STANDARD_IA"},
                ]
            }
        ]

        result = move_objects_to_standard_storage("test-bucket", "us-east-1")

        assert result is True
        assert mock_s3_client.copy_object.call_count == 2
        captured = capsys.readouterr()
        assert "Processed 3 objects" in captured.out
        assert "converted 2 to Standard storage" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_move_objects_empty_bucket(self, mock_create_client, capsys):
        """Test moving objects from empty bucket."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        mock_paginator = MagicMock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{}]

        result = move_objects_to_standard_storage("empty-bucket", "us-east-1")

        assert result is True
        mock_s3_client.copy_object.assert_not_called()
        captured = capsys.readouterr()
        assert "Processed 0 objects" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_move_objects_all_standard(self, mock_create_client, capsys):
        """Test when all objects are already standard."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        mock_paginator = MagicMock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "file1.txt", "StorageClass": "STANDARD"},
                    {"Key": "file2.txt", "StorageClass": "STANDARD"},
                ]
            }
        ]

        result = move_objects_to_standard_storage("test-bucket", "us-east-1")

        assert result is True
        mock_s3_client.copy_object.assert_not_called()
        captured = capsys.readouterr()
        assert "converted 0 to Standard storage" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_move_objects_progress_messages(self, mock_create_client, capsys):
        """Test progress messages for large conversions."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        mock_paginator = MagicMock()
        mock_s3_client.get_paginator.return_value = mock_paginator

        objects = [{"Key": f"file{i}.txt", "StorageClass": "GLACIER"} for i in range(150)]
        mock_paginator.paginate.return_value = [{"Contents": objects}]

        result = move_objects_to_standard_storage("large-bucket", "us-east-1")

        assert result is True
        assert mock_s3_client.copy_object.call_count == 150
        captured = capsys.readouterr()
        assert "Converted 100 objects" in captured.out


class TestMoveObjectsToStandardStorageErrors:
    """Tests for object conversion error scenarios."""

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_move_objects_conversion_error(self, mock_create_client, capsys):
        """Test handling conversion errors."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        mock_paginator = MagicMock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"Contents": [{"Key": "file1.txt", "StorageClass": "GLACIER"}]}]
        mock_s3_client.copy_object.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "copy_object")

        result = move_objects_to_standard_storage("test-bucket", "us-east-1")

        assert result is True
        captured = capsys.readouterr()
        assert "Warning: Could not convert" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_move_objects_bucket_error(self, mock_create_client, capsys):
        """Test error accessing bucket."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        mock_paginator = MagicMock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = ClientError({"Error": {"Code": "NoSuchBucket"}}, "list_objects_v2")

        result = move_objects_to_standard_storage("non-existent", "us-east-1")

        assert result is False
        captured = capsys.readouterr()
        assert "Error converting objects" in captured.out
