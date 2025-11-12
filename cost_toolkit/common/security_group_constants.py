"""
Shared security group constants for cleanup and audit scripts.
Contains hardcoded security group data for groups identified with circular dependencies
or deletion failures.
"""

# Security groups in us-east-2 with circular dependencies
US_EAST_2_CIRCULAR_SECURITY_GROUPS = [
    {
        "group_id": "sg-09e291dc61da97af1",
        "name": "security-group-for-outbound-nfs-d-ki8zr9k0yt95",
        "region": "us-east-2",
    },
    {
        "group_id": "sg-0dba11de0f5b92f40",
        "name": "security-group-for-inbound-nfs-d-ki8zr9k0yt95",
        "region": "us-east-2",
    },
]

# Security groups in us-east-1 with circular dependencies
US_EAST_1_CIRCULAR_SECURITY_GROUPS = [
    {
        "group_id": "sg-0423403672ae41d94",
        "name": "security-group-for-outbound-nfs-d-jbqwgqwiy4df",
        "region": "us-east-1",
    },
    {
        "group_id": "sg-0dfa7bedc21d91798",
        "name": "security-group-for-inbound-nfs-d-jbqwgqwiy4df",
        "region": "us-east-1",
    },
    {
        "group_id": "sg-049977ce080d9ab0f",
        "name": "security-group-for-inbound-nfs-d-ujcvqjdoyu70",
        "region": "us-east-1",
    },
    {
        "group_id": "sg-05ec40d14e0fb6fed",
        "name": "security-group-for-outbound-nfs-d-ujcvqjdoyu70",
        "region": "us-east-1",
    },
    {"group_id": "sg-0bf8a0d06a121f4a0", "name": "rds-ec2-1", "region": "us-east-1"},
    {"group_id": "sg-044777fbbcdee8f28", "name": "ec2-rds-1", "region": "us-east-1"},
]

# Combined list of all security groups with circular dependencies
ALL_CIRCULAR_SECURITY_GROUPS = (
    US_EAST_1_CIRCULAR_SECURITY_GROUPS + US_EAST_2_CIRCULAR_SECURITY_GROUPS
)
