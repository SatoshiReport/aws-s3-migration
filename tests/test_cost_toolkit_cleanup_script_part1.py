"""Comprehensive tests for aws_cleanup_script.py - Part 1."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.common.lightsail_utils import UnknownBundleError
from cost_toolkit.scripts.cleanup.aws_cleanup_script import (
    _stop_instance,
    disable_global_accelerators,
    estimate_database_cost,
    estimate_instance_cost,
)


@patch("cost_toolkit.scripts.cleanup.aws_cleanup_script.aws_utils.setup_aws_credentials")
def test_setup_credentials_success(mock_setup):
    """disable_global_accelerators should load shared credentials."""
    with patch("boto3.client") as mock_client:
        mock_ga = MagicMock()
        mock_ga.list_accelerators.return_value = {"Accelerators": []}
        mock_client.return_value = mock_ga
        disable_global_accelerators()
    mock_setup.assert_called_once()


class TestEstimateInstanceCost:
    """Tests for estimate_instance_cost function."""

    def test_estimate_cost_known_bundle(self):
        """Test cost estimation for known bundles."""
        assert estimate_instance_cost("nano_2_0") == 3.5
        assert estimate_instance_cost("micro_2_0") == 5.0
        assert estimate_instance_cost("small_2_0") == 10.0
        assert estimate_instance_cost("medium_2_0") == 20.0
        assert estimate_instance_cost("large_2_0") == 40.0
        assert estimate_instance_cost("xlarge_2_0") == 80.0
        assert estimate_instance_cost("2xlarge_2_0") == 160.0

    def test_estimate_cost_unknown_bundle(self):
        """Unknown bundles should raise to avoid silent underestimation."""
        with pytest.raises(UnknownBundleError):
            estimate_instance_cost("unknown_bundle")

    def test_estimate_cost_none(self):
        """None bundle should also raise to force explicit handling."""
        with pytest.raises(UnknownBundleError):
            estimate_instance_cost(None)  # type: ignore[arg-type]


class TestEstimateDatabaseCost:
    """Tests for estimate_database_cost function."""

    def test_estimate_cost_known_bundle(self):
        """Test cost estimation for known database bundles."""
        assert estimate_database_cost("micro_1_0") == 15.0
        assert estimate_database_cost("small_1_0") == 30.0
        assert estimate_database_cost("medium_1_0") == 60.0
        assert estimate_database_cost("large_1_0") == 115.0

    def test_estimate_cost_unknown_bundle(self):
        """Unknown bundles should raise to avoid silent underestimation."""
        with pytest.raises(UnknownBundleError):
            estimate_database_cost("unknown_db_bundle")

    def test_estimate_cost_none(self):
        """None bundle should also raise to force explicit handling."""
        with pytest.raises(UnknownBundleError):
            estimate_database_cost(None)  # type: ignore[arg-type]


def test_disable_global_accelerators_none_found(capsys):
    """Test when no accelerators found."""
    with patch("cost_toolkit.scripts.cleanup.aws_cleanup_script.aws_utils.setup_aws_credentials"):
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_accelerators.return_value = {"Accelerators": []}
            mock_client.return_value = mock_ga
            disable_global_accelerators()
    captured = capsys.readouterr()
    assert "No Global Accelerators found" in captured.out


def test_disable_global_accelerators_handles_deployed(capsys):
    """Test disabling deployed accelerator."""
    mock_accelerator = {
        "AcceleratorArn": "arn:aws:globalaccelerator::123:accelerator/abc",
        "Name": "test-accelerator",
        "Status": "DEPLOYED",
        "Enabled": True,
    }
    with patch("cost_toolkit.scripts.cleanup.aws_cleanup_script.aws_utils.setup_aws_credentials"):
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_accelerators.return_value = {"Accelerators": [mock_accelerator]}
            # Mock describe_accelerator to simulate state transition or stability
            mock_ga.describe_accelerator.side_effect = [
                {"Accelerator": {"Status": "DEPLOYED", "Enabled": True}},  # Initial check
                {"Accelerator": {"Status": "IN_PROGRESS", "Enabled": False}},  # After update
                {"Accelerator": {"Status": "DEPLOYED", "Enabled": False}},  # Final stable state
            ]
            mock_client.return_value = mock_ga

            # Patch the wait event to avoid sleeping
            with patch("cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup._WAIT_EVENT") as mock_event:
                disable_global_accelerators()
                assert mock_event.wait.call_count > 0

    mock_ga.update_accelerator.assert_called_once()
    captured = capsys.readouterr()
    assert "Accelerator is disabled" in captured.out


def test_disable_global_accelerators_skips_in_progress(capsys):
    """Test skipping accelerator already being modified."""
    mock_accelerator = {
        "AcceleratorArn": "arn:aws:globalaccelerator::123:accelerator/abc",
        "Name": "test-accelerator",
        "Status": "IN_PROGRESS",
        "Enabled": False,
    }
    with patch("cost_toolkit.scripts.cleanup.aws_cleanup_script.aws_utils.setup_aws_credentials"):
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_accelerators.return_value = {"Accelerators": [mock_accelerator]}
            # Return DEPLOYED/False so disable_accelerator loop exits immediately
            mock_ga.describe_accelerator.return_value = {"Accelerator": {"Status": "DEPLOYED", "Enabled": False}}
            mock_client.return_value = mock_ga

            # Patch wait event just in case
            with patch("cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup._WAIT_EVENT"):
                disable_global_accelerators()

    mock_ga.update_accelerator.assert_not_called()
    captured = capsys.readouterr()
    assert "Accelerator is disabled" in captured.out


def test_disable_global_accelerators_skips_disabled(capsys):
    """Test when accelerator is already disabled."""
    mock_accelerator = {
        "AcceleratorArn": "arn:aws:globalaccelerator::123:accelerator/abc",
        "Name": "test-accelerator",
        "Status": "DEPLOYED",
        "Enabled": False,
    }
    with patch("cost_toolkit.scripts.cleanup.aws_cleanup_script.aws_utils.setup_aws_credentials"):
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_accelerators.return_value = {"Accelerators": [mock_accelerator]}
            # Describe call returns stable state
            mock_ga.describe_accelerator.return_value = {"Accelerator": {"Status": "DEPLOYED", "Enabled": False}}
            mock_client.return_value = mock_ga

            with patch("cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup._WAIT_EVENT"):
                disable_global_accelerators()

    mock_ga.update_accelerator.assert_not_called()
    captured = capsys.readouterr()
    assert "already disabled" in captured.out


def test_disable_global_accelerators_handles_update_error(capsys):
    """Test error when disabling accelerator."""
    mock_accelerator = {
        "AcceleratorArn": "arn:aws:globalaccelerator::123:accelerator/abc",
        "Name": "test-accelerator",
        "Status": "DEPLOYED",
    }
    with patch("cost_toolkit.scripts.cleanup.aws_cleanup_script.aws_utils.setup_aws_credentials"):
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_accelerators.return_value = {"Accelerators": [mock_accelerator]}
            mock_ga.update_accelerator.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "update_accelerator")
            mock_client.return_value = mock_ga
            disable_global_accelerators()
    captured = capsys.readouterr()
    assert "Error disabling accelerator" in captured.out


def test_disable_global_accelerators_handles_client_error(capsys):
    """Test error accessing Global Accelerator service."""
    with patch("cost_toolkit.scripts.cleanup.aws_cleanup_script.aws_utils.setup_aws_credentials"):
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_accelerators.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "list_accelerators")
            mock_client.return_value = mock_ga
            disable_global_accelerators()
    captured = capsys.readouterr()
    assert "Error listing accelerators" in captured.out


class TestStopInstance:
    """Tests for _stop_instance function."""

    def test_stop_instance_success(self, capsys):
        """Test successful instance stop."""
        mock_client = MagicMock()
        instance = {"name": "test-instance", "state": {"name": "running"}, "bundleId": "nano_2_0"}
        stopped, cost = _stop_instance(mock_client, instance)
        assert stopped == 1
        assert cost == 3.5
        mock_client.stop_instance.assert_called_once_with(instanceName="test-instance")
        captured = capsys.readouterr()
        assert "Stopped instance" in captured.out

    def test_stop_instance_already_stopped(self, capsys):
        """Test instance already stopped."""
        mock_client = MagicMock()
        instance = {"name": "test-instance", "state": {"name": "stopped"}, "bundleId": "nano_2_0"}
        stopped, cost = _stop_instance(mock_client, instance)
        assert stopped == 0
        assert cost == 0.0
        mock_client.stop_instance.assert_not_called()
        captured = capsys.readouterr()
        assert "already stopped" in captured.out

    def test_stop_instance_error(self, capsys):
        """Test error stopping instance."""
        mock_client = MagicMock()
        mock_client.stop_instance.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "stop_instance")
        instance = {"name": "test-instance", "state": {"name": "running"}, "bundleId": "nano_2_0"}
        stopped, cost = _stop_instance(mock_client, instance)
        assert stopped == 0
        assert cost == 0.0
        captured = capsys.readouterr()
        assert "Error stopping instance" in captured.out

    def test_stop_instance_no_bundle_id(self, capsys):
        """Test stopping instance without bundle ID."""
        mock_client = MagicMock()
        instance = {"name": "test-instance", "state": {"name": "running"}}
        stopped, cost = _stop_instance(mock_client, instance)
        assert stopped == 1
        assert cost == 0.0
        captured = capsys.readouterr()
        assert "Stopped instance" in captured.out
