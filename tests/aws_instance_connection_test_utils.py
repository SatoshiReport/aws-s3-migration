"""Helpers for aws_instance_connection_info tests."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.audit import aws_instance_connection_info


def build_instance_connection_mocks():
    """Return instance details and mock EC2/SSM clients."""
    mock_instance = {"InstanceId": "i-123", "SecurityGroups": []}

    mock_ec2 = MagicMock()
    mock_ec2.describe_subnets.return_value = {"Subnets": [{}]}
    mock_ec2.describe_route_tables.return_value = {"RouteTables": []}

    mock_ssm = MagicMock()
    mock_ssm.describe_instance_information.return_value = {"InstanceInformationList": []}

    return mock_instance, mock_ec2, mock_ssm


def run_connection_info_with_clients(mock_instance, mock_ec2, mock_ssm, instance_id, region):
    """Invoke get_instance_connection_info with supplied clients wired via boto3 patch."""
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                aws_instance_connection_info,
                "get_instance_info",
                return_value=mock_instance,
            )
        )
        stack.enter_context(patch("boto3.client", side_effect=[mock_ec2, mock_ssm]))
        return aws_instance_connection_info.get_instance_connection_info(instance_id, region)
