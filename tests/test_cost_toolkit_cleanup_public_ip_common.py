"""Tests for public_ip_common helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from cost_toolkit.scripts.cleanup.public_ip_common import fetch_instance_network_details


def test_fetch_instance_network_details():
    """Ensure network context is normalized."""
    instance = {
        "State": {"Name": "running"},
        "PublicIpAddress": "1.2.3.4",
        "NetworkInterfaces": [{"NetworkInterfaceId": "eni-123", "Attachment": {"AttachmentId": "a-1"}}],
        "VpcId": "vpc-1",
        "SubnetId": "subnet-1",
        "SecurityGroups": [{"GroupId": "sg-1"}, {"GroupId": "sg-2"}],
    }
    fetcher = MagicMock(return_value=instance)

    context = fetch_instance_network_details("i-1", "us-east-1", instance_fetcher=fetcher)

    assert context.state == "running"
    assert context.public_ip == "1.2.3.4"
    assert context.current_eni_id == "eni-123"
    assert context.security_groups == ["sg-1", "sg-2"]
