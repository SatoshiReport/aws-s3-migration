"""CLI interface for RDS to Aurora Serverless migration"""

import argparse

import boto3

from ...aws_utils import setup_aws_credentials
from .cluster_ops import (
    create_aurora_serverless_cluster,
    create_rds_snapshot,
    discover_rds_instances,
    validate_migration_compatibility,
)
from .migration_workflow import (
    estimate_aurora_serverless_cost,
    estimate_rds_monthly_cost,
    print_migration_results,
    record_migration_action,
)


class InvalidSelectionError(ValueError):
    """Raised when user makes an invalid instance selection."""

    def __init__(self):
        super().__init__("Invalid selection")


def _validate_choice(choice: int, max_instances: int) -> None:
    """Validate the user's instance choice."""
    if choice < 0 or choice >= max_instances:
        raise InvalidSelectionError()


def _select_instance_for_migration(instances, instance_identifier, region):
    """Select an instance for migration from the discovered instances."""
    if not instance_identifier:
        print("\nAvailable instances for migration:")
        for i, instance in enumerate(instances, 1):
            print(
                f"{i}. {instance['identifier']} ({instance['region']}) - "
                f"{instance['engine']} {instance['instance_class']}"
            )

        try:
            choice = int(input("\nSelect instance to migrate (number): ")) - 1
            _validate_choice(choice, len(instances))
            return instances[choice]
        except (InvalidSelectionError, ValueError, IndexError):
            print("❌ Invalid selection. Exiting.")
            return None

    for instance in instances:
        if instance["identifier"] == instance_identifier and (
            not region or instance["region"] == region
        ):
            return instance

    print(f"❌ Instance '{instance_identifier}' not found.")
    return None


def _print_cost_analysis(selected_instance):
    """Print cost analysis for the migration."""
    current_monthly_cost = estimate_rds_monthly_cost(selected_instance["instance_class"])
    estimated_serverless_cost = estimate_aurora_serverless_cost()

    print("\n💰 COST ANALYSIS:")
    print(f"   Current RDS cost: ~${current_monthly_cost:.2f}/month")
    print(f"   Aurora Serverless v2: ~${estimated_serverless_cost:.2f}/month (with auto-scaling)")
    print(f"   Potential savings: ~${current_monthly_cost - estimated_serverless_cost:.2f}/month")

    return current_monthly_cost, estimated_serverless_cost


def _confirm_migration(selected_instance):
    """Get user confirmation for migration."""
    print("\n⚠️  MIGRATION PLAN:")
    print(f"1. Create snapshot of {selected_instance['identifier']}")
    print("2. Create Aurora Serverless v2 cluster from snapshot")
    print("3. Provide new connection details")
    print("4. Keep original RDS instance for rollback (manual cleanup required)")

    confirm = input("\nProceed with migration? (type 'MIGRATE' to confirm): ")
    return confirm == "MIGRATE"


def migrate_rds_to_aurora_serverless(instance_identifier=None, region=None):
    """Main migration function"""
    setup_aws_credentials()

    print("🚀 RDS TO AURORA SERVERLESS V2 MIGRATION")
    print("=" * 80)
    print("This script will migrate your RDS instance to Aurora Serverless v2")
    print("for significant cost savings through automatic scaling.")
    print("=" * 80)

    instances = discover_rds_instances()

    if not instances:
        print("No RDS instances found for migration.")
        return

    selected_instance = _select_instance_for_migration(instances, instance_identifier, region)
    if not selected_instance:
        return

    print(
        f"\n🎯 Selected for migration: {selected_instance['identifier']} "
        f"({selected_instance['region']})"
    )

    is_compatible, target_engine_or_issues = validate_migration_compatibility(selected_instance)

    if not is_compatible:
        print("❌ Migration cannot proceed due to compatibility issues.")
        return

    target_engine = target_engine_or_issues

    current_monthly_cost, estimated_serverless_cost = _print_cost_analysis(selected_instance)

    if not _confirm_migration(selected_instance):
        print("❌ Migration cancelled.")
        return

    try:
        rds_client = boto3.client("rds", region_name=selected_instance["region"])

        snapshot_id = create_rds_snapshot(
            rds_client, selected_instance["identifier"], selected_instance["region"]
        )

        endpoint_info = create_aurora_serverless_cluster(
            rds_client, selected_instance, target_engine, snapshot_id
        )

        print_migration_results(
            selected_instance, endpoint_info, current_monthly_cost, estimated_serverless_cost
        )

        record_migration_action(
            selected_instance, endpoint_info, current_monthly_cost - estimated_serverless_cost
        )

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print("Please check AWS console for any resources that may need cleanup.")
        raise


def main():
    """Main function"""
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
