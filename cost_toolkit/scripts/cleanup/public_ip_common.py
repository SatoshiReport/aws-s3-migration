"""Shared helpers for public IP removal workflows."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Callable

from cost_toolkit.scripts.aws_utils import get_instance_info, wait_for_instance_state

_WAIT_EVENT = Event()


@dataclass
class InstanceNetworkContext:  # pylint: disable=too-many-instance-attributes
    """Normalized network context for an EC2 instance."""

    instance: dict
    state: str
    public_ip: str | None
    current_eni_id: str | None
    current_eni: dict
    vpc_id: str | None
    subnet_id: str | None
    security_groups: list[str]


class MissingNetworkInterfacesError(KeyError):
    """Raised when an instance has no network interfaces."""


class MissingInstanceStateError(KeyError):
    """Raised when an instance response is missing required fields."""


def fetch_instance_network_details(
    instance_id: str, region_name: str, *, instance_fetcher: Callable = get_instance_info
) -> InstanceNetworkContext:
    """Fetch core network context for an instance to drive public-IP removal flows.

    Raises:
        ValueError: If instance_id or region_name is empty.
        MissingInstanceStateError: If the instance response is missing State.
        MissingNetworkInterfacesError: If the instance has no network interfaces.
    """
    if not instance_id:
        raise ValueError("instance_id is required")
    if not region_name:
        raise ValueError("region_name is required")

    instance = instance_fetcher(instance_id, region_name)

    if "State" not in instance or "Name" not in instance["State"]:
        raise MissingInstanceStateError(f"Instance {instance_id} response missing State.Name")

    if "NetworkInterfaces" not in instance:
        raise MissingNetworkInterfacesError(
            f"Instance {instance_id} response missing NetworkInterfaces"
        )

    network_interfaces = instance["NetworkInterfaces"]
    if not network_interfaces:
        raise MissingNetworkInterfacesError(f"Instance {instance_id} has no network interfaces")

    primary_interface = network_interfaces[0]

    if "NetworkInterfaceId" not in primary_interface:
        raise MissingNetworkInterfacesError(
            f"Instance {instance_id} primary interface missing NetworkInterfaceId"
        )

    if "SecurityGroups" not in instance:
        raise MissingInstanceStateError(f"Instance {instance_id} response missing SecurityGroups")

    return InstanceNetworkContext(
        instance=instance,
        state=instance["State"]["Name"],
        public_ip=instance.get("PublicIpAddress"),
        current_eni_id=primary_interface["NetworkInterfaceId"],
        current_eni=primary_interface,
        vpc_id=instance.get("VpcId"),
        subnet_id=instance.get("SubnetId"),
        security_groups=[sg["GroupId"] for sg in instance["SecurityGroups"]],
    )


def wait_for_state(ec2, instance_id: str, waiter_name: str) -> None:
    """Wait for an instance to reach a given state."""
    wait_for_instance_state(ec2, instance_id, waiter_name)


def delay(seconds: int):
    """Interruptible wait helper."""
    _WAIT_EVENT.wait(seconds)
