"""Batch tests for cost_toolkit setup scripts."""

from __future__ import annotations

from cost_toolkit.scripts.setup import (
    aws_route53_domain_setup,
    aws_vmimport_role_setup,
    exceptions,
    route53_helpers,
    verify_iwannabenewyork_domain,
)


class TestSetupModules:
    """Tests for setup modules."""

    def test_exceptions_imports(self):
        """Test exceptions module can be imported."""
        assert exceptions is not None

    def test_route53_domain_setup_imports(self):
        """Test aws_route53_domain_setup module can be imported."""
        assert aws_route53_domain_setup is not None

    def test_route53_domain_setup_main_exists(self):
        """Test aws_route53_domain_setup has main function."""
        assert hasattr(aws_route53_domain_setup, "main")

    def test_vmimport_role_setup_imports(self):
        """Test aws_vmimport_role_setup module can be imported."""
        assert aws_vmimport_role_setup is not None

    def test_vmimport_role_setup_main_exists(self):
        """Test aws_vmimport_role_setup has main function."""
        assert hasattr(aws_vmimport_role_setup, "main")

    def test_route53_helpers_imports(self):
        """Test route53_helpers module can be imported."""
        assert route53_helpers is not None

    def test_verify_iwannabenewyork_domain_imports(self):
        """Test verify_iwannabenewyork_domain module can be imported."""
        assert verify_iwannabenewyork_domain is not None

    def test_verify_iwannabenewyork_domain_main_exists(self):
        """Test verify_iwannabenewyork_domain has main function."""
        assert hasattr(verify_iwannabenewyork_domain, "main")
