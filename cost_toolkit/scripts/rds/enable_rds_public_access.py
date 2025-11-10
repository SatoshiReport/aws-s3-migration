#!/usr/bin/env python3
"""Enable public accessibility for RDS database instances."""

import boto3
from botocore.exceptions import ClientError

from ..aws_utils import setup_aws_credentials


def enable_public_access():
    """Temporarily enable public access to the restored RDS instance"""

    setup_aws_credentials()
    rds = boto3.client("rds", region_name="us-east-1")

    print("🔧 Enabling public access to restored RDS instance...")
    print("⚠️  This is temporary - we'll disable it after data migration")

    try:
        # Modify the instance to be publicly accessible
        _ = rds.modify_db_instance(
            DBInstanceIdentifier="simba-db-restored", PubliclyAccessible=True, ApplyImmediately=True
        )

        print("✅ Public access enabled!")
        print("⏳ Waiting for modification to complete...")
        print("   This may take 2-3 minutes...")

        # Wait for the modification to complete
        waiter = rds.get_waiter("db_instance_available")
        waiter.wait(
            DBInstanceIdentifier="simba-db-restored", WaiterConfig={"Delay": 30, "MaxAttempts": 10}
        )

        print("✅ RDS instance is now publicly accessible!")
        print("🔍 You can now connect to explore your data")

    except ClientError as e:
        print(f"❌ Error enabling public access: {e}")


if __name__ == "__main__":
    enable_public_access()
