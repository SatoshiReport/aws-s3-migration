"""Batch tests for cost_toolkit audit scripts - Part 1."""

from __future__ import annotations

from cost_toolkit.scripts.audit import (
    aws_ami_snapshot_analysis,
    aws_backup_audit,
    aws_comprehensive_vpc_audit,
    aws_ebs_audit,
    aws_ebs_post_termination_audit,
    aws_ec2_compute_detailed_audit,
    aws_ec2_usage_audit,
    aws_elastic_ip_audit,
    aws_instance_connection_info,
    aws_kms_audit,
    aws_network_interface_audit,
    aws_network_interface_deep_audit,
    aws_rds_audit,
    aws_rds_network_interface_audit,
)


class TestAmiSnapshotAnalysis:
    """Tests for aws_ami_snapshot_analysis.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_ami_snapshot_analysis is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_ami_snapshot_analysis, "main")


class TestBackupAudit:
    """Tests for aws_backup_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_backup_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_backup_audit, "main")


class TestComprehensiveVpcAudit:
    """Tests for aws_comprehensive_vpc_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_comprehensive_vpc_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_comprehensive_vpc_audit, "main")


class TestEbsAudit:
    """Tests for aws_ebs_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_ebs_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_ebs_audit, "main")


class TestEbsPostTerminationAudit:
    """Tests for aws_ebs_post_termination_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_ebs_post_termination_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_ebs_post_termination_audit, "main")


class TestEc2ComputeDetailedAudit:
    """Tests for aws_ec2_compute_detailed_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_ec2_compute_detailed_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_ec2_compute_detailed_audit, "main")


class TestEc2UsageAudit:
    """Tests for aws_ec2_usage_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_ec2_usage_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_ec2_usage_audit, "main")


class TestElasticIpAudit:
    """Tests for aws_elastic_ip_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_elastic_ip_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_elastic_ip_audit, "main")


class TestInstanceConnectionInfo:
    """Tests for aws_instance_connection_info.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_instance_connection_info is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_instance_connection_info, "main")


class TestKmsAudit:
    """Tests for aws_kms_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_kms_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_kms_audit, "main")


class TestNetworkInterfaceAudit:
    """Tests for aws_network_interface_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_network_interface_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_network_interface_audit, "main")


class TestNetworkInterfaceDeepAudit:
    """Tests for aws_network_interface_deep_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_network_interface_deep_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_network_interface_deep_audit, "main")


class TestRdsAudit:
    """Tests for aws_rds_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_rds_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_rds_audit, "main")


class TestRdsNetworkInterfaceAudit:
    """Tests for aws_rds_network_interface_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_rds_network_interface_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_rds_network_interface_audit, "main")
