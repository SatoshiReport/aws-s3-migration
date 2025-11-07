#!/usr/bin/env python3
"""
AWS Lightsail Cleanup Script
Completely removes all Lightsail instances and databases to eliminate charges.
"""

import json
import os
import sys
import time
from datetime import datetime

import boto3

# Add parent directory to path for shared utilities
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from aws_utils import get_aws_regions, setup_aws_credentials


def delete_lightsail_instances():
    """Delete all Lightsail instances across all regions"""
    setup_aws_credentials()

    print("🔍 LIGHTSAIL INSTANCE CLEANUP")
    print("=" * 80)
    print("⚠️  WARNING: This will DELETE ALL Lightsail instances and databases!")
    print("This action cannot be undone. All data will be lost.")
    print("=" * 80)

    # Regions where Lightsail is available
    lightsail_regions = [
        "us-east-1",
        "us-east-2",
        "us-west-1",
        "us-west-2",
        "eu-west-1",
        "eu-west-2",
        "eu-central-1",
        "ap-southeast-1",
        "ap-southeast-2",
        "ap-south-1",
    ]

    total_instances_deleted = 0
    total_databases_deleted = 0
    total_savings = 0.0

    for region in lightsail_regions:
        try:
            print(f"\n🔍 Checking region: {region}")
            lightsail_client = boto3.client("lightsail", region_name=region)

            # Get instances
            instances_response = lightsail_client.get_instances()
            instances = instances_response.get("instances", [])

            # Get databases
            databases_response = lightsail_client.get_relational_databases()
            databases = databases_response.get("relationalDatabases", [])

            if not instances and not databases:
                print(f"✅ No Lightsail resources found in {region}")
                continue

            # Delete instances
            for instance in instances:
                instance_name = instance["name"]
                instance_state = instance["state"]["name"]
                bundle_id = instance.get("bundleId", "unknown")

                print(f"\n📦 Found instance: {instance_name}")
                print(f"   State: {instance_state}")
                print(f"   Bundle: {bundle_id}")

                # Estimate monthly cost based on bundle
                monthly_cost = estimate_instance_cost(bundle_id)
                total_savings += monthly_cost

                try:
                    print(f"🗑️  Deleting instance: {instance_name}")
                    # Force delete instance and any associated addons (static IPs, load balancers, etc.)
                    lightsail_client.delete_instance(
                        instanceName=instance_name, forceDeleteAddOns=True
                    )
                    print(f"✅ Successfully deleted instance: {instance_name}")
                    print(f"💰 Monthly savings: ${monthly_cost:.2f}")
                    total_instances_deleted += 1

                    # Wait a moment between deletions
                    time.sleep(2)

                except Exception as e:
                    print(f"❌ Error deleting instance {instance_name}: {e}")

            # Delete databases
            for database in databases:
                db_name = database["name"]
                db_state = database["state"]
                db_bundle = database.get("relationalDatabaseBundleId", "unknown")

                print(f"\n🗄️  Found database: {db_name}")
                print(f"   State: {db_state}")
                print(f"   Bundle: {db_bundle}")

                # Estimate monthly cost
                monthly_cost = estimate_database_cost(db_bundle)
                total_savings += monthly_cost

                try:
                    print(f"🗑️  Deleting database: {db_name}")
                    lightsail_client.delete_relational_database(
                        relationalDatabaseName=db_name,
                        skipFinalSnapshot=True,  # Skip final snapshot to avoid additional charges
                    )
                    print(f"✅ Successfully deleted database: {db_name}")
                    print(f"💰 Monthly savings: ${monthly_cost:.2f}")
                    total_databases_deleted += 1

                    # Wait a moment between deletions
                    time.sleep(2)

                except Exception as e:
                    print(f"❌ Error deleting database {db_name}: {e}")

        except Exception as e:
            if "InvalidAction" in str(e) or "not available" in str(e):
                print(f"ℹ️  Lightsail not available in {region}")
            else:
                print(f"❌ Error accessing Lightsail in {region}: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("🎉 LIGHTSAIL CLEANUP COMPLETED")
    print("=" * 80)
    print(f"Instances deleted: {total_instances_deleted}")
    print(f"Databases deleted: {total_databases_deleted}")
    print(f"Total estimated monthly savings: ${total_savings:.2f}")

    if total_instances_deleted > 0 or total_databases_deleted > 0:
        print("\n📝 IMPORTANT NOTES:")
        print("• Lightsail resources are being deleted in the background")
        print("• It may take a few minutes for charges to stop")
        print("• Final bills may include partial charges for the current period")
        print("• All data has been permanently deleted")

        # Record the cleanup action
        record_cleanup_action(
            "lightsail", total_instances_deleted + total_databases_deleted, total_savings
        )

    return total_instances_deleted, total_databases_deleted, total_savings


def estimate_instance_cost(bundle_id):
    """Estimate monthly cost based on Lightsail bundle ID"""
    # Common Lightsail bundle pricing (approximate)
    bundle_costs = {
        "nano_2_0": 3.50,
        "micro_2_0": 5.00,
        "small_2_0": 10.00,
        "medium_2_0": 20.00,
        "large_2_0": 40.00,
        "xlarge_2_0": 80.00,
        "2xlarge_2_0": 160.00,
    }

    return bundle_costs.get(bundle_id, 10.00)  # Default estimate


def estimate_database_cost(bundle_id):
    """Estimate monthly cost for Lightsail database"""
    # Common database bundle pricing (approximate)
    db_costs = {
        "micro_1_0": 15.00,
        "small_1_0": 30.00,
        "medium_1_0": 60.00,
        "large_1_0": 115.00,
    }

    return db_costs.get(bundle_id, 30.00)  # Default estimate


def record_cleanup_action(service, resources_deleted, savings):
    """Record cleanup action to prevent future optimization attempts"""
    cleanup_log = {
        "timestamp": datetime.now().isoformat(),
        "service": service,
        "action": "deleted_all_resources",
        "resources_deleted": resources_deleted,
        "estimated_monthly_savings": savings,
        "status": "completed",
    }

    # Create cleanup log file
    log_file = os.path.join(os.path.dirname(__file__), "..", "config", "cleanup_log.json")

    try:
        # Read existing log
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                log_data = json.load(f)
        else:
            log_data = {"cleanup_actions": []}

        # Add new action
        log_data["cleanup_actions"].append(cleanup_log)

        # Write updated log
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2)

        print(f"📝 Cleanup action recorded in {log_file}")

    except Exception as e:
        print(f"⚠️  Could not record cleanup action: {e}")


def main():
    """Main function"""
    print("AWS Lightsail Complete Cleanup")
    print("=" * 80)
    print("This script will DELETE ALL Lightsail instances and databases.")
    print("This will eliminate all Lightsail charges from your AWS account.")
    print("=" * 80)

    # Confirmation prompt
    response = input(
        "\nAre you sure you want to delete ALL Lightsail resources? (type 'DELETE' to confirm): "
    )

    if response != "DELETE":
        print("❌ Cleanup cancelled. No resources were deleted.")
        return

    # Perform cleanup
    instances, databases, savings = delete_lightsail_instances()

    if instances == 0 and databases == 0:
        print("\n✅ No Lightsail resources found. Your account is already clean!")
    else:
        print(f"\n🎉 Cleanup completed! Estimated monthly savings: ${savings:.2f}")


if __name__ == "__main__":
    main()
