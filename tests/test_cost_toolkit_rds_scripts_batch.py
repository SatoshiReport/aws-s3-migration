"""Batch tests for cost_toolkit RDS scripts."""

from __future__ import annotations

from cost_toolkit.scripts.rds import (
    constants,
    db_inspection_common,
    enable_rds_public_access,
    explore_aurora_data,
    explore_user_data,
    fix_default_subnet_group,
    fix_rds_subnet_routing,
    update_rds_security_group,
)


def test_rds_constants_module_imports():
    """Test rds/constants.py module can be imported."""
    assert constants is not None


def test_db_inspection_common_module_imports():
    """Test rds/db_inspection_common.py module can be imported."""
    assert db_inspection_common is not None


class TestEnableRdsPublicAccess:
    """Tests for enable_rds_public_access.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert enable_rds_public_access is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(enable_rds_public_access, "main")


class TestExploreAuroraData:
    """Tests for explore_aurora_data.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert explore_aurora_data is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(explore_aurora_data, "main")


class TestExploreUserData:
    """Tests for explore_user_data.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert explore_user_data is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(explore_user_data, "main")


class TestFixDefaultSubnetGroup:
    """Tests for fix_default_subnet_group.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert fix_default_subnet_group is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(fix_default_subnet_group, "main")


class TestFixRdsSubnetRouting:
    """Tests for fix_rds_subnet_routing.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert fix_rds_subnet_routing is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(fix_rds_subnet_routing, "main")


class TestUpdateRdsSecurityGroup:
    """Tests for update_rds_security_group.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert update_rds_security_group is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(update_rds_security_group, "main")
