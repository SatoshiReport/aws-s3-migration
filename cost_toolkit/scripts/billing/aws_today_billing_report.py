#!/usr/bin/env python3
"""
AWS Today's Billing Report Script
Gets detailed billing information for today to identify currently active cost-generating services.
"""

from collections import defaultdict
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

from cost_toolkit.common.credential_utils import check_aws_credentials
from cost_toolkit.common.terminal_utils import clear_screen

# Constants for cost analysis thresholds and calculations
MIN_TREND_DATA_POINTS = 2  # Minimum number of data points needed for trend analysis
MINIMUM_COST_THRESHOLD = 0.001  # Minimum cost ($) to display detailed breakdown


def get_today_date_range():
    """Get today's date range (start today, end tomorrow)."""
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
    check_aws_credentials()

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

    except ClientError as e:
        print(f"Error retrieving billing data: {str(e)}")
        return None, None, None

    return today_response, trend_response, usage_response


def _process_today_data(today_data):
    """Process today's billing data."""
    today_service_costs = defaultdict(float)
    if today_data["ResultsByTime"]:
        for result in today_data["ResultsByTime"]:
            for group in result["Groups"]:
                service = group["Keys"][0] if group["Keys"] else "Unknown Service"
                cost_amount = float(group["Metrics"]["BlendedCost"]["Amount"])
                today_service_costs[service] += cost_amount
    return today_service_costs


def _process_trend_data(trend_data):
    """Process trend data for comparison."""
    daily_trends = defaultdict(list)
    if trend_data and "ResultsByTime" in trend_data:
        for result in trend_data["ResultsByTime"]:
            date = result["TimePeriod"]["Start"]
            for group in result["Groups"]:
                service = group["Keys"][0] if group["Keys"] else "Unknown Service"
                cost_amount = float(group["Metrics"]["BlendedCost"]["Amount"])
                daily_trends[service].append({"date": date, "cost": cost_amount})
    return daily_trends


def _process_usage_details(usage_data):
    """Process detailed usage data."""
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
    return service_usage_details


def _calculate_trend_indicator(service, daily_trends, cost):
    """Calculate trend indicator for a service."""
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
    return trend_indicator


def _calculate_hourly_info(cost, now):
    """Calculate hourly rate and projection."""
    hours_elapsed = now.hour + (now.minute / 60.0)
    if hours_elapsed > 0:
        hourly_rate = cost / hours_elapsed
        daily_projection = hourly_rate * 24
        return f" (${hourly_rate:.6f}/hr, proj. ${daily_projection:.6f}/day)"
    return ""


def _display_service_usage_details(service, service_usage_details, cost):
    """Display detailed usage breakdown for a service."""
    if service in service_usage_details and cost > MINIMUM_COST_THRESHOLD:
        usage_details = sorted(
            service_usage_details[service], key=lambda x: x["cost"], reverse=True
        )
        for detail in usage_details[:3]:
            usage_type = detail["usage_type"]
            usage_cost = detail["cost"]
            quantity = detail["quantity"]
            unit = detail["unit"]

            if usage_cost > 0:
                print(f"      └─ {usage_type:<40} ${usage_cost:.6f} ({quantity:.2f} {unit})")


def _display_active_services(today_service_costs, daily_trends, service_usage_details, now):
    """Display active services generating costs today."""
    if today_service_costs:
        total_today = sum(today_service_costs.values())
        print(f"\n🔥 SERVICES GENERATING COSTS TODAY (${total_today:.6f} total)")
        print("-" * 80)

        sorted_today = sorted(today_service_costs.items(), key=lambda x: x[1], reverse=True)

        for service, cost in sorted_today:
            trend_indicator = _calculate_trend_indicator(service, daily_trends, cost)
            hourly_info = _calculate_hourly_info(cost, now)

            print(f"   💰 {service:<50} ${cost:.6f}{hourly_info}{trend_indicator}")
            _display_service_usage_details(service, service_usage_details, cost)
    else:
        print("\n✅ NO SERVICES GENERATING COSTS TODAY")
        print("🎉 Excellent! Your cleanup efforts have been very effective!")


def _display_trend_analysis(daily_trends, today_service_costs):
    """Display 3-day cost trends."""
    if daily_trends:
        print("\n📈 3-DAY COST TRENDS")
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
                        bar_length = min(int(cost * 10000), 50)
                        cost_bar = "█" * bar_length
                        print(f"   {date}: ${cost:.6f} {cost_bar}")


def _get_service_recommendation(service):
    """Get optimization recommendation for a service."""
    service_upper = service.upper()
    if "EC2" in service_upper:
        return "      💡 Check for running instances, unused volumes, or Elastic IPs"
    if "RDS" in service_upper:
        return "      💡 Check for running databases or unused snapshots"
    if "S3" in service_upper:
        return "      💡 Check for storage costs or data transfer charges"
    if "VPC" in service_upper:
        return "      💡 Check for NAT Gateways or VPC endpoints"
    if "ROUTE" in service_upper:
        return "      💡 Check for hosted zones or DNS queries"
    return None


def _display_optimization_insights(today_service_costs):
    """Display cost optimization insights."""
    print("\n💡 COST OPTIMIZATION INSIGHTS")
    print("-" * 80)

    if today_service_costs:
        print("⚠️  Services currently generating costs (focus cleanup here):")
        active_services = sorted(today_service_costs.items(), key=lambda x: x[1], reverse=True)

        for service, cost in active_services:
            if cost > MINIMUM_COST_THRESHOLD:
                print(f"   🎯 {service}: ${cost:.6f} today")

                recommendation = _get_service_recommendation(service)
                if recommendation:
                    print(recommendation)

        print(f"\n🎯 Total daily cost to eliminate: ${sum(today_service_costs.values()):.6f}")
    else:
        print("✅ No active cost-generating services found today")
        print("🎉 Your AWS account is optimally configured!")

    if today_service_costs:
        total_today = sum(today_service_costs.values())
        estimated_monthly = total_today * 30
        print(f"\n📊 MONTHLY PROJECTION: ${estimated_monthly:.2f} (if current rate continues)")


def format_today_billing_report(today_data, trend_data, usage_data):
    """Format and display today's billing report"""
    if not today_data or "ResultsByTime" not in today_data:
        print("No billing data available for today")
        return

    now = datetime.now()

    today_service_costs = _process_today_data(today_data)
    daily_trends = _process_trend_data(trend_data)
    service_usage_details = _process_usage_details(usage_data)

    print(f"\nTODAY'S AWS BILLING REPORT - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 120)

    _display_active_services(today_service_costs, daily_trends, service_usage_details, now)
    _display_trend_analysis(daily_trends, today_service_costs)
    _display_optimization_insights(today_service_costs)


def main():
    """Main execution function"""
    clear_screen()

    print("AWS TODAY'S BILLING REPORT")
    print("=" * 50)
    print("Real-time cost analysis for today's active services")
    print()

    if not check_aws_credentials():
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
