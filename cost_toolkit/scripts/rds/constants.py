#!/usr/bin/env python3
"""Shared constants and utilities for RDS scripts."""

from botocore.exceptions import ClientError

# Public subnets in us-east-1 (ones with internet gateway routes)
PUBLIC_SUBNETS = [
    "subnet-2b441e6d",  # us-east-1d
    "subnet-34dd5c38",  # us-east-1f
    "subnet-3ce78006",  # us-east-1e
    "subnet-2755cf42",  # us-east-1a
    "subnet-98bf86ec",  # us-east-1c
    "subnet-5edaa076",  # us-east-1b
]


DEFAULT_SUBNET_GROUP_DESCRIPTION = "Public subnets only for RDS internet access"


def create_public_subnet_group(
    rds, subnet_group_name, description: str = DEFAULT_SUBNET_GROUP_DESCRIPTION
):
    """Create a new DB subnet group with public subnets.

    Args:
        rds: boto3 RDS client
        subnet_group_name: Name for the subnet group
        description: Description for the subnet group

    Returns:
        None

    Raises:
        ClientError: If creation fails for reasons other than already existing
    """

    print(f"🌐 Creating public subnet group: {subnet_group_name}")

    try:
        rds.create_db_subnet_group(
            DBSubnetGroupName=subnet_group_name,
            DBSubnetGroupDescription=description,
            SubnetIds=PUBLIC_SUBNETS,
            Tags=[{"Key": "Purpose", "Value": "Public RDS access"}],
        )
        print(f"✅ Created new subnet group: {subnet_group_name}")
    except ClientError as e:
        if "already exists" in str(e).lower():
            print(f"✅ Subnet group {subnet_group_name} already exists")
        else:
            raise


if __name__ == "__main__":
    pass
