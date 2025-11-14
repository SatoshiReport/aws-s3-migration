"""Batch tests for cost_toolkit cleanup scripts - Part 1."""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.scripts.cleanup import (
    aws_ami_deregister_bulk,
    aws_backup_disable,
    aws_cleanup_failed_export_amis,
    aws_cleanup_script,
    aws_cleanup_unused_resources,
    aws_cloudwatch_cleanup,
    aws_ec2_instance_cleanup,
    aws_efs_cleanup,
    aws_fix_termination_protection,
    aws_fix_termination_protection_and_terminate,
)


class TestAmiDeregisterBulk:
    """Tests for aws_ami_deregister_bulk.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_ami_deregister_bulk is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_ami_deregister_bulk, "main")

    def test_main_with_no_args(self):
        """Test main function with no arguments."""
        with patch("boto3.client"):
            with patch("sys.argv", ["script"]):
                with patch("builtins.input", return_value=""):
                    try:
                        aws_ami_deregister_bulk.main()
                    except SystemExit:
                        pass


class TestBackupDisable:
    """Tests for aws_backup_disable.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_backup_disable is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_backup_disable, "main")

    def test_has_docstring(self):
        """Test module has docstring."""
        assert aws_backup_disable.__doc__ is not None


class TestCleanupFailedExportAmis:
    """Tests for aws_cleanup_failed_export_amis.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_cleanup_failed_export_amis is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_cleanup_failed_export_amis, "main")


class TestCleanupScript:
    """Tests for aws_cleanup_script.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_cleanup_script is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_cleanup_script, "main")


class TestCleanupUnusedResources:
    """Tests for aws_cleanup_unused_resources.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_cleanup_unused_resources is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_cleanup_unused_resources, "main")


class TestCloudWatchCleanup:
    """Tests for aws_cloudwatch_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_cloudwatch_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_cloudwatch_cleanup, "main")


class TestEc2InstanceCleanup:
    """Tests for aws_ec2_instance_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_ec2_instance_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_ec2_instance_cleanup, "main")


class TestEfsCleanup:
    """Tests for aws_efs_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_efs_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_efs_cleanup, "main")


class TestFixTerminationProtection:
    """Tests for aws_fix_termination_protection.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_fix_termination_protection is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_fix_termination_protection, "main")


class TestFixTerminationProtectionAndTerminate:
    """Tests for aws_fix_termination_protection_and_terminate.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_fix_termination_protection_and_terminate is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_fix_termination_protection_and_terminate, "main")
