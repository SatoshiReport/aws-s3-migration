"""Batch tests for cost_toolkit cleanup scripts - Part 2."""

from __future__ import annotations

from cost_toolkit.scripts.cleanup import (
    aws_global_accelerator_cleanup,
    aws_instance_termination,
    aws_kms_cleanup,
    aws_lambda_cleanup,
    aws_lightsail_cleanup,
    aws_orphaned_rds_network_interface_cleanup,
    aws_rds_cleanup,
    aws_remove_public_ip,
    aws_remove_public_ip_advanced,
    aws_route53_cleanup,
    aws_security_group_circular_cleanup,
    aws_snapshot_bulk_delete,
    aws_snapshot_cleanup_final,
    aws_stopped_instance_cleanup,
)


class TestGlobalAcceleratorCleanup:
    """Tests for aws_global_accelerator_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_global_accelerator_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_global_accelerator_cleanup, "main")


class TestInstanceTermination:
    """Tests for aws_instance_termination.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_instance_termination is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_instance_termination, "main")


class TestKmsCleanup:
    """Tests for aws_kms_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_kms_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_kms_cleanup, "main")


class TestLambdaCleanup:
    """Tests for aws_lambda_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_lambda_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_lambda_cleanup, "main")


class TestLightsailCleanup:
    """Tests for aws_lightsail_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_lightsail_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_lightsail_cleanup, "main")


class TestOrphanedRdsNetworkInterfaceCleanup:
    """Tests for aws_orphaned_rds_network_interface_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_orphaned_rds_network_interface_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_orphaned_rds_network_interface_cleanup, "main")


class TestRdsCleanup:
    """Tests for aws_rds_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_rds_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_rds_cleanup, "main")


class TestRemovePublicIp:
    """Tests for aws_remove_public_ip.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_remove_public_ip is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_remove_public_ip, "main")


class TestRemovePublicIpAdvanced:
    """Tests for aws_remove_public_ip_advanced.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_remove_public_ip_advanced is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_remove_public_ip_advanced, "main")


class TestRoute53Cleanup:
    """Tests for aws_route53_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_route53_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_route53_cleanup, "main")


class TestSecurityGroupCircularCleanup:
    """Tests for aws_security_group_circular_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_security_group_circular_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_security_group_circular_cleanup, "main")


class TestSnapshotBulkDelete:
    """Tests for aws_snapshot_bulk_delete.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_snapshot_bulk_delete is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_snapshot_bulk_delete, "main")


class TestSnapshotCleanupFinal:
    """Tests for aws_snapshot_cleanup_final.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_snapshot_cleanup_final is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_snapshot_cleanup_final, "main")


class TestStoppedInstanceCleanup:
    """Tests for aws_stopped_instance_cleanup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_stopped_instance_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_stopped_instance_cleanup, "main")
