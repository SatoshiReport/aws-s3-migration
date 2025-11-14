"""Batch tests for cost_toolkit optimization scripts."""

from __future__ import annotations

from cost_toolkit.scripts.optimization import (
    aws_export_recovery,
    aws_s3_to_snapshot_restore,
    aws_snapshot_to_s3_semi_manual,
    monitor_manual_exports,
    snapshot_export_common,
)
from cost_toolkit.scripts.optimization.snapshot_export_fixed import (
    cli,
    monitoring,
    recovery,
)


class TestExportRecovery:
    """Tests for aws_export_recovery.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_export_recovery is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_export_recovery, "main")


class TestS3ToSnapshotRestore:
    """Tests for aws_s3_to_snapshot_restore.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_s3_to_snapshot_restore is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_s3_to_snapshot_restore, "main")


class TestSnapshotToS3SemiManual:
    """Tests for aws_snapshot_to_s3_semi_manual.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_snapshot_to_s3_semi_manual is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(aws_snapshot_to_s3_semi_manual, "main")


class TestMonitorManualExports:
    """Tests for monitor_manual_exports.py."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert monitor_manual_exports is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert hasattr(monitor_manual_exports, "main")


class TestSnapshotExportModules:
    """Tests for snapshot_export modules."""

    def test_snapshot_export_common_imports(self):
        """Test snapshot_export_common module can be imported."""
        assert snapshot_export_common is not None

    def test_snapshot_export_fixed_cli_imports(self):
        """Test snapshot_export_fixed/cli module can be imported."""
        assert cli is not None

    def test_snapshot_export_fixed_cli_main_exists(self):
        """Test snapshot_export_fixed/cli has main function."""
        assert hasattr(cli, "main")

    def test_snapshot_export_fixed_monitoring_imports(self):
        """Test snapshot_export_fixed/monitoring module can be imported."""
        assert monitoring is not None

    def test_snapshot_export_fixed_recovery_imports(self):
        """Test snapshot_export_fixed/recovery module can be imported."""
        assert recovery is not None
