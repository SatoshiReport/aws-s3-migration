#!/usr/bin/env python3
"""
AWS Cost Overview Script
Provides a comprehensive overview of current AWS costs and optimization opportunities.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import boto3

SCRIPT_ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(SCRIPT_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.append(SCRIPTS_DIR)

from aws_utils import setup_aws_credentials

# Cost thresholds for recommendations
COST_RECOMMENDATION_THRESHOLD = 5  # Minimum cost in dollars to trigger recommendations


def get_current_month_costs():
    """Get current month's AWS costs from Cost Explorer"""
    try:
        ce_client = boto3.client("ce", region_name="us-east-1")

        # Get current month date range
        end_date = datetime.now().date()
        start_date = end_date.replace(day=1)

        response = ce_client.get_cost_and_usage(
            TimePeriod={
                "Start": start_date.strftime("%Y-%m-%d"),
                "End": end_date.strftime("%Y-%m-%d"),
            },
            Granularity="MONTHLY",
            Metrics=["BlendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        service_costs = {}
        total_cost = 0.0

        for result in response["ResultsByTime"]:
            for group in result["Groups"]:
                service = group["Keys"][0]
                cost = float(group["Metrics"]["BlendedCost"]["Amount"])
                if cost > 0:
                    service_costs[service] = cost
                    total_cost += cost

    except Exception as e:
        print(f"❌ Error retrieving cost data: {str(e)}")
        return {}, 0.0
    else:
        return service_costs, total_cost


def analyze_optimization_opportunities():  # noqa: C901, PLR0912, PLR0915
    """Analyze potential cost optimization opportunities"""
    opportunities = []

    # Check for unattached EBS volumes
    try:
        regions = ["us-east-1", "us-east-2", "us-west-1", "us-west-2", "eu-west-1", "eu-west-2"]
        unattached_volumes = 0
        unattached_cost = 0.0

        for region in regions:
            try:
                ec2 = boto3.client("ec2", region_name=region)
                volumes = ec2.describe_volumes()["Volumes"]

                for volume in volumes:
                    if not volume.get("Attachments"):
                        unattached_volumes += 1
                        size_gb = volume["Size"]
                        volume_type = volume["VolumeType"]

                        # Estimate monthly cost
                        if volume_type == "gp3":
                            monthly_cost = size_gb * 0.08
                        elif volume_type == "gp2":
                            monthly_cost = size_gb * 0.10
                        else:
                            monthly_cost = size_gb * 0.10

                        unattached_cost += monthly_cost
            except Exception as exc:
                print(f"⚠️  Failed to inspect EBS volumes in {region}: {exc}")

        if unattached_volumes > 0:
            opportunities.append(
                {
                    "category": "EBS Optimization",
                    "description": f"{unattached_volumes} unattached EBS volumes",
                    "potential_savings": unattached_cost,
                    "risk": "Low",
                    "action": "Delete unused volumes after verification",
                }
            )
    except:
        pass

    # Check for unused Elastic IPs
    try:
        elastic_ips = 0
        for region in [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
        ]:
            try:
                ec2 = boto3.client("ec2", region_name=region)
                addresses = ec2.describe_addresses()["Addresses"]

                for address in addresses:
                    if not address.get("InstanceId"):
                        elastic_ips += 1
            except Exception as exc:
                print(f"⚠️  Failed to inspect Elastic IPs in {region}: {exc}")

        if elastic_ips > 0:
            opportunities.append(
                {
                    "category": "VPC Optimization",
                    "description": f"{elastic_ips} unattached Elastic IPs",
                    "potential_savings": elastic_ips * 3.60,
                    "risk": "Low",
                    "action": "Release unused Elastic IPs",
                }
            )
    except:
        pass

    # Check for old snapshots
    try:
        old_snapshots = 0
        snapshot_cost = 0.0
        cutoff_date = datetime.now() - timedelta(days=90)

        for region in ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]:
            try:
                ec2 = boto3.client("ec2", region_name=region)
                snapshots = ec2.describe_snapshots(OwnerIds=["self"])["Snapshots"]

                for snapshot in snapshots:
                    if snapshot["StartTime"].replace(tzinfo=None) < cutoff_date:
                        old_snapshots += 1
                        size_gb = snapshot.get("VolumeSize", 0)
                        snapshot_cost += size_gb * 0.05
            except Exception as exc:
                print(f"⚠️  Failed to inspect snapshots in {region}: {exc}")

        if old_snapshots > 0:
            opportunities.append(
                {
                    "category": "Snapshot Optimization",
                    "description": f"{old_snapshots} snapshots older than 90 days",
                    "potential_savings": snapshot_cost,
                    "risk": "Medium",
                    "action": "Review and delete unnecessary old snapshots",
                }
            )
    except:
        pass

    return opportunities


def get_completed_cleanups():
    """Get list of completed cleanup actions to avoid duplicate recommendations"""
    cleanup_log_path = os.path.join("config", "cleanup_log.json")
    completed_services = set()

    try:
        if os.path.exists(cleanup_log_path):
            with open(cleanup_log_path, "r") as f:
                log_data = json.load(f)
                for action in log_data.get("cleanup_actions", []):
                    if action.get("status") == "completed":
                        completed_services.add(action.get("service", "").lower())
    except Exception as e:
        print(f"⚠️  Could not read cleanup log: {e}")

    return completed_services


def get_service_recommendations(service_costs):  # noqa: C901, PLR0912
    """Get specific recommendations based on current service usage"""
    recommendations = []
    total_cost = sum(service_costs.values())
    completed_cleanups = get_completed_cleanups()

    # High-cost services recommendations
    for service, cost in sorted(service_costs.items(), key=lambda x: x[1], reverse=True)[:8]:
        if cost > COST_RECOMMENDATION_THRESHOLD:
            percentage = (cost / total_cost) * 100

            if "S3" in service.upper() or "STORAGE" in service.upper():
                recommendations.append(f"💡 {service}: ${cost:.2f}/month ({percentage:.1f}%)")
                recommendations.append(
                    "   📋 Implement lifecycle policies or Glacier transitions for infrequently accessed data"
                )
                recommendations.append(
                    "   🔧 Action: Review objects older than 30 days and move cold data to IA/Glacier classes"
                )

            elif "EC2" in service.upper():
                recommendations.append(f"💡 {service}: ${cost:.2f}/month ({percentage:.1f}%)")
                recommendations.append(
                    "   📋 Consider Reserved or Savings Plans for predictable compute usage"
                )
                recommendations.append(
                    "   🔧 Action: Analyze utilization metrics and match steady workloads with discounted capacity"
                )

            elif "RDS" in service.upper() or "DATABASE" in service.upper():
                recommendations.append(f"💡 {service}: ${cost:.2f}/month ({percentage:.1f}%)")
                recommendations.append(
                    "   📋 Review DB instance sizing, storage type, and idle clusters; Aurora Serverless may fit bursty usage"
                )
                recommendations.append(
                    "   🔧 Action: Monitor CPU/memory and storage metrics, then right-size or pause unused databases"
                )

            elif "LIGHTSAIL" in service.upper():
                if "lightsail" in completed_cleanups:
                    recommendations.append(f"✅ {service}: ${cost:.2f}/month ({percentage:.1f}%)")
                    recommendations.append(
                        "   📋 Lightsail cleanup previously completed; monitor for residual billing only"
                    )
                    recommendations.append(
                        "   🔧 Status: No action needed unless new resources appear"
                    )
                else:
                    recommendations.append(f"💡 {service}: ${cost:.2f}/month ({percentage:.1f}%)")
                    recommendations.append(
                        "   📋 Lightsail resources detected - remove instances, databases, or static IPs to stop charges"
                    )
                    recommendations.append(
                        "   🔧 Action: Run python cost_toolkit/scripts/cleanup/aws_lightsail_cleanup.py"
                    )

            elif "GLOBAL ACCELERATOR" in service.upper():
                recommendations.append(f"💡 {service}: ${cost:.2f}/month ({percentage:.1f}%)")
                recommendations.append(
                    "   📋 Global Accelerator is running; validate whether the accelerator still serves traffic"
                )
                recommendations.append(
                    "   🔧 Action: Review listeners/endpoints and disable unused accelerators"
                )

            elif "VPC" in service.upper() or "PRIVATE CLOUD" in service.upper():
                recommendations.append(f"💡 {service}: ${cost:.2f}/month ({percentage:.1f}%)")
                recommendations.append(
                    "   📋 VPC charges often originate from NAT Gateways or unattached Elastic IPs"
                )
                recommendations.append(
                    "   🔧 Action: Audit gateway usage and release unused Elastic IPs"
                )

            elif "CLOUDWATCH" in service.upper():
                recommendations.append(f"💡 {service}: ${cost:.2f}/month ({percentage:.1f}%)")
                recommendations.append(
                    "   📋 Review log retention and custom metrics to avoid storing data indefinitely"
                )
                recommendations.append(
                    "   🔧 Action: Set retention to 30-90 days and remove unused canaries/metrics"
                )

            else:
                recommendations.append(f"💡 {service}: ${cost:.2f}/month ({percentage:.1f}%)")
                recommendations.append(
                    f"   📋 Review usage patterns and consider optimization opportunities"
                )

    return recommendations


def run_quick_audit():  # noqa: PLR0912
    """Run a quick audit using existing scripts"""
    print("🔍 Running Quick Resource Audit...")
    print("=" * 60)

    audit_scripts = [
        ("EBS Audit", os.path.join(SCRIPTS_DIR, "audit", "aws_ebs_audit.py")),
        ("VPC Audit", os.path.join(SCRIPTS_DIR, "audit", "aws_vpc_audit.py")),
    ]

    for name, script_path in audit_scripts:
        if os.path.exists(script_path):
            print(f"\n📊 {name}:")
            try:
                result = subprocess.run(
                    [sys.executable, script_path], capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    # Extract key information from output
                    lines = result.stdout.split("\n")
                    summary_lines = []
                    for line in lines:
                        if any(
                            keyword in line
                            for keyword in [
                                "Total",
                                "Found",
                                "RECOMMENDATIONS",
                                "monthly cost",
                                "snapshots",
                                "volumes",
                            ]
                        ):
                            summary_lines.append(line.strip())

                    # Show last 5 most relevant lines
                    for line in summary_lines[-5:]:
                        if line:
                            print(f"  {line}")
                else:
                    print(f"  ⚠️ Script failed: {result.stderr.strip()}")
            except subprocess.TimeoutExpired:
                print(f"  ⚠️ Audit timed out - try running manually: python3 {script_path}")
            except Exception as e:
                print(f"  ⚠️ Error running audit: {str(e)}")
        else:
            print(f"  ⚠️ Script not found: {script_path}")


def report_lightsail_cost_breakdown():
    """Show the current month's Lightsail spend grouped by usage type."""
    print("\n🔎 LIGHTSAIL COST BREAKDOWN")
    print("=" * 60)
    try:
        ce_client = boto3.client("ce", region_name="us-east-1")
        today = datetime.now(timezone.utc).date()
        start = today.replace(day=1)
        response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start.strftime("%Y-%m-%d"), "End": today.strftime("%Y-%m-%d")},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            Filter={"Dimensions": {"Key": "SERVICE", "Values": ["Amazon Lightsail"]}},
            GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
        )
        rows = []
        total = 0.0
        for result in response.get("ResultsByTime", []):
            for group in result.get("Groups", []):
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                if amount <= 0:
                    continue
                total += amount
                rows.append((group["Keys"][0], amount))
        if not rows:
            print("No Lightsail spend recorded so far this month.")
            return
        print(f"Total month-to-date Lightsail charges: ${total:.2f}")
        for usage, amount in sorted(rows, key=lambda x: x[1], reverse=True):
            print(f"  {usage}: ${amount:.2f}")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Unable to fetch Lightsail cost breakdown: {exc}")


def main():  # noqa: PLR0915
    """Main function to display AWS cost overview"""
    print("AWS Cost Management Overview")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Setup credentials
    setup_aws_credentials()

    # Get current costs
    print("\n💰 CURRENT MONTH COSTS")
    print("=" * 60)

    service_costs, total_cost = get_current_month_costs()

    if total_cost > 0:
        print(f"Total AWS Spend (Month-to-Date): ${total_cost:.2f}")
        print("\nTop Services by Cost:")

        sorted_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)
        for service, cost in sorted_services[:10]:
            percentage = (cost / total_cost) * 100
            print(f"  {service:<30} ${cost:>8.2f} ({percentage:>5.1f}%)")
    else:
        print("No cost data available or unable to retrieve costs.")

    # Analyze optimization opportunities
    print("\n🎯 OPTIMIZATION OPPORTUNITIES")
    print("=" * 60)

    opportunities = analyze_optimization_opportunities()
    total_potential_savings = sum(opp["potential_savings"] for opp in opportunities)

    if opportunities:
        print(f"Total Potential Monthly Savings: ${total_potential_savings:.2f}")
        print("\nIdentified Opportunities:")

        for opp in sorted(opportunities, key=lambda x: x["potential_savings"], reverse=True):
            print(f"\n📋 {opp['category']}")
            print(f"   Description: {opp['description']}")
            print(f"   Potential Savings: ${opp['potential_savings']:.2f}/month")
            print(f"   Risk Level: {opp['risk']}")
            print(f"   Recommended Action: {opp['action']}")
    else:
        print("No immediate optimization opportunities identified.")

    # Service-specific recommendations
    if service_costs:
        print("\n💡 SERVICE-SPECIFIC RECOMMENDATIONS")
        print("=" * 60)

        recommendations = get_service_recommendations(service_costs)
        if recommendations:
            for rec in recommendations:
                print(rec)
        else:
            print("No specific service recommendations at this time.")

    # Quick audit
    print("\n")
    run_quick_audit()
    report_lightsail_cost_breakdown()

    # Next steps
    print("\n🚀 RECOMMENDED NEXT STEPS")
    print("=" * 60)
    print("1. Review optimization opportunities above")
    print("2. Run detailed audits: python3 scripts/audit/aws_ebs_audit.py")
    print("3. Generate full billing report: python3 scripts/billing/aws_billing_report.py")
    print("4. Start with low-risk optimizations first")
    print("5. Set up AWS Cost Budgets and Alerts")

    print("\n📚 AVAILABLE TOOLS")
    print("=" * 60)
    print("• Audit Scripts: scripts/audit/")
    print("• Cleanup Scripts: scripts/cleanup/")
    print("• Migration Tools: scripts/migration/")
    print("• Billing Reports: scripts/billing/")

    print(f"\n💾 For detailed documentation, see: README.md")
    print("=" * 80)


if __name__ == "__main__":
    main()
