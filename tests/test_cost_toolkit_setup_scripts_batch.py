"""Batch tests for cost_toolkit setup scripts."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestSetupExceptions:
    """Tests for setup/exceptions.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.setup import exceptions

        assert exceptions is not None


class TestRoute53DomainSetup:
    """Tests for aws_route53_domain_setup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.setup import aws_route53_domain_setup

        assert aws_route53_domain_setup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        from cost_toolkit.scripts.setup import aws_route53_domain_setup

        assert hasattr(aws_route53_domain_setup, "main")


class TestVmimportRoleSetup:
    """Tests for aws_vmimport_role_setup.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.setup import aws_vmimport_role_setup

        assert aws_vmimport_role_setup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        from cost_toolkit.scripts.setup import aws_vmimport_role_setup

        assert hasattr(aws_vmimport_role_setup, "main")


class TestRoute53Helpers:
    """Tests for route53_helpers.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.setup import route53_helpers

        assert route53_helpers is not None


class TestVerifyIwannabenewyorkDomain:
    """Tests for verify_iwannabenewyork_domain.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        from cost_toolkit.scripts.setup import verify_iwannabenewyork_domain

        assert verify_iwannabenewyork_domain is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        from cost_toolkit.scripts.setup import verify_iwannabenewyork_domain

        assert hasattr(verify_iwannabenewyork_domain, "main")
