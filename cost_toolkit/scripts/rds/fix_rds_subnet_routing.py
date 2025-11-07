#!/usr/bin/env python3
import os
import sys

import boto3

SCRIPT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPT_ROOT not in sys.path:
    sys.path.append(SCRIPT_ROOT)

from aws_utils import setup_aws_credentials


def fix_rds_subnet_routing():
    """Move RDS instance to public subnets only"""

    setup_aws_credentials()
    rds = boto3.client("rds", region_name="us-east-1")
    ec2 = boto3.client("ec2", region_name="us-east-1")

    print("🔧 Fixing RDS subnet routing for internet access...")

    # Public subnets (ones with internet gateway routes)
    public_subnets = [
        "subnet-2b441e6d",  # us-east-1d
        "subnet-34dd5c38",  # us-east-1f
        "subnet-3ce78006",  # us-east-1e
        "subnet-2755cf42",  # us-east-1a
        "subnet-98bf86ec",  # us-east-1c
        "subnet-5edaa076",  # us-east-1b
    ]

    try:
        # Create a new DB subnet group with only public subnets
        subnet_group_name = "public-subnet-group"

        print(f"🌐 Creating public subnet group: {subnet_group_name}")

        try:
            rds.create_db_subnet_group(
                DBSubnetGroupName=subnet_group_name,
                DBSubnetGroupDescription="Public subnets only for internet access",
                SubnetIds=public_subnets,
                Tags=[{"Key": "Purpose", "Value": "Public RDS access"}],
            )
            print(f"✅ Created new subnet group: {subnet_group_name}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"✅ Subnet group {subnet_group_name} already exists")
            else:
                raise e

        # Modify the RDS instance to use the new subnet group
        print(f"🔄 Moving RDS instance to public subnet group...")

        rds.modify_db_instance(
            DBInstanceIdentifier="simba-db-restored",
            DBSubnetGroupName=subnet_group_name,
            ApplyImmediately=True,
        )

        print(f"✅ RDS instance modification initiated!")
        print(f"⏳ Waiting for modification to complete...")
        print(f"   This may take 5-10 minutes...")

        # Wait for the modification to complete
        waiter = rds.get_waiter("db_instance_available")
        waiter.wait(
            DBInstanceIdentifier="simba-db-restored", WaiterConfig={"Delay": 30, "MaxAttempts": 20}
        )

        print(f"✅ RDS instance is now in public subnets!")
        print(f"🔍 You should now be able to connect from the internet")

    except Exception as e:
        print(f"❌ Error fixing subnet routing: {e}")


if __name__ == "__main__":
    fix_rds_subnet_routing()
