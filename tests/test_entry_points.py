"""Tests for CLI entry point modules."""


def test_cost_overview_imports():
    """Test that cost_overview module can be imported."""
    try:
        from cost_toolkit import cost_overview

        assert cost_overview is not None
    except ImportError as exc:
        raise AssertionError(f"Failed to import cost_overview: {exc}") from exc


def test_duplicate_tree_cli_exports_imports():
    """Test that duplicate_tree_cli_exports module can be imported."""
    try:
        import duplicate_tree_cli_exports

        assert duplicate_tree_cli_exports is not None
        assert hasattr(duplicate_tree_cli_exports, "__all__")
        assert "main" in duplicate_tree_cli_exports.__all__
    except ImportError as exc:
        raise AssertionError(f"Failed to import duplicate_tree_cli_exports: {exc}") from exc


def test_find_compressible_files_imports():
    """Test that find_compressible_files module can be imported."""
    try:
        import find_compressible_files

        assert find_compressible_files is not None
    except ImportError as exc:
        raise AssertionError(f"Failed to import find_compressible_files: {exc}") from exc


def test_aws_vmimport_role_setup_imports():
    """Test that aws_vmimport_role_setup module can be imported."""
    try:
        from cost_toolkit.scripts.setup import aws_vmimport_role_setup

        assert aws_vmimport_role_setup is not None
        assert hasattr(aws_vmimport_role_setup, "create_vmimport_role")
    except ImportError as exc:
        raise AssertionError(f"Failed to import aws_vmimport_role_setup: {exc}") from exc


def test_audit_scripts_import():
    """Test that audit CLI scripts can be imported."""
    try:
        from cost_toolkit.scripts.audit import (
            aws_ami_snapshot_analysis,
            aws_comprehensive_vpc_audit,
            aws_ebs_audit,
            aws_elastic_ip_audit,
            aws_kms_audit,
            aws_rds_audit,
            aws_s3_audit,
            aws_security_group_dependencies,
        )

        assert all(
            [
                aws_ami_snapshot_analysis,
                aws_comprehensive_vpc_audit,
                aws_ebs_audit,
                aws_elastic_ip_audit,
                aws_kms_audit,
                aws_rds_audit,
                aws_s3_audit,
                aws_security_group_dependencies,
            ]
        )
    except ImportError as exc:
        raise AssertionError(f"Failed to import audit scripts: {exc}") from exc


def test_billing_scripts_import():
    """Test that billing CLI scripts can be imported."""
    try:
        from cost_toolkit.scripts.billing import aws_billing_report

        assert aws_billing_report is not None
    except ImportError as exc:
        raise AssertionError(f"Failed to import billing scripts: {exc}") from exc


def test_management_scripts_import():
    """Test that management CLI scripts can be imported."""
    try:
        from cost_toolkit.scripts.management import (
            aws_ebs_volume_manager,
            aws_s3_standardization,
        )

        assert all([aws_ebs_volume_manager, aws_s3_standardization])
    except ImportError as exc:
        raise AssertionError(f"Failed to import management scripts: {exc}") from exc


def test_migration_scripts_import():
    """Test that migration CLI scripts can be imported."""
    try:
        from cost_toolkit.scripts.migration import (
            aws_check_instance_status,
            aws_ebs_to_s3_migration,
            aws_london_ebs_analysis,
            aws_london_ebs_cleanup,
            aws_london_final_analysis_summary,
            aws_london_final_status,
            aws_london_volume_inspector,
            aws_migration_monitor,
            aws_rds_to_aurora_serverless_migration,
            aws_start_and_migrate,
        )

        assert all(
            [
                aws_check_instance_status,
                aws_ebs_to_s3_migration,
                aws_london_ebs_analysis,
                aws_london_ebs_cleanup,
                aws_london_final_analysis_summary,
                aws_london_final_status,
                aws_london_volume_inspector,
                aws_migration_monitor,
                aws_rds_to_aurora_serverless_migration,
                aws_start_and_migrate,
            ]
        )
    except ImportError as exc:
        raise AssertionError(f"Failed to import migration scripts: {exc}") from exc


def test_optimization_scripts_import():
    """Test that optimization CLI scripts can be imported."""
    try:
        from cost_toolkit.scripts.optimization import (
            aws_s3_to_snapshot_restore,
            aws_snapshot_to_s3_export,
            aws_snapshot_to_s3_export_fixed,
            aws_snapshot_to_s3_export_robust,
        )

        assert all(
            [
                aws_s3_to_snapshot_restore,
                aws_snapshot_to_s3_export,
                aws_snapshot_to_s3_export_fixed,
                aws_snapshot_to_s3_export_robust,
            ]
        )
    except ImportError as exc:
        raise AssertionError(f"Failed to import optimization scripts: {exc}") from exc
