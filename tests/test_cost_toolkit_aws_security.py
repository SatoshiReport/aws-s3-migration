"""Tests for cost_toolkit/scripts/aws_security.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_security import delete_security_group


def test_delete_security_group_with_client_object():
    """When provided an EC2 client, delete_security_group should use it directly."""
    client = MagicMock()

    result = delete_security_group(region_or_client=client, group_id="sg-123", group_name="test")

    assert result is True
    client.delete_security_group.assert_called_once_with(GroupId="sg-123")


@patch("cost_toolkit.scripts.aws_security.create_ec2_client")
def test_delete_security_group_handles_client_error(mock_client_factory):
    """ClientError should be caught and return False."""
    failing_client = MagicMock()
    failing_client.delete_security_group.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedOperation"}},
        "DeleteSecurityGroup",
    )
    mock_client_factory.return_value = failing_client

    result = delete_security_group(region="us-west-1", group_id="sg-err")

    assert result is False
    mock_client_factory.assert_called_once_with(
        region="us-west-1", aws_access_key_id=None, aws_secret_access_key=None
    )


def test_delete_security_group_requires_group_id():
    """Missing group_id should raise ValueError."""
    with pytest.raises(ValueError):
        delete_security_group(region="us-east-1")
