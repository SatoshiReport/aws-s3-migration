#!/usr/bin/env python3
import os
import sys

import boto3

SCRIPT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPT_ROOT not in sys.path:
    sys.path.append(SCRIPT_ROOT)

from aws_utils import setup_aws_credentials


def fix_default_subnet_group():
    """Modify the default subnet group to only include public subnets"""

    setup_aws_credentials()
    rds = boto3.client("rds", region_name="us-east-1")
    ec2 = boto3.client("ec2", region_name="us-east-1")

    print("🔧 Fixing default subnet group to only include public subnets...")

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
        subnet_group_name = "public-rds-subnets"

        print(f"🌐 Creating new public subnet group: {subnet_group_name}")

        try:
            rds.create_db_subnet_group(
                DBSubnetGroupName=subnet_group_name,
                DBSubnetGroupDescription="Public subnets only for RDS internet access",
                SubnetIds=public_subnets,
                Tags=[{"Key": "Purpose", "Value": "Public RDS access"}],
            )
            print(f"✅ Created new subnet group: {subnet_group_name}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"✅ Subnet group {subnet_group_name} already exists")
            else:
                raise

        # Since we can't modify the subnet group directly, let's try a different approach
        # We'll create a snapshot and restore to a new instance in the public subnet group
        print(f"🔄 Creating snapshot for subnet group migration...")

        snapshot_id = "simba-db-public-migration-snapshot"

        try:
            rds.create_db_snapshot(
                DBSnapshotIdentifier=snapshot_id, DBInstanceIdentifier="simba-db-restored"
            )
            print(f"✅ Snapshot creation initiated: {snapshot_id}")

            # Wait for snapshot to complete
            print(f"⏳ Waiting for snapshot to complete...")
            waiter = rds.get_waiter("db_snapshot_completed")
            waiter.wait(
                DBSnapshotIdentifier=snapshot_id, WaiterConfig={"Delay": 30, "MaxAttempts": 20}
            )
            print(f"✅ Snapshot completed!")

            # Restore to new instance in public subnet group
            new_instance_id = "simba-db-public"
            print(f"🔄 Restoring to new instance in public subnets: {new_instance_id}")

            rds.restore_db_instance_from_db_snapshot(
                DBInstanceIdentifier=new_instance_id,
                DBSnapshotIdentifier=snapshot_id,
                DBInstanceClass="db.t4g.micro",
                DBSubnetGroupName=subnet_group_name,
                PubliclyAccessible=True,
                VpcSecurityGroupIds=["sg-265aa043"],  # Use the same security group
            )

            print(f"✅ New instance restoration initiated!")
            print(f"⏳ Waiting for new instance to be available...")

            # Wait for new instance to be available
            waiter = rds.get_waiter("db_instance_available")
            waiter.wait(
                DBInstanceIdentifier=new_instance_id, WaiterConfig={"Delay": 30, "MaxAttempts": 20}
            )

            print(f"✅ New instance is available in public subnets!")
            print(f"🔍 You can now connect to: {new_instance_id}")
            print(f"💡 After confirming connectivity, you can delete the old instance")

        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"✅ Snapshot {snapshot_id} already exists, proceeding...")
            else:
                raise

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    fix_default_subnet_group()
