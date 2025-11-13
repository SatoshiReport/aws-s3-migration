"""Batch tests for VPC cleanup scripts."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestVpcCleanup:
    """Tests for aws_vpc_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.cleanup import aws_vpc_cleanup

        assert aws_vpc_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        from cost_toolkit.scripts.cleanup import aws_vpc_cleanup

        assert hasattr(aws_vpc_cleanup, "main")


class TestVpcCleanupUnusedResources:
    """Tests for aws_vpc_cleanup_unused_resources.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.cleanup import aws_vpc_cleanup_unused_resources

        assert aws_vpc_cleanup_unused_resources is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        from cost_toolkit.scripts.cleanup import aws_vpc_cleanup_unused_resources

        assert hasattr(aws_vpc_cleanup_unused_resources, "main")


class TestVpcFinalCleanup:
    """Tests for aws_vpc_final_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.cleanup import aws_vpc_final_cleanup

        assert aws_vpc_final_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        from cost_toolkit.scripts.cleanup import aws_vpc_final_cleanup

        assert hasattr(aws_vpc_final_cleanup, "main")


class TestVpcImmediateCleanup:
    """Tests for aws_vpc_immediate_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.cleanup import aws_vpc_immediate_cleanup

        assert aws_vpc_immediate_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        from cost_toolkit.scripts.cleanup import aws_vpc_immediate_cleanup

        assert hasattr(aws_vpc_immediate_cleanup, "main")


class TestVpcSafeDeletion:
    """Tests for aws_vpc_safe_deletion.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.cleanup import aws_vpc_safe_deletion

        assert aws_vpc_safe_deletion is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        from cost_toolkit.scripts.cleanup import aws_vpc_safe_deletion

        assert hasattr(aws_vpc_safe_deletion, "main")
