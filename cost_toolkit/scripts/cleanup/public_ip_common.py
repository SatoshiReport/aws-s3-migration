"""Shared helpers for public IP removal workflows."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Callable

from cost_toolkit.scripts.aws_utils import get_instance_info, wait_for_instance_state

_WAIT_EVENT = Event()


@dataclass
class InstanceNetworkContext:
    """Normalized network context for an EC2 instance."""

    instance: dict
    state: str
    public_ip: str | None
    current_eni_id: str | None
    current_eni: dict
    vpc_id: str | None
    subnet_id: str | None
    security_groups: list[str]


def fetch_instance_network_details(
    instance_id: str, region_name: str, *, instance_fetcher: Callable = get_instance_info
) -> InstanceNetworkContext:
    """Fetch core network context for an instance to drive public-IP removal flows."""
    instance = instance_fetcher(instance_id, region_name)
    network_interfaces = instance.get("NetworkInterfaces") or []
    primary_interface = network_interfaces[0] if network_interfaces else {}
    interface_id = primary_interface.get("NetworkInterfaceId")
    return InstanceNetworkContext(
        instance=instance,
        state=instance["State"]["Name"],
        public_ip=instance.get("PublicIpAddress"),
        current_eni_id=interface_id,
        current_eni=primary_interface,
        vpc_id=instance.get("VpcId"),
        subnet_id=instance.get("SubnetId"),
        security_groups=[sg["GroupId"] for sg in instance.get("SecurityGroups", [])],
    )


def wait_for_state(ec2, instance_id: str, waiter_name: str) -> None:
    """Wait for an instance to reach a given state."""
    wait_for_instance_state(ec2, instance_id, waiter_name)


def delay(seconds: int):
    """Interruptible wait helper."""
    _WAIT_EVENT.wait(seconds)
