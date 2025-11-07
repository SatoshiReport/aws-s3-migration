#!/usr/bin/env python3
"""
AWS Cleanup Script
Disables Global Accelerator and stops Lightsail instances to reduce costs.
"""

import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cost_toolkit.scripts import aws_utils  # pylint: disable=wrong-import-position

INSTANCE_BUNDLE_COSTS = {
    "nano_2_0": 3.5,
    "micro_2_0": 5.0,
    "small_2_0": 10.0,
    "medium_2_0": 20.0,
    "large_2_0": 40.0,
    "xlarge_2_0": 80.0,
    "2xlarge_2_0": 160.0,
}

DATABASE_BUNDLE_COSTS = {
    "micro_1_0": 15.0,
    "small_1_0": 30.0,
    "medium_1_0": 60.0,
    "large_1_0": 115.0,
}


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    aws_utils.setup_aws_credentials()


def estimate_instance_cost(bundle_id: str | None) -> float:
    """Approximate monthly cost for a Lightsail instance bundle."""
    if not bundle_id:
        return 0.0
    return INSTANCE_BUNDLE_COSTS.get(bundle_id, 0.0)


def estimate_database_cost(bundle_id: str | None) -> float:
    """Approximate monthly cost for a Lightsail database bundle."""
    if not bundle_id:
        return 0.0
    return DATABASE_BUNDLE_COSTS.get(bundle_id, 0.0)


def disable_global_accelerators():
    """Disable all Global Accelerators"""
    setup_aws_credentials()

    print("🔍 Checking Global Accelerators...")
    print("=" * 60)

    try:
        # Global Accelerator is only available in us-west-2
        ga_client = boto3.client("globalaccelerator", region_name="us-west-2")

        # List all accelerators
        response = ga_client.list_accelerators()
        accelerators = response.get("Accelerators", [])

        if not accelerators:
            print("✅ No Global Accelerators found.")
            return

        for accelerator in accelerators:
            accelerator_arn = accelerator["AcceleratorArn"]
            accelerator_name = accelerator["Name"]
            status = accelerator["Status"]

            print(f"📍 Found accelerator: {accelerator_name}")
            print(f"   ARN: {accelerator_arn}")
            print(f"   Status: {status}")

            if status == "IN_PROGRESS":
                print(f"⏳ Accelerator {accelerator_name} is already being modified. Skipping...")
                continue

            if status == "DEPLOYED":
                print(f"🛑 Disabling accelerator: {accelerator_name}")
                try:
                    ga_client.update_accelerator(AcceleratorArn=accelerator_arn, Enabled=False)
                    print(f"✅ Successfully disabled accelerator: {accelerator_name}")
                except ClientError as e:
                    print(f"❌ Error disabling accelerator {accelerator_name}: {e}")
            else:
                print(f"ℹ️  Accelerator {accelerator_name} is already disabled or in transition.")

            print("-" * 40)

    except ClientError as e:
        print(f"❌ Error accessing Global Accelerator service: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def stop_lightsail_instances():
    """Stop all Lightsail instances"""
    setup_aws_credentials()

    print("\n🔍 Checking Lightsail instances...")
    print("=" * 60)

    regions_to_check = ["eu-central-1", "us-east-1", "us-west-2", "eu-west-1"]
    total_instances_stopped = 0
    total_databases_stopped = 0
    estimated_monthly_savings = 0.0

    for region in regions_to_check:
        try:
            print(f"\n📍 Checking region: {region}")
            lightsail_client = boto3.client("lightsail", region_name=region)

            instances = lightsail_client.get_instances().get("instances", [])
            databases = lightsail_client.get_relational_databases().get("relationalDatabases", [])

            if not instances and not databases:
                print(f"✅ No Lightsail resources found in {region}")
                continue

            for instance in instances:
                instance_name = instance["name"]
                state = instance["state"]["name"]
                bundle_id = instance.get("bundleId")

                print(f"📦 Found instance: {instance_name}")
                print(f"   State: {state}")

                if state == "running":
                    print(f"🛑 Stopping instance: {instance_name}")
                    try:
                        lightsail_client.stop_instance(instanceName=instance_name)
                        total_instances_stopped += 1
                        monthly_cost = estimate_instance_cost(bundle_id)
                        estimated_monthly_savings += monthly_cost
                        if monthly_cost:
                            print(
                                f"✅ Stopped instance {instance_name} (est. ${monthly_cost:.2f}/month)"
                            )
                        else:
                            print(f"✅ Stopped instance {instance_name}")
                    except ClientError as exc:
                        print(f"❌ Error stopping instance {instance_name}: {exc}")
                else:
                    print(f"ℹ️  Instance {instance_name} is already {state}")

                print("-" * 30)

            for database in databases:
                db_name = database["name"]
                db_state = database["state"]
                bundle_id = database.get("relationalDatabaseBundleId")

                print(f"🗄️  Found database: {db_name}")
                print(f"   State: {db_state}")

                if db_state.lower() == "available":
                    print(f"🛑 Stopping database: {db_name}")
                    try:
                        lightsail_client.stop_relational_database(relationalDatabaseName=db_name)
                        total_databases_stopped += 1
                        monthly_cost = estimate_database_cost(bundle_id)
                        estimated_monthly_savings += monthly_cost
                        if monthly_cost:
                            print(f"✅ Stopped database {db_name} (est. ${monthly_cost:.2f}/month)")
                        else:
                            print(f"✅ Stopped database {db_name}")
                    except ClientError as exc:
                        print(f"❌ Error stopping database {db_name}: {exc}")
                else:
                    print(f"ℹ️  Database {db_name} is already {db_state}")

                print("-" * 30)

        except ClientError as exc:
            if "InvalidAction" in str(exc) or "not available" in str(exc):
                print(f"ℹ️  Lightsail not available in {region}")
            else:
                print(f"❌ Error accessing Lightsail in {region}: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Unexpected error in {region}: {exc}")

    return total_instances_stopped, total_databases_stopped, estimated_monthly_savings


def main():
    """Main function to run cleanup operations"""
    print("AWS Cost Optimization Cleanup")
    print("=" * 80)
    print("This script will:")
    print("1. Disable Global Accelerators")
    print("2. Stop Lightsail instances and databases")
    print("=" * 80)

    disable_global_accelerators()
    instances, databases, savings = stop_lightsail_instances()

    print("\n" + "=" * 80)
    print("🎉 Cleanup completed!")
    print(f"📦 Lightsail instances stopped: {instances}")
    print(f"🗄️  Lightsail databases stopped: {databases}")
    print(f"💰 Estimated monthly savings from stopped resources: ${savings:.2f}")
    print("⏰ Changes may take a few minutes to take effect.")
    print("=" * 80)


if __name__ == "__main__":
    main()
