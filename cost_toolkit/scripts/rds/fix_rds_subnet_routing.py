#!/usr/bin/env python3
"""Fix RDS subnet routing configuration."""


import boto3
from botocore.exceptions import ClientError

from ..aws_utils import setup_aws_credentials
from .constants import create_public_subnet_group


def fix_rds_subnet_routing():
    """Move RDS instance to public subnets only"""

    setup_aws_credentials()
    rds = boto3.client("rds", region_name="us-east-1")

    print("🔧 Fixing RDS subnet routing for internet access...")

    try:
        # Create a new DB subnet group with only public subnets
        subnet_group_name = "public-subnet-group"
        create_public_subnet_group(
            rds, subnet_group_name, "Public subnets only for internet access"
        )

        # Modify the RDS instance to use the new subnet group
        print("🔄 Moving RDS instance to public subnet group...")

        rds.modify_db_instance(
            DBInstanceIdentifier="simba-db-restored",
            DBSubnetGroupName=subnet_group_name,
            ApplyImmediately=True,
        )

        print("✅ RDS instance modification initiated!")
        print("⏳ Waiting for modification to complete...")
        print("   This may take 5-10 minutes...")

        # Wait for the modification to complete
        waiter = rds.get_waiter("db_instance_available")
        waiter.wait(
            DBInstanceIdentifier="simba-db-restored", WaiterConfig={"Delay": 30, "MaxAttempts": 20}
        )

        print("✅ RDS instance is now in public subnets!")
        print("🔍 You should now be able to connect from the internet")

    except ClientError as e:
        print(f"❌ Error fixing subnet routing: {e}")


def main():
    """Main function."""
    fix_rds_subnet_routing()


if __name__ == "__main__":
    main()
