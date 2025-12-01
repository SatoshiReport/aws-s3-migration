#!/usr/bin/env python3
"""
AWS Cost Overview CLI
Main entry point for cost overview and reporting functionality.
"""

import os
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from ..scripts.aws_utils import setup_aws_credentials
from .audit import report_lightsail_cost_breakdown, run_quick_audit
from .optimization import analyze_optimization_opportunities
from .recommendations import get_service_recommendations

SCRIPT_ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_ROOT)
SCRIPTS_DIR = os.path.join(PARENT_DIR, "scripts")


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

    except ClientError as e:
        raise RuntimeError(
            f"Failed to retrieve current month costs from AWS Cost Explorer: {str(e)}"
        ) from e
    return service_costs, total_cost


def _print_header():
    """Print overview header."""
    print("AWS Cost Management Overview")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


def _print_current_costs(service_costs, total_cost):
    """Print current month costs."""
    print("\n💰 CURRENT MONTH COSTS")
    print("=" * 60)

    if total_cost > 0:
        print(f"Total AWS Spend (Month-to-Date): ${total_cost:.2f}")
        print("\nTop Services by Cost:")
        sorted_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)
        for service, cost in sorted_services[:10]:
            percentage = (cost / total_cost) * 100
            print(f"  {service:<30} ${cost:>8.2f} ({percentage:>5.1f}%)")
    else:
        print("No cost data available or unable to retrieve costs.")


def _print_optimization_opportunities(opportunities):
    """Print optimization opportunities."""
    print("\n🎯 OPTIMIZATION OPPORTUNITIES")
    print("=" * 60)

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


def _print_service_recommendations(service_costs):
    """Print service-specific recommendations."""
    if not service_costs:
        return

    print("\n💡 SERVICE-SPECIFIC RECOMMENDATIONS")
    print("=" * 60)

    recommendations = get_service_recommendations(service_costs)
    if recommendations:
        for rec in recommendations:
            print(rec)
    else:
        print("No specific service recommendations at this time.")


def _print_next_steps_and_tools():
    """Print next steps and available tools."""
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

    print("\n💾 For detailed documentation, see: README.md")
    print("=" * 80)


def main():
    """Main function to display AWS cost overview"""
    _print_header()
    setup_aws_credentials()

    service_costs, total_cost = get_current_month_costs()
    _print_current_costs(service_costs, total_cost)

    opportunities = analyze_optimization_opportunities()
    _print_optimization_opportunities(opportunities)

    _print_service_recommendations(service_costs)

    print("\n")
    run_quick_audit(SCRIPTS_DIR)
    report_lightsail_cost_breakdown()

    _print_next_steps_and_tools()


if __name__ == "__main__":
    main()
