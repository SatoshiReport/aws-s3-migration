"""Tests for the waiter helper wrappers."""

from __future__ import annotations

from unittest.mock import MagicMock

from cost_toolkit.common import waiter_utils


def test_wait_ami_available():
    """Ensure wait_ami_available requests the correct waiter and arguments."""
    client = MagicMock()
    waiter = MagicMock()
    client.get_waiter.return_value = waiter

    waiter_utils.wait_ami_available(client, "ami-123")

    client.get_waiter.assert_called_once_with("image_available")
    waiter.wait.assert_called_once_with(ImageIds=["ami-123"], WaiterConfig={"Delay": 15, "MaxAttempts": 40})
