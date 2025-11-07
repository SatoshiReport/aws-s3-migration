#!/usr/bin/env python3
"""
AWS RDS to Aurora Serverless v2 Migration Script
Migrates existing RDS instances to Aurora Serverless v2 for cost optimization.
"""

import json
import os
import sys
import time
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for shared utilities
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from aws_utils import get_aws_regions, setup_aws_credentials


def discover_rds_instances():
    """Discover all RDS instances across regions"""
    setup_aws_credentials()

    print("🔍 DISCOVERING RDS INSTANCES")
    print("=" * 80)

    regions = get_aws_regions()
    discovered_instances = []

    for region in regions:
        try:
            rds_client = boto3.client("rds", region_name=region)
            response = rds_client.describe_db_instances()

            for instance in response["DBInstances"]:
                # Skip instances that are already part of Aurora clusters
                if instance.get("DBClusterIdentifier"):
                    continue

                instance_info = {
                    "region": region,
                    "identifier": instance["DBInstanceIdentifier"],
                    "engine": instance["Engine"],
                    "engine_version": instance.get("EngineVersion", "Unknown"),
                    "instance_class": instance["DBInstanceClass"],
                    "status": instance["DBInstanceStatus"],
                    "allocated_storage": instance.get("AllocatedStorage", 0),
                    "storage_type": instance.get("StorageType", "gp2"),
                    "multi_az": instance.get("MultiAZ", False),
                    "publicly_accessible": instance.get("PubliclyAccessible", False),
                    "vpc_security_groups": [
                        sg["VpcSecurityGroupId"] for sg in instance.get("VpcSecurityGroups", [])
                    ],
                    "db_subnet_group": instance.get("DBSubnetGroup", {}).get("DBSubnetGroupName"),
                    "parameter_group": instance.get("DBParameterGroups", [{}])[0].get(
                        "DBParameterGroupName"
                    ),
                    "backup_retention": instance.get("BackupRetentionPeriod", 0),
                    "preferred_backup_window": instance.get("PreferredBackupWindow"),
                    "preferred_maintenance_window": instance.get("PreferredMaintenanceWindow"),
                    "storage_encrypted": instance.get("StorageEncrypted", False),
                    "kms_key_id": instance.get("KmsKeyId"),
                    "deletion_protection": instance.get("DeletionProtection", False),
                }

                discovered_instances.append(instance_info)

                print(f"\n📦 Found RDS Instance: {instance_info['identifier']}")
                print(f"   Region: {region}")
                print(f"   Engine: {instance_info['engine']} {instance_info['engine_version']}")
                print(f"   Class: {instance_info['instance_class']}")
                print(f"   Status: {instance_info['status']}")
                print(
                    f"   Storage: {instance_info['allocated_storage']} GB ({instance_info['storage_type']})"
                )

        except ClientError as e:
            if "not available" not in str(e).lower():
                print(f"❌ Error accessing region {region}: {e}")

    if not discovered_instances:
        print("✅ No standalone RDS instances found for migration")
        return []

    print(f"\n📊 Total instances found: {len(discovered_instances)}")
    return discovered_instances


def validate_migration_compatibility(instance_info):
    """Validate if instance can be migrated to Aurora Serverless v2"""
    print(f"\n🔍 Validating migration compatibility for {instance_info['identifier']}")

    compatibility_issues = []

    # Check engine compatibility
    compatible_engines = {
        "mysql": ["aurora-mysql"],
        "postgres": ["aurora-postgresql"],
        "mariadb": ["aurora-mysql"],  # MariaDB can migrate to Aurora MySQL
    }

    source_engine = instance_info["engine"].lower()
    if source_engine not in compatible_engines:
        compatibility_issues.append(
            f"Engine '{instance_info['engine']}' is not compatible with Aurora Serverless v2"
        )

    # Check if instance is running
    if instance_info["status"] != "available":
        compatibility_issues.append(
            f"Instance status is '{instance_info['status']}', must be 'available' for migration"
        )

    # Check storage size (Aurora has minimum requirements)
    if instance_info["allocated_storage"] < 1:
        compatibility_issues.append("Storage size too small for Aurora migration")

    if compatibility_issues:
        print("❌ Migration compatibility issues found:")
        for issue in compatibility_issues:
            print(f"   • {issue}")
        return False, compatibility_issues

    # Determine target Aurora engine
    target_engine = compatible_engines[source_engine][0]
    print(f"✅ Compatible for migration: {instance_info['engine']} → {target_engine}")

    return True, target_engine


def create_rds_snapshot(rds_client, instance_identifier, region):
    """Create a snapshot of the RDS instance"""
    snapshot_identifier = f"{instance_identifier}-migration-{int(time.time())}"

    print(f"\n📸 Creating snapshot: {snapshot_identifier}")

    try:
        response = rds_client.create_db_snapshot(
            DBSnapshotIdentifier=snapshot_identifier, DBInstanceIdentifier=instance_identifier
        )

        print(f"✅ Snapshot creation initiated: {snapshot_identifier}")

        # Wait for snapshot to complete
        print("⏳ Waiting for snapshot to complete...")
        waiter = rds_client.get_waiter("db_snapshot_completed")
        waiter.wait(
            DBSnapshotIdentifier=snapshot_identifier,
            WaiterConfig={"Delay": 30, "MaxAttempts": 120},  # 60 minutes max
        )

        print(f"✅ Snapshot completed: {snapshot_identifier}")
        return snapshot_identifier

    except ClientError as e:
        print(f"❌ Error creating snapshot: {e}")
        raise


def create_aurora_serverless_cluster(rds_client, instance_info, target_engine, snapshot_identifier):
    """Create Aurora Serverless v2 cluster from RDS snapshot"""
    cluster_identifier = f"{instance_info['identifier']}-aurora-serverless"

    print(f"\n🚀 Creating Aurora Serverless v2 cluster: {cluster_identifier}")

    try:
        # First, create an empty Aurora Serverless v2 cluster
        cluster_params = {
            "DBClusterIdentifier": cluster_identifier,
            "Engine": target_engine,
            # Let AWS choose the latest compatible version
            "MasterUsername": "postgres" if target_engine == "aurora-postgresql" else "admin",
            "MasterUserPassword": "TempPassword123!",  # Temporary password
            "ServerlessV2ScalingConfiguration": {
                "MinCapacity": 0.5,  # Minimum for cost optimization
                "MaxCapacity": 4.0,  # Reasonable maximum for most workloads
            },
            "DeletionProtection": False,  # Allow deletion for cost management
            "EnableCloudwatchLogsExports": (
                ["postgresql"]
                if target_engine == "aurora-postgresql"
                else ["error", "general", "slowquery"]
            ),
            "BackupRetentionPeriod": max(instance_info["backup_retention"], 1),
            "StorageEncrypted": instance_info["storage_encrypted"],
        }

        # Add VPC security groups if available
        if instance_info["vpc_security_groups"]:
            cluster_params["VpcSecurityGroupIds"] = instance_info["vpc_security_groups"]

        # Add subnet group if available
        if instance_info["db_subnet_group"]:
            cluster_params["DBSubnetGroupName"] = instance_info["db_subnet_group"]

        # Add KMS key if encryption is enabled
        if instance_info["storage_encrypted"] and instance_info["kms_key_id"]:
            cluster_params["KmsKeyId"] = instance_info["kms_key_id"]

        # Add backup and maintenance windows
        if instance_info["preferred_backup_window"]:
            cluster_params["PreferredBackupWindow"] = instance_info["preferred_backup_window"]

        if instance_info["preferred_maintenance_window"]:
            cluster_params["PreferredMaintenanceWindow"] = instance_info[
                "preferred_maintenance_window"
            ]

        response = rds_client.create_db_cluster(**cluster_params)

        print(f"✅ Aurora Serverless v2 cluster creation initiated")
        print(f"   Cluster: {cluster_identifier}")
        print(f"   Engine: {target_engine}")
        print(f"   Scaling: 0.5-4.0 ACU")

        # Wait for cluster to be available
        print("⏳ Waiting for cluster to become available...")
        waiter = rds_client.get_waiter("db_cluster_available")
        waiter.wait(
            DBClusterIdentifier=cluster_identifier,
            WaiterConfig={"Delay": 30, "MaxAttempts": 120},  # 60 minutes max
        )

        print(f"✅ Aurora Serverless v2 cluster is ready: {cluster_identifier}")

        # Get cluster endpoint information
        cluster_response = rds_client.describe_db_clusters(DBClusterIdentifier=cluster_identifier)
        cluster = cluster_response["DBClusters"][0]

        endpoint_info = {
            "cluster_identifier": cluster_identifier,
            "writer_endpoint": cluster["Endpoint"],
            "reader_endpoint": cluster.get("ReaderEndpoint"),
            "port": cluster["Port"],
            "engine": cluster["Engine"],
            "status": cluster["Status"],
        }

        return endpoint_info

    except ClientError as e:
        print(f"❌ Error creating Aurora Serverless v2 cluster: {e}")
        raise


def migrate_rds_to_aurora_serverless(instance_identifier=None, region=None):
    """Main migration function"""
    setup_aws_credentials()

    print("🚀 RDS TO AURORA SERVERLESS V2 MIGRATION")
    print("=" * 80)
    print("This script will migrate your RDS instance to Aurora Serverless v2")
    print("for significant cost savings through automatic scaling.")
    print("=" * 80)

    # Discover instances
    instances = discover_rds_instances()

    if not instances:
        print("No RDS instances found for migration.")
        return

    # If specific instance not provided, let user choose
    if not instance_identifier:
        print("\nAvailable instances for migration:")
        for i, instance in enumerate(instances, 1):
            print(
                f"{i}. {instance['identifier']} ({instance['region']}) - {instance['engine']} {instance['instance_class']}"
            )

        try:
            choice = int(input("\nSelect instance to migrate (number): ")) - 1
            if choice < 0 or choice >= len(instances):
                raise ValueError("Invalid selection")
            selected_instance = instances[choice]
        except (ValueError, IndexError):
            print("❌ Invalid selection. Exiting.")
            return
    else:
        # Find specific instance
        selected_instance = None
        for instance in instances:
            if instance["identifier"] == instance_identifier and (
                not region or instance["region"] == region
            ):
                selected_instance = instance
                break

        if not selected_instance:
            print(f"❌ Instance '{instance_identifier}' not found.")
            return

    print(
        f"\n🎯 Selected for migration: {selected_instance['identifier']} ({selected_instance['region']})"
    )

    # Validate compatibility
    is_compatible, target_engine_or_issues = validate_migration_compatibility(selected_instance)

    if not is_compatible:
        print("❌ Migration cannot proceed due to compatibility issues.")
        return

    target_engine = target_engine_or_issues

    # Estimate cost savings
    current_monthly_cost = estimate_rds_monthly_cost(selected_instance["instance_class"])
    estimated_serverless_cost = estimate_aurora_serverless_cost()

    print(f"\n💰 COST ANALYSIS:")
    print(f"   Current RDS cost: ~${current_monthly_cost:.2f}/month")
    print(f"   Aurora Serverless v2: ~${estimated_serverless_cost:.2f}/month (with auto-scaling)")
    print(f"   Potential savings: ~${current_monthly_cost - estimated_serverless_cost:.2f}/month")

    # Confirmation
    print(f"\n⚠️  MIGRATION PLAN:")
    print(f"1. Create snapshot of {selected_instance['identifier']}")
    print(f"2. Create Aurora Serverless v2 cluster from snapshot")
    print(f"3. Provide new connection details")
    print(f"4. Keep original RDS instance for rollback (manual cleanup required)")

    confirm = input("\nProceed with migration? (type 'MIGRATE' to confirm): ")
    if confirm != "MIGRATE":
        print("❌ Migration cancelled.")
        return

    # Perform migration
    try:
        rds_client = boto3.client("rds", region_name=selected_instance["region"])

        # Step 1: Create snapshot
        snapshot_id = create_rds_snapshot(
            rds_client, selected_instance["identifier"], selected_instance["region"]
        )

        # Step 2: Create Aurora Serverless v2 cluster
        endpoint_info = create_aurora_serverless_cluster(
            rds_client, selected_instance, target_engine, snapshot_id
        )

        # Step 3: Provide connection information
        print_migration_results(
            selected_instance, endpoint_info, current_monthly_cost, estimated_serverless_cost
        )

        # Record migration
        record_migration_action(
            selected_instance, endpoint_info, current_monthly_cost - estimated_serverless_cost
        )

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print("Please check AWS console for any resources that may need cleanup.")
        raise


def estimate_rds_monthly_cost(instance_class):
    """Estimate monthly cost for RDS instance class"""
    # Approximate US East 1 pricing
    cost_mapping = {
        "db.t3.micro": 15.0,
        "db.t3.small": 30.0,
        "db.t3.medium": 60.0,
        "db.t3.large": 120.0,
        "db.t3.xlarge": 240.0,
        "db.t3.2xlarge": 480.0,
        "db.m5.large": 180.0,
        "db.m5.xlarge": 360.0,
        "db.r5.large": 220.0,
        "db.r5.xlarge": 440.0,
    }

    return cost_mapping.get(instance_class, 100.0)  # Default estimate


def estimate_aurora_serverless_cost():
    """Estimate Aurora Serverless v2 cost for typical usage"""
    # Assuming 20% utilization at 0.5 ACU average
    # $0.12 per ACU-hour in US East 1
    hours_per_month = 720
    average_acu = 0.5
    utilization = 0.2  # 20% active time
    cost_per_acu_hour = 0.12

    monthly_cost = hours_per_month * average_acu * utilization * cost_per_acu_hour
    return monthly_cost


def print_migration_results(original_instance, endpoint_info, original_cost, new_cost):
    """Print migration results and next steps"""
    print("\n" + "=" * 80)
    print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 80)

    print(f"\n📊 MIGRATION SUMMARY:")
    print(
        f"Original RDS Instance: {original_instance['identifier']} ({original_instance['region']})"
    )
    print(f"New Aurora Cluster: {endpoint_info['cluster_identifier']}")
    print(f"Engine Migration: {original_instance['engine']} → {endpoint_info['engine']}")
    print(f"Cost Reduction: ${original_cost:.2f}/month → ${new_cost:.2f}/month")
    print(f"Monthly Savings: ${original_cost - new_cost:.2f}")

    print(f"\n🔗 NEW CONNECTION DETAILS:")
    print(f"Writer Endpoint: {endpoint_info['writer_endpoint']}")
    if endpoint_info["reader_endpoint"]:
        print(f"Reader Endpoint: {endpoint_info['reader_endpoint']}")
    print(f"Port: {endpoint_info['port']}")
    print(f"Engine: {endpoint_info['engine']}")

    print(f"\n📝 NEXT STEPS:")
    print("1. Update your application connection strings to use the new Aurora endpoints")
    print("2. Test your application thoroughly with the new Aurora cluster")
    print("3. Monitor Aurora Serverless v2 scaling and performance")
    print("4. Once satisfied, delete the original RDS instance to stop charges:")
    print(
        f"   aws rds delete-db-instance --db-instance-identifier {original_instance['identifier']} --skip-final-snapshot"
    )

    print(f"\n⚠️  IMPORTANT NOTES:")
    print("• The original RDS instance is still running and incurring charges")
    print("• Aurora Serverless v2 will automatically scale based on demand")
    print("• Minimum scaling is 0.5 ACU (~$43/month if always active)")
    print("• Cluster will scale to zero during periods of inactivity")
    print("• Monitor CloudWatch metrics for scaling behavior")


def record_migration_action(original_instance, endpoint_info, monthly_savings):
    """Record migration action for tracking"""
    migration_log = {
        "timestamp": datetime.now().isoformat(),
        "action": "rds_to_aurora_serverless_migration",
        "original_instance": {
            "identifier": original_instance["identifier"],
            "region": original_instance["region"],
            "engine": original_instance["engine"],
            "instance_class": original_instance["instance_class"],
        },
        "new_cluster": {
            "identifier": endpoint_info["cluster_identifier"],
            "engine": endpoint_info["engine"],
            "writer_endpoint": endpoint_info["writer_endpoint"],
        },
        "estimated_monthly_savings": monthly_savings,
        "status": "completed",
    }

    # Create migration log file
    log_file = os.path.join(os.path.dirname(__file__), "..", "config", "migration_log.json")

    try:
        # Read existing log
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                log_data = json.load(f)
        else:
            log_data = {"migrations": []}

        # Add new migration
        log_data["migrations"].append(migration_log)

        # Write updated log
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2)

        print(f"📝 Migration recorded in {log_file}")

    except Exception as e:
        print(f"⚠️  Could not record migration: {e}")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate RDS instance to Aurora Serverless v2")
    parser.add_argument("--instance", help="RDS instance identifier to migrate")
    parser.add_argument("--region", help="AWS region of the instance")
    parser.add_argument("--list-only", action="store_true", help="Only list available instances")

    args = parser.parse_args()

    if args.list_only:
        discover_rds_instances()
        return

    migrate_rds_to_aurora_serverless(args.instance, args.region)


if __name__ == "__main__":
    main()
