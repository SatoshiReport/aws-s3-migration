"""Batch tests for cost_toolkit audit scripts - Part 2."""

from __future__ import annotations

from cost_toolkit.scripts.audit import (
    aws_route53_audit,
    aws_route53_domain_ownership,
    aws_security_group_dependencies,
    aws_vpc_audit,
    aws_vpc_flow_logs_audit,
)


class TestRoute53Audit:
    """Tests for aws_route53_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_route53_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_route53_audit, "main")


class TestRoute53DomainOwnership:
    """Tests for aws_route53_domain_ownership.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_route53_domain_ownership is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_route53_domain_ownership, "main")


class TestSecurityGroupDependencies:
    """Tests for aws_security_group_dependencies.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_security_group_dependencies is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_security_group_dependencies, "main")


class TestVpcAudit:
    """Tests for aws_vpc_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_vpc_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_vpc_audit, "main")


class TestVpcFlowLogsAudit:
    """Tests for aws_vpc_flow_logs_audit.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_vpc_flow_logs_audit is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_vpc_flow_logs_audit, "main")
