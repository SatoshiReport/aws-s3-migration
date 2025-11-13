"""Comprehensive tests for aws_global_accelerator_cleanup.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup import (
    delete_accelerator,
    delete_listeners,
    disable_accelerator,
    list_accelerators,
    print_cleanup_summary,
    process_single_accelerator,
)


class TestListAccelerators:
    """Tests for list_accelerators function."""

    def test_list_accelerators_success(self):
        """Test successful listing of accelerators."""
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_accelerators.return_value = {
                "Accelerators": [
                    {"AcceleratorArn": "arn:aws:globalaccelerator::123456789012:accelerator/abc123"}
                ]
            }
            mock_client.return_value = mock_ga

            result = list_accelerators()

            assert len(result) == 1
            assert (
                result[0]["AcceleratorArn"]
                == "arn:aws:globalaccelerator::123456789012:accelerator/abc123"
            )
            mock_client.assert_called_once_with("globalaccelerator", region_name="us-west-2")

    def test_list_accelerators_empty(self):
        """Test listing when no accelerators exist."""
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_accelerators.return_value = {"Accelerators": []}
            mock_client.return_value = mock_ga

            result = list_accelerators()

            assert result == []

    def test_list_accelerators_error(self, capsys):
        """Test error handling when listing fails."""
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_accelerators.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied"}}, "list_accelerators"
            )
            mock_client.return_value = mock_ga

            result = list_accelerators()

            assert result == []
            captured = capsys.readouterr()
            assert "Error listing accelerators" in captured.out


class TestDisableAccelerator:
    """Tests for disable_accelerator function."""

    def test_disable_enabled_accelerator(self, capsys):
        """Test disabling an enabled accelerator."""
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.describe_accelerator.side_effect = [
                {"Accelerator": {"Status": "DEPLOYED", "Enabled": True}},
                {"Accelerator": {"Status": "DEPLOYED", "Enabled": False}},
            ]
            mock_client.return_value = mock_ga

            result = disable_accelerator(
                "arn:aws:globalaccelerator::123456789012:accelerator/abc123"
            )

            assert result is True
            mock_ga.update_accelerator.assert_called_once()
            captured = capsys.readouterr()
            assert "Disabling accelerator" in captured.out

    def test_disable_already_disabled(self, capsys):
        """Test handling accelerator already disabled."""
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.describe_accelerator.side_effect = [
                {"Accelerator": {"Status": "DEPLOYED", "Enabled": False}},
                {"Accelerator": {"Status": "DEPLOYED", "Enabled": False}},
            ]
            mock_client.return_value = mock_ga

            result = disable_accelerator(
                "arn:aws:globalaccelerator::123456789012:accelerator/abc123"
            )

            assert result is True
            captured = capsys.readouterr()
            assert "already disabled" in captured.out

    def test_disable_timeout_waiting(self, capsys):
        """Test timeout when waiting for stable state."""
        with patch("boto3.client") as mock_client:
            with patch("time.sleep"):
                mock_ga = MagicMock()
                mock_ga.describe_accelerator.return_value = {
                    "Accelerator": {"Status": "IN_PROGRESS", "Enabled": False}
                }
                mock_client.return_value = mock_ga

                with patch(
                    "cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup.MAX_ACCELERATOR_WAIT_SECONDS",
                    1,
                ):
                    result = disable_accelerator(
                        "arn:aws:globalaccelerator::123456789012:accelerator/abc123"
                    )

                assert result is False
                captured = capsys.readouterr()
                assert "Timeout" in captured.out

    def test_disable_error(self, capsys):
        """Test error handling when disabling fails."""
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.describe_accelerator.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "describe_accelerator"
            )
            mock_client.return_value = mock_ga

            result = disable_accelerator(
                "arn:aws:globalaccelerator::123456789012:accelerator/abc123"
            )

            assert result is False
            captured = capsys.readouterr()
            assert "Error disabling accelerator" in captured.out


class TestDeleteListeners:
    """Tests for delete_listeners function."""

    def test_delete_listeners_with_endpoint_groups(self, capsys):
        """Test deleting listeners with endpoint groups."""
        with patch("boto3.client") as mock_client:
            with patch("time.sleep"):
                mock_ga = MagicMock()
                mock_ga.list_listeners.return_value = {
                    "Listeners": [{"ListenerArn": "arn:aws:listener/123"}]
                }
                mock_ga.list_endpoint_groups.return_value = {
                    "EndpointGroups": [{"EndpointGroupArn": "arn:aws:endpoint/456"}]
                }
                mock_client.return_value = mock_ga

                result = delete_listeners("arn:aws:accelerator/abc")

                assert result is True
                mock_ga.delete_endpoint_group.assert_called_once()
                mock_ga.delete_listener.assert_called_once()

    def test_delete_listeners_no_endpoint_groups(self, capsys):
        """Test deleting listeners without endpoint groups."""
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_listeners.return_value = {
                "Listeners": [{"ListenerArn": "arn:aws:listener/123"}]
            }
            mock_ga.list_endpoint_groups.return_value = {"EndpointGroups": []}
            mock_client.return_value = mock_ga

            result = delete_listeners("arn:aws:accelerator/abc")

            assert result is True
            mock_ga.delete_listener.assert_called_once()

    def test_delete_listeners_error(self, capsys):
        """Test error handling when deleting listeners fails."""
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_listeners.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "list_listeners"
            )
            mock_client.return_value = mock_ga

            result = delete_listeners("arn:aws:accelerator/abc")

            assert result is False
            captured = capsys.readouterr()
            assert "Error deleting listeners" in captured.out


class TestDeleteAccelerator:
    """Tests for delete_accelerator function."""

    def test_delete_accelerator_success(self, capsys):
        """Test successful accelerator deletion."""
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_client.return_value = mock_ga

            result = delete_accelerator("arn:aws:accelerator/abc")

            assert result is True
            mock_ga.delete_accelerator.assert_called_once_with(
                AcceleratorArn="arn:aws:accelerator/abc"
            )
            captured = capsys.readouterr()
            assert "deletion initiated" in captured.out

    def test_delete_accelerator_error(self, capsys):
        """Test error handling when deletion fails."""
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.delete_accelerator.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "delete_accelerator"
            )
            mock_client.return_value = mock_ga

            result = delete_accelerator("arn:aws:accelerator/abc")

            assert result is False
            captured = capsys.readouterr()
            assert "Error deleting accelerator" in captured.out


class TestProcessSingleAccelerator:
    """Tests for process_single_accelerator function."""

    def test_process_accelerator_success(self, capsys):
        """Test successful processing of single accelerator."""
        accelerator = {
            "AcceleratorArn": "arn:aws:accelerator/abc",
            "Name": "test-accelerator",
            "Status": "DEPLOYED",
            "Enabled": True,
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup.disable_accelerator",
            return_value=True,
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup.delete_listeners",
                return_value=True,
            ):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup.delete_accelerator",
                    return_value=True,
                ):
                    success, cost = process_single_accelerator(accelerator)

        assert success is True
        assert cost == 18.0
        captured = capsys.readouterr()
        assert "Successfully deleted" in captured.out

    def test_process_accelerator_disable_fails(self, capsys):
        """Test when disabling accelerator fails."""
        accelerator = {
            "AcceleratorArn": "arn:aws:accelerator/abc",
            "Name": "test-accelerator",
            "Status": "DEPLOYED",
            "Enabled": True,
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup.disable_accelerator",
            return_value=False,
        ):
            success, cost = process_single_accelerator(accelerator)

        assert success is False
        assert cost == 18.0

    def test_process_accelerator_delete_listeners_fails(self, capsys):
        """Test when deleting listeners fails."""
        accelerator = {
            "AcceleratorArn": "arn:aws:accelerator/abc",
            "Name": "test-accelerator",
            "Status": "DEPLOYED",
            "Enabled": True,
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup.disable_accelerator",
            return_value=True,
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup.delete_listeners",
                return_value=False,
            ):
                success, cost = process_single_accelerator(accelerator)

        assert success is False

    def test_process_accelerator_unnamed(self, capsys):
        """Test processing accelerator without name."""
        accelerator = {
            "AcceleratorArn": "arn:aws:accelerator/abc",
            "Status": "DEPLOYED",
            "Enabled": False,
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup.disable_accelerator",
            return_value=True,
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup.delete_listeners",
                return_value=True,
            ):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_global_accelerator_cleanup.delete_accelerator",
                    return_value=True,
                ):
                    success, cost = process_single_accelerator(accelerator)

        captured = capsys.readouterr()
        assert "Unnamed" in captured.out


class TestPrintCleanupSummary:
    """Tests for print_cleanup_summary function."""

    def test_print_summary_with_deletions(self, capsys):
        """Test summary with successful deletions."""
        print_cleanup_summary(5, 4, 72.0)

        captured = capsys.readouterr()
        assert "CLEANUP SUMMARY" in captured.out
        assert "Total accelerators processed: 5" in captured.out
        assert "Successfully deleted: 4" in captured.out
        assert "$72.00" in captured.out
        assert "IMPORTANT NOTES" in captured.out

    def test_print_summary_no_deletions(self, capsys):
        """Test summary with no deletions."""
        print_cleanup_summary(2, 0, 0.0)

        captured = capsys.readouterr()
        assert "CLEANUP SUMMARY" in captured.out
        assert "No accelerators were successfully deleted" in captured.out

    def test_print_summary_partial_success(self, capsys):
        """Test summary with partial success."""
        print_cleanup_summary(3, 2, 36.0)

        captured = capsys.readouterr()
        assert "Total accelerators processed: 3" in captured.out
        assert "Successfully deleted: 2" in captured.out
        assert "$36.00" in captured.out
