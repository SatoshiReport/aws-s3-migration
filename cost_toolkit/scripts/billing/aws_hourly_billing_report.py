#!/usr/bin/env python3
"""
AWS Hourly Billing Report Script
Gets detailed billing information for the current hour to identify active cost-generating services.
"""

import os
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv


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


def get_hourly_date_range():
    """Get the date range for the current hour"""
    now = datetime.now()
    # Start of current hour
    start_time = now.replace(minute=0, second=0, microsecond=0)
    # Current time (end of range)
    end_time = now

    return start_time.strftime("%Y-%m-%dT%H:%M:%S"), end_time.strftime("%Y-%m-%dT%H:%M:%S")


def get_today_date_range():
    """Get the date range for today (for comparison)"""
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # AWS Cost Explorer requires dates in YYYY-MM-DD format, not datetime
    end_of_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    return start_of_day.strftime("%Y-%m-%d"), end_of_day.strftime("%Y-%m-%d")


def get_hourly_billing_data():
    """Retrieve hourly cost and usage data from AWS Cost Explorer"""
    setup_aws_credentials()

    # Create Cost Explorer client
    ce_client = boto3.client("ce", region_name="us-east-1")

    start_date, end_date = get_today_date_range()

    print(f"Retrieving hourly billing data for today: {start_date}")
    print("=" * 80)

    try:
        # Get cost and usage data grouped by service with hourly granularity
        hourly_response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="HOURLY",
            Metrics=["BlendedCost", "UsageQuantity"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        # Get daily summary for comparison
        daily_response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="DAILY",
            Metrics=["BlendedCost", "UsageQuantity"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

    except ClientError as e:
        print(f"Error retrieving billing data: {str(e)}")
        return None, None

    return hourly_response, daily_response


def _process_daily_data(daily_data):
    """Process daily billing data."""
    daily_service_costs = defaultdict(float)
    if daily_data and "ResultsByTime" in daily_data:
        for result in daily_data["ResultsByTime"]:
            for group in result["Groups"]:
                service = group["Keys"][0] if group["Keys"] else "Unknown Service"
                cost_amount = float(group["Metrics"]["BlendedCost"]["Amount"])
                daily_service_costs[service] += cost_amount
    return daily_service_costs


def _process_hourly_data(hourly_data, current_hour):
    """Process hourly billing data."""
    hourly_service_costs = defaultdict(list)
    current_hour_costs = defaultdict(float)

    for result in hourly_data["ResultsByTime"]:
        period_start = result["TimePeriod"]["Start"]
        period_end = result["TimePeriod"]["End"]

        hour_start = datetime.fromisoformat(period_start.replace("Z", "+00:00"))

        for group in result["Groups"]:
            service = group["Keys"][0] if group["Keys"] else "Unknown Service"
            cost_amount = float(group["Metrics"]["BlendedCost"]["Amount"])

            if cost_amount > 0:
                hourly_service_costs[service].append(
                    {
                        "hour": hour_start,
                        "cost": cost_amount,
                        "period_start": period_start,
                        "period_end": period_end,
                    }
                )

                if hour_start.hour == current_hour.hour:
                    current_hour_costs[service] += cost_amount

    return hourly_service_costs, current_hour_costs


def _display_current_hour_section(current_hour_costs, current_hour, now, daily_service_costs):
    """Display current hour active services section."""
    if current_hour_costs:
        print(
            f"\n🔥 ACTIVE SERVICES IN CURRENT HOUR "
            f"({current_hour.strftime('%H:00')} - {now.strftime('%H:%M')})"
        )
        print("-" * 80)

        current_hour_total = 0
        sorted_current = sorted(current_hour_costs.items(), key=lambda x: x[1], reverse=True)

        for service, cost in sorted_current:
            current_hour_total += cost
            daily_cost = daily_service_costs.get(service, 0)

            hourly_rate = ""
            if daily_cost > 0:
                hours_elapsed = now.hour + (now.minute / 60.0)
                if hours_elapsed > 0:
                    estimated_daily = (daily_cost / hours_elapsed) * 24
                    hourly_rate = f" (Est. ${estimated_daily:.4f}/day)"

            print(f"   💰 {service:<50} ${cost:.6f}{hourly_rate}")

        print(f"\n   📊 Current Hour Total: ${current_hour_total:.6f}")
    else:
        print(
            f"\n✅ NO ACTIVE SERVICES IN CURRENT HOUR "
            f"({current_hour.strftime('%H:00')} - {now.strftime('%H:%M')})"
        )


def _display_daily_summary(daily_service_costs, hourly_service_costs):
    """Display today's cost summary by service."""
    if daily_service_costs:
        print("\n📈 TODAY'S COST SUMMARY BY SERVICE")
        print("-" * 80)

        daily_total = 0
        sorted_daily = sorted(daily_service_costs.items(), key=lambda x: x[1], reverse=True)

        for service, cost in sorted_daily:
            daily_total += cost

            hourly_breakdown = ""
            if service in hourly_service_costs:
                hours_with_cost = len([h for h in hourly_service_costs[service] if h["cost"] > 0])
                if hours_with_cost > 0:
                    avg_hourly = cost / hours_with_cost
                    hourly_breakdown = f" ({hours_with_cost}h active, avg ${avg_hourly:.6f}/h)"

            print(f"   📊 {service:<50} ${cost:.6f}{hourly_breakdown}")

        print(f"\n   💰 Today's Total: ${daily_total:.6f}")


def _display_hourly_trends(hourly_service_costs, daily_service_costs):
    """Display hourly cost trends for top services."""
    if hourly_service_costs:
        print("\n⏰ HOURLY COST TRENDS (Top Services)")
        print("-" * 80)

        top_services = sorted(daily_service_costs.items(), key=lambda x: x[1], reverse=True)[:5]

        for service, daily_cost in top_services:
            if service in hourly_service_costs:
                print(f"\n🔍 {service} (${daily_cost:.6f} today)")

                hourly_costs = hourly_service_costs[service]
                hourly_costs.sort(key=lambda x: x["hour"])

                for hour_data in hourly_costs[-12:]:
                    hour_str = hour_data["hour"].strftime("%H:00")
                    cost = hour_data["cost"]
                    if cost > 0:
                        bar_length = min(int(cost * 1000000), 50)
                        bar = "█" * bar_length
                        print(f"   {hour_str}: ${cost:.6f} {bar}")


def _display_optimization_insights(current_hour_costs, daily_service_costs):
    """Display cost optimization insights."""
    print("\n💡 COST OPTIMIZATION INSIGHTS")
    print("-" * 80)

    if current_hour_costs:
        print("⚠️  Services currently generating costs:")
        for service, cost in sorted(current_hour_costs.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {service}: ${cost:.6f} this hour")
        print("\n🎯 Focus cleanup efforts on these active services")
    else:
        print("✅ No services generating costs in the current hour")
        print("🎉 Your cleanup efforts are working!")

    earlier_services = set(daily_service_costs.keys()) - set(current_hour_costs.keys())
    if earlier_services:
        print("\n📝 Services active earlier today but not in current hour:")
        for service in sorted(earlier_services):
            daily_cost = daily_service_costs[service]
            print(f"   • {service}: ${daily_cost:.6f} (may be already cleaned up)")


def format_hourly_billing_report(hourly_data, daily_data):
    """Format and display the hourly billing report"""
    if not hourly_data or "ResultsByTime" not in hourly_data:
        print("No hourly billing data available")
        return

    now = datetime.now()
    current_hour = now.replace(minute=0, second=0, microsecond=0)

    daily_service_costs = _process_daily_data(daily_data)
    hourly_service_costs, current_hour_costs = _process_hourly_data(hourly_data, current_hour)

    print(f"\nHOURLY AWS BILLING REPORT - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 120)

    _display_current_hour_section(current_hour_costs, current_hour, now, daily_service_costs)
    _display_daily_summary(daily_service_costs, hourly_service_costs)
    _display_hourly_trends(hourly_service_costs, daily_service_costs)
    _display_optimization_insights(current_hour_costs, daily_service_costs)


def main():
    """Main execution function"""
    clear_screen()

    print("AWS HOURLY BILLING REPORT")
    print("=" * 50)
    print("Real-time cost analysis to identify active services")
    print()

    if not setup_aws_credentials():
        return

    # Get billing data
    hourly_data, daily_data = get_hourly_billing_data()

    if hourly_data and daily_data:
        format_hourly_billing_report(hourly_data, daily_data)
    else:
        print("Failed to retrieve billing data")

    print("\n" + "=" * 120)
    print("💡 Use this report to identify services still generating costs")
    print("🎯 Focus cleanup efforts on services active in the current hour")
    print("📊 Compare with monthly report to track cleanup progress")


if __name__ == "__main__":
    main()
