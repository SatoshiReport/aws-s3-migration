"""Shared helpers for security group-related tests."""

from __future__ import annotations


def sample_sg_with_reference(target_id: str = "sg-target"):
    """Return a security group referencing the provided target."""
    return {
        "GroupId": "sg-source",
        "GroupName": "source-sg",
        "IpPermissions": [
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "UserIdGroupPairs": [{"GroupId": target_id}],
            }
        ],
    }


def describe_response_with_reference(target_id: str = "sg-target"):
    """Return a describe_security_groups payload referencing the target."""
    return {
        "SecurityGroups": [
            {
                **sample_sg_with_reference(target_id),
                "IpPermissionsEgress": [],
            }
        ]
    }
