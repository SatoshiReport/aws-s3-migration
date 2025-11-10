#!/usr/bin/env python3
"""Clean up RDS database instances."""

import boto3
from botocore.exceptions import ClientError


def _delete_aurora_instance(rds_client, instance_id):
    """Delete an Aurora instance."""
    print(f"Deleting Aurora instance: {instance_id}")
    try:
        rds_client.delete_db_instance(
            DBInstanceIdentifier=instance_id,
            SkipFinalSnapshot=True,
            DeleteAutomatedBackups=True,
        )
        print("  ✅ Aurora instance deletion initiated")
    except ClientError as e:
        if "DBInstanceNotFound" in str(e):
            print("  ⚠️  Instance already deleted")
            return False
        if "InvalidDBInstanceState" in str(e) and "already being deleted" in str(e):
            print("  ⚠️  Instance already being deleted")
            return False
        print(f"  ❌ Error deleting instance: {e}")
        raise
    else:
        return True


def _wait_for_instance_deletion(rds_client, instance_id):
    """Wait for an RDS instance to be deleted."""
    print("  ⏳ Waiting for instance deletion...")
    try:
        waiter = rds_client.get_waiter("db_instance_deleted")
        waiter.wait(DBInstanceIdentifier=instance_id, WaiterConfig={"Delay": 30, "MaxAttempts": 20})
        print("  ✅ Aurora instance deleted successfully")
    except ClientError as e:
        print(f"  ⚠️  Proceeding with cluster deletion: {e}")


def _delete_aurora_cluster(rds_client, cluster_id):
    """Delete an Aurora cluster."""
    print(f"Deleting Aurora cluster: {cluster_id}")
    try:
        rds_client.delete_db_cluster(DBClusterIdentifier=cluster_id, SkipFinalSnapshot=True)
        print("  ✅ Aurora cluster deletion initiated")
        print("  💰 Will save: ~$0.05/month")
    except ClientError as e:
        if "DBClusterNotFound" in str(e):
            print("  ⚠️  Cluster already deleted")
        else:
            print(f"  ❌ Error deleting cluster: {e}")


def _cleanup_aurora_cluster():
    """Clean up Aurora cluster in eu-west-2."""
    print("\n1. DELETING AURORA CLUSTER (eu-west-2)")
    print("-" * 40)

    try:
        rds_eu = boto3.client("rds", region_name="eu-west-2")
        cluster_id = "database-1"
        instance_id = "database-1-instance-1"

        if _delete_aurora_instance(rds_eu, instance_id):
            _wait_for_instance_deletion(rds_eu, instance_id)

        _delete_aurora_cluster(rds_eu, cluster_id)

    except ClientError as e:
        print(f"❌ Error accessing eu-west-2: {e}")


def _stop_mariadb_instance(rds_client, instance_id):
    """Stop a MariaDB instance."""
    try:
        response = rds_client.describe_db_instances(DBInstanceIdentifier=instance_id)
        current_status = response["DBInstances"][0]["DBInstanceStatus"]
        print(f"Current status: {current_status}")

        if current_status == "available":
            print(f"Stopping MariaDB instance: {instance_id}")
            rds_client.stop_db_instance(DBInstanceIdentifier=instance_id)
            print("  ✅ MariaDB instance stop initiated")
            print("  💰 Will save: ~$1.29/month while stopped")
            print("  📝 Instance preserved - can be restarted when needed")
        elif current_status == "stopped":
            print("  ⚠️  Instance already stopped")
        else:
            print(f"  ⚠️  Instance status '{current_status}' - cannot stop")

    except ClientError as e:
        if "DBInstanceNotFound" in str(e):
            print("  ❌ Instance not found")
        else:
            print(f"  ❌ Error: {e}")


def _cleanup_mariadb_instance():
    """Stop MariaDB instance in us-east-1."""
    print("\n2. STOPPING MARIADB INSTANCE (us-east-1)")
    print("-" * 40)

    try:
        rds_us = boto3.client("rds", region_name="us-east-1")
        instance_id = "database-1"
        _stop_mariadb_instance(rds_us, instance_id)
    except ClientError as e:
        print(f"❌ Error accessing us-east-1: {e}")


def _print_cleanup_summary():
    """Print the cleanup summary."""
    print("\n" + "=" * 50)
    print("RDS CLEANUP SUMMARY:")
    print("• Aurora Cluster (eu-west-2): Deleted")
    print("• MariaDB Instance (us-east-1): Stopped (not deleted)")
    print("• Estimated savings: ~$1.34/month while stopped")
    print("• MariaDB can be restarted anytime if needed")


def cleanup_rds_databases():
    """Delete Aurora cluster and stop MariaDB instance"""
    print("AWS RDS Database Cleanup")
    print("=" * 50)

    _cleanup_aurora_cluster()
    _cleanup_mariadb_instance()
    _print_cleanup_summary()


if __name__ == "__main__":
    cleanup_rds_databases()
