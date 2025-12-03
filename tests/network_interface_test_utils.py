"""Shared helpers for network interface audit tests."""

from __future__ import annotations

_BASE_ATTACHED_INTERFACES = (
    {
        "interface_id": "eni-1",
        "name": "interface-1",
        "type": "interface",
        "attached_to": "i-1",
        "status": "in-use",
        "vpc_id": "vpc-1",
        "private_ip": "10.0.0.1",
        "public_ip": "1.1.1.1",
    },
    {
        "interface_id": "eni-2",
        "name": "interface-2",
        "type": "interface",
        "attached_to": None,
        "status": "available",
        "vpc_id": "vpc-1",
        "private_ip": "10.0.0.2",
        "public_ip": None,
    },
)


def build_attached_interfaces(overrides=None):
    """Return a fresh list of attached interface dictionaries with optional overrides."""
    interfaces = [dict(item) for item in _BASE_ATTACHED_INTERFACES]
    if overrides:
        for index, update in overrides.items():
            interfaces[index].update(update)
    return interfaces
