"""Batch tests for cost_toolkit VPC cleanup scripts."""

from __future__ import annotations

from cost_toolkit.scripts.cleanup import (
    aws_vpc_cleanup,
    aws_vpc_cleanup_unused_resources,
    aws_vpc_final_cleanup,
    aws_vpc_immediate_cleanup,
    aws_vpc_safe_deletion,
)


class TestVpcCleanup:
    """Tests for aws_vpc_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_vpc_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_vpc_cleanup, "main")


class TestVpcCleanupUnusedResources:
    """Tests for aws_vpc_cleanup_unused_resources.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_vpc_cleanup_unused_resources is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_vpc_cleanup_unused_resources, "main")


class TestVpcFinalCleanup:
    """Tests for aws_vpc_final_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_vpc_final_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_vpc_final_cleanup, "main")


class TestVpcImmediateCleanup:
    """Tests for aws_vpc_immediate_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_vpc_immediate_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_vpc_immediate_cleanup, "main")


class TestVpcSafeDeletion:
    """Tests for aws_vpc_safe_deletion.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_vpc_safe_deletion is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_vpc_safe_deletion, "main")
