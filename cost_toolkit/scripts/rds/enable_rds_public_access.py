#!/usr/bin/env python3
"""Enable public accessibility for RDS database instances."""

from botocore.exceptions import ClientError

from cost_toolkit.common.aws_client_factory import create_rds_client
from cost_toolkit.scripts.aws_utils import setup_aws_credentials, wait_for_db_instance_available


def enable_public_access():
    """Temporarily enable public access to the restored RDS instance"""

    setup_aws_credentials()
    rds = create_rds_client(region="us-east-1")

    print("🔧 Enabling public access to restored RDS instance...")
    print("⚠️  This is temporary - we'll disable it after data migration")

    try:
        # Modify the instance to be publicly accessible
        rds.modify_db_instance(
            DBInstanceIdentifier="simba-db-restored", PubliclyAccessible=True, ApplyImmediately=True
        )

        print("✅ Public access enabled!")
        print("⏳ Waiting for modification to complete...")
        print("   This may take 2-3 minutes...")

        # Wait for the modification to complete
        wait_for_db_instance_available(rds, "simba-db-restored", max_attempts=10)

        print("✅ RDS instance is now publicly accessible!")
        print("🔍 You can now connect to explore your data")

    except ClientError as e:
        print(f"❌ Error enabling public access: {e}")


def main():
    """Main function."""
    enable_public_access()


if __name__ == "__main__":
    main()
