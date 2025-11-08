#!/usr/bin/env python3
"""
AWS Today's Billing Report Script
Gets detailed billing information for today to identify currently active cost-generating services.
"""

import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta

import boto3
import botocore.exceptions
from dotenv import load_dotenv

# Constants for cost analysis thresholds and calculations
MIN_TREND_DATA_POINTS = 2  # Minimum number of data points needed for trend analysis
MINIMUM_COST_THRESHOLD = 0.001  # Minimum cost ($) to display detailed breakdown


def clear_screen():
    """Clear the terminal screen without invoking a shell."""
    try:
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "cls"], check=False)
        else:
            subprocess.run(["clear"], check=False)
    except FileNotFoundError:
        print("\033c", end="")


def setup_aws_credentials():
    """Load AWS credentials from .env file"""
    # Load environment variables from .env file
    load_dotenv(os.path.expanduser("~/.env"))

    # Check if credentials are loaded
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        print("⚠️  AWS credentials not found in ~/.env file.")
        print("Please ensure ~/.env contains:")
        print("  AWS_ACCESS_KEY_ID=your-access-key")
        print("  AWS_SECRET_ACCESS_KEY=your-secret-key")
        print("  AWS_DEFAULT_REGION=us-east-1")
        return False

    return True


def get_today_date_range():
    """Get the date range for today"""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    return today, tomorrow


def get_recent_days_range():
    """Get the date range for the last 3 days for trend analysis"""
    now = datetime.now()
    three_days_ago = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    return three_days_ago, tomorrow


def get_today_billing_data():
    """Retrieve today's cost and usage data from AWS Cost Explorer"""
    setup_aws_credentials()

    # Create Cost Explorer client
    ce_client = boto3.client("ce", region_name="us-east-1")

    today_start, today_end = get_today_date_range()
    recent_start, recent_end = get_recent_days_range()

    print(f"Retrieving billing data for today: {today_start}")
    print("=" * 80)

    try:
        # Get today's cost data grouped by service
        today_response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": today_start, "End": today_end},
            Granularity="DAILY",
            Metrics=["BlendedCost", "UsageQuantity"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        # Get recent days for trend analysis
        trend_response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": recent_start, "End": recent_end},
            Granularity="DAILY",
            Metrics=["BlendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        # Get detailed usage breakdown for today
        usage_response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": today_start, "End": today_end},
            Granularity="DAILY",
            Metrics=["BlendedCost", "UsageQuantity"],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "USAGE_TYPE"},
            ],
        )

    except Exception as e:
        print(f"Error retrieving billing data: {str(e)}")
        return None, None, None

    else:
        return today_response, trend_response, usage_response


def format_today_billing_report(today_data, trend_data, usage_data):  # noqa: C901, PLR0912, PLR0915
    """Format and display today's billing report"""
    if not today_data or "ResultsByTime" not in today_data:
        print("No billing data available for today")
        return

    now = datetime.now()

    # Process today's data
    today_service_costs = defaultdict(float)
    if today_data["ResultsByTime"]:
        for result in today_data["ResultsByTime"]:
            for group in result["Groups"]:
                service = group["Keys"][0] if group["Keys"] else "Unknown Service"
                cost_amount = float(group["Metrics"]["BlendedCost"]["Amount"])
                today_service_costs[service] += cost_amount

    # Process trend data for comparison
    daily_trends = defaultdict(list)
    if trend_data and "ResultsByTime" in trend_data:
        for result in trend_data["ResultsByTime"]:
            date = result["TimePeriod"]["Start"]
            for group in result["Groups"]:
                service = group["Keys"][0] if group["Keys"] else "Unknown Service"
                cost_amount = float(group["Metrics"]["BlendedCost"]["Amount"])
                daily_trends[service].append({"date": date, "cost": cost_amount})

    # Process detailed usage data
    service_usage_details = defaultdict(list)
    if usage_data and "ResultsByTime" in usage_data:
        for result in usage_data["ResultsByTime"]:
            for group in result["Groups"]:
                keys = group["Keys"]
                service = keys[0] if len(keys) > 0 else "Unknown Service"
                usage_type = keys[1] if len(keys) > 1 else "Unknown Usage"

                cost_amount = float(group["Metrics"]["BlendedCost"]["Amount"])
                usage_quantity = float(group["Metrics"]["UsageQuantity"]["Amount"])
                usage_unit = group["Metrics"]["UsageQuantity"]["Unit"]

                if cost_amount > 0:
                    service_usage_details[service].append(
                        {
                            "usage_type": usage_type,
                            "cost": cost_amount,
                            "quantity": usage_quantity,
                            "unit": usage_unit,
                        }
                    )

    # Display report
    print(f"\nTODAY'S AWS BILLING REPORT - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 120)

    # Active services today
    if today_service_costs:
        total_today = sum(today_service_costs.values())
        print(f"\n🔥 SERVICES GENERATING COSTS TODAY (${total_today:.6f} total)")
        print("-" * 80)

        sorted_today = sorted(today_service_costs.items(), key=lambda x: x[1], reverse=True)

        for service, cost in sorted_today:
            # Calculate trend
            trend_indicator = ""
            if service in daily_trends and len(daily_trends[service]) >= MIN_TREND_DATA_POINTS:
                recent_costs = [d["cost"] for d in daily_trends[service]]
                if len(recent_costs) >= MIN_TREND_DATA_POINTS:
                    yesterday_cost = recent_costs[-2] if len(recent_costs) > 1 else 0
                    if cost > yesterday_cost * 1.1:
                        trend_indicator = " 📈 INCREASING"
                    elif cost < yesterday_cost * 0.9:
                        trend_indicator = " 📉 DECREASING"
                    else:
                        trend_indicator = " ➡️ STABLE"

            # Estimate hourly rate
            hours_elapsed = now.hour + (now.minute / 60.0)
            if hours_elapsed > 0:
                hourly_rate = cost / hours_elapsed
                daily_projection = hourly_rate * 24
                hourly_info = f" (${hourly_rate:.6f}/hr, proj. ${daily_projection:.6f}/day)"
            else:
                hourly_info = ""

            print(f"   💰 {service:<50} ${cost:.6f}{hourly_info}{trend_indicator}")

            # Show detailed usage breakdown for top services
            if (
                service in service_usage_details and cost > MINIMUM_COST_THRESHOLD
            ):  # Show details for services above minimum threshold
                usage_details = sorted(
                    service_usage_details[service], key=lambda x: x["cost"], reverse=True
                )
                for detail in usage_details[:3]:  # Show top 3 usage types
                    usage_type = detail["usage_type"]
                    usage_cost = detail["cost"]
                    quantity = detail["quantity"]
                    unit = detail["unit"]

                    if usage_cost > 0:
                        print(
                            f"      └─ {usage_type:<40} ${usage_cost:.6f} ({quantity:.2f} {unit})"
                        )
    else:
        print(f"\n✅ NO SERVICES GENERATING COSTS TODAY")
        print("🎉 Excellent! Your cleanup efforts have been very effective!")

    # Trend analysis
    if daily_trends:
        print(f"\n📈 3-DAY COST TRENDS")
        print("-" * 80)

        for service in sorted(
            today_service_costs.keys(), key=lambda x: today_service_costs[x], reverse=True
        )[:5]:
            if service in daily_trends:
                print(f"\n📊 {service}")
                trends = sorted(daily_trends[service], key=lambda x: x["date"])
                for trend in trends:
                    date = trend["date"]
                    cost = trend["cost"]
                    if cost > 0:
                        bar_length = min(int(cost * 10000), 50)  # Scale for visualization
                        bar = "█" * bar_length
                        print(f"   {date}: ${cost:.6f} {bar}")

    # Cost optimization recommendations
    print(f"\n💡 COST OPTIMIZATION INSIGHTS")
    print("-" * 80)

    if today_service_costs:
        print("⚠️  Services currently generating costs (focus cleanup here):")
        active_services = sorted(today_service_costs.items(), key=lambda x: x[1], reverse=True)

        for service, cost in active_services:
            if cost > MINIMUM_COST_THRESHOLD:  # Focus on services with meaningful costs
                print(f"   🎯 {service}: ${cost:.6f} today")

                # Provide specific recommendations based on service
                if "EC2" in service.upper():
                    print(f"      💡 Check for running instances, unused volumes, or Elastic IPs")
                elif "RDS" in service.upper():
                    print(f"      💡 Check for running databases or unused snapshots")
                elif "S3" in service.upper():
                    print(f"      💡 Check for storage costs or data transfer charges")
                elif "VPC" in service.upper():
                    print(f"      💡 Check for NAT Gateways or VPC endpoints")
                elif "ROUTE" in service.upper():
                    print(f"      💡 Check for hosted zones or DNS queries")

        print(f"\n🎯 Total daily cost to eliminate: ${sum(today_service_costs.values()):.6f}")
    else:
        print("✅ No active cost-generating services found today")
        print("🎉 Your AWS account is optimally configured!")

    # Show estimated monthly impact
    if today_service_costs:
        total_today = sum(today_service_costs.values())
        estimated_monthly = total_today * 30
        print(f"\n📊 MONTHLY PROJECTION: ${estimated_monthly:.2f} (if current rate continues)")


def main():
    """Main execution function"""
    clear_screen()

    print("AWS TODAY'S BILLING REPORT")
    print("=" * 50)
    print("Real-time cost analysis for today's active services")
    print()

    if not setup_aws_credentials():
        return

    # Get billing data
    today_data, trend_data, usage_data = get_today_billing_data()

    if today_data:
        format_today_billing_report(today_data, trend_data, usage_data)
    else:
        print("Failed to retrieve billing data")

    print("\n" + "=" * 120)
    print("💡 Use this report to identify services actively generating costs today")
    print("🎯 Focus cleanup efforts on services with the highest daily costs")
    print("📊 Run regularly to track the impact of your optimization efforts")


if __name__ == "__main__":
    main()
