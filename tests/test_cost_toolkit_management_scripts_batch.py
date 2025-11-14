"""Batch tests for cost_toolkit management scripts."""

from __future__ import annotations

from cost_toolkit.scripts.management import (
    aws_s3_standardization,
    aws_volume_cleanup,
)


class TestAwsS3Standardization:
    """Tests for aws_s3_standardization.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_s3_standardization is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_s3_standardization, "main")


class TestAwsVolumeCleanup:
    """Tests for aws_volume_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_volume_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_volume_cleanup, "main")
