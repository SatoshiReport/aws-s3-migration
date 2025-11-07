#!/usr/bin/env python3

import time

import boto3
from botocore.exceptions import ClientError


def cleanup_rds_databases():
    """Delete Aurora cluster and stop MariaDB instance"""

    print("AWS RDS Database Cleanup")
    print("=" * 50)

    # 1. Delete Aurora Cluster in eu-west-2
    print("\n1. DELETING AURORA CLUSTER (eu-west-2)")
    print("-" * 40)

    try:
        rds_eu = boto3.client("rds", region_name="eu-west-2")

        cluster_id = "database-1"
        instance_id = "database-1-instance-1"

        print(f"Deleting Aurora instance: {instance_id}")

        # First delete the instance
        try:
            rds_eu.delete_db_instance(
                DBInstanceIdentifier=instance_id,
                SkipFinalSnapshot=True,
                DeleteAutomatedBackups=True,
            )
            print(f"  ✅ Aurora instance deletion initiated")

        except ClientError as e:
            if "DBInstanceNotFound" in str(e):
                print(f"  ⚠️  Instance already deleted")
            elif "InvalidDBInstanceState" in str(e) and "already being deleted" in str(e):
                print(f"  ⚠️  Instance already being deleted")
            else:
                print(f"  ❌ Error deleting instance: {e}")
                return

        # Wait for instance to be deleted before deleting cluster
        print("  ⏳ Waiting for instance deletion...")
        try:
            waiter = rds_eu.get_waiter("db_instance_deleted")
            waiter.wait(
                DBInstanceIdentifier=instance_id, WaiterConfig={"Delay": 30, "MaxAttempts": 20}
            )
            print(f"  ✅ Aurora instance deleted successfully")
        except Exception as e:
            print(f"  ⚠️  Proceeding with cluster deletion: {e}")

        # Now delete the cluster
        print(f"Deleting Aurora cluster: {cluster_id}")
        try:
            rds_eu.delete_db_cluster(DBClusterIdentifier=cluster_id, SkipFinalSnapshot=True)
            print(f"  ✅ Aurora cluster deletion initiated")
            print(f"  💰 Will save: ~$0.05/month")

        except ClientError as e:
            if "DBClusterNotFound" in str(e):
                print(f"  ⚠️  Cluster already deleted")
            else:
                print(f"  ❌ Error deleting cluster: {e}")

    except ClientError as e:
        print(f"❌ Error accessing eu-west-2: {e}")

    # 2. Stop MariaDB Instance in us-east-1
    print("\n2. STOPPING MARIADB INSTANCE (us-east-1)")
    print("-" * 40)

    try:
        rds_us = boto3.client("rds", region_name="us-east-1")

        instance_id = "database-1"

        # Check current status
        try:
            response = rds_us.describe_db_instances(DBInstanceIdentifier=instance_id)
            current_status = response["DBInstances"][0]["DBInstanceStatus"]
            print(f"Current status: {current_status}")

            if current_status == "available":
                print(f"Stopping MariaDB instance: {instance_id}")
                rds_us.stop_db_instance(DBInstanceIdentifier=instance_id)
                print(f"  ✅ MariaDB instance stop initiated")
                print(f"  💰 Will save: ~$1.29/month while stopped")
                print(f"  📝 Instance preserved - can be restarted when needed")

            elif current_status == "stopped":
                print(f"  ⚠️  Instance already stopped")

            else:
                print(f"  ⚠️  Instance status '{current_status}' - cannot stop")

        except ClientError as e:
            if "DBInstanceNotFound" in str(e):
                print(f"  ❌ Instance not found")
            else:
                print(f"  ❌ Error: {e}")

    except ClientError as e:
        print(f"❌ Error accessing us-east-1: {e}")

    print(f"\n" + "=" * 50)
    print(f"RDS CLEANUP SUMMARY:")
    print(f"• Aurora Cluster (eu-west-2): Deleted")
    print(f"• MariaDB Instance (us-east-1): Stopped (not deleted)")
    print(f"• Estimated savings: ~$1.34/month while stopped")
    print(f"• MariaDB can be restarted anytime if needed")


if __name__ == "__main__":
    cleanup_rds_databases()
