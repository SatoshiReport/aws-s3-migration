"""Migration workflow utilities and cost calculations"""

import json
import os
from datetime import datetime


class UnknownInstanceClassError(KeyError):
    """Raised when an RDS instance class is not in the cost mapping."""


def estimate_rds_monthly_cost(instance_class):
    """Estimate monthly cost for RDS instance class.

    Raises:
        UnknownInstanceClassError: If the instance class is not in the cost mapping.
    """
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

    if instance_class not in cost_mapping:
        raise UnknownInstanceClassError(
            f"Unknown instance class: {instance_class}. "
            f"Supported classes: {', '.join(sorted(cost_mapping.keys()))}"
        )
    return cost_mapping[instance_class]


def estimate_aurora_serverless_cost():
    """Estimate Aurora Serverless v2 cost for typical usage"""
    hours_per_month = 720
    average_acu = 0.5
    utilization = 0.2
    cost_per_acu_hour = 0.12

    monthly_cost = hours_per_month * average_acu * utilization * cost_per_acu_hour
    return monthly_cost


def print_migration_results(original_instance, endpoint_info, original_cost, new_cost):
    """Print migration results and next steps"""
    print("\n" + "=" * 80)
    print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 80)

    print("\n📊 MIGRATION SUMMARY:")
    print(
        f"Original RDS Instance: {original_instance['identifier']} ({original_instance['region']})"
    )
    print(f"New Aurora Cluster: {endpoint_info['cluster_identifier']}")
    print(f"Engine Migration: {original_instance['engine']} → {endpoint_info['engine']}")
    print(f"Cost Reduction: ${original_cost:.2f}/month → ${new_cost:.2f}/month")
    print(f"Monthly Savings: ${original_cost - new_cost:.2f}")

    print("\n🔗 NEW CONNECTION DETAILS:")
    print(f"Writer Endpoint: {endpoint_info['writer_endpoint']}")
    if endpoint_info["reader_endpoint"]:
        print(f"Reader Endpoint: {endpoint_info['reader_endpoint']}")
    print(f"Port: {endpoint_info['port']}")
    print(f"Engine: {endpoint_info['engine']}")

    print("\n📝 NEXT STEPS:")
    print("1. Update your application connection strings to use the new Aurora endpoints")
    print("2. Test your application thoroughly with the new Aurora cluster")
    print("3. Monitor Aurora Serverless v2 scaling and performance")
    print("4. Once satisfied, delete the original RDS instance to stop charges:")
    print(
        f"   aws rds delete-db-instance --db-instance-identifier "
        f"{original_instance['identifier']} --skip-final-snapshot"
    )

    print("\n⚠️  IMPORTANT NOTES:")
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

    log_file = os.path.join(os.path.dirname(__file__), "..", "..", "config", "migration_log.json")

    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            log_data = json.load(f)
    else:
        log_data = {"migrations": []}

    log_data["migrations"].append(migration_log)

    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)

    print(f"📝 Migration recorded in {log_file}")
