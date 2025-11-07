#!/usr/bin/env python3

import json
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError


def get_instance_details_in_region(region_name):
    """Get detailed information about EC2 instances in a region"""
    print(f"\n🔍 Auditing EC2 instances in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)
        cloudwatch = boto3.client("cloudwatch", region_name=region_name)

        # Get all instances
        response = ec2.describe_instances()

        instances = []
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                instances.append(instance)

        if not instances:
            print(f"✅ No EC2 instances found in {region_name}")
            return []

        region_summary = []

        for instance in instances:
            instance_id = instance["InstanceId"]
            instance_type = instance["InstanceType"]
            state = instance["State"]["Name"]
            launch_time = instance.get("LaunchTime")

            # Get instance name from tags
            name = "Unnamed"
            for tag in instance.get("Tags", []):
                if tag["Key"] == "Name":
                    name = tag["Value"]
                    break

            print(f"Instance: {instance_id} ({name})")
            print(f"  Type: {instance_type}")
            print(f"  State: {state}")
            print(f"  Launch Time: {launch_time}")

            # Get CPU utilization for the last 7 days
            try:
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(days=7)

                cpu_response = cloudwatch.get_metric_statistics(
                    Namespace="AWS/EC2",
                    MetricName="CPUUtilization",
                    Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,  # 1 hour periods
                    Statistics=["Average", "Maximum"],
                )

                if cpu_response["Datapoints"]:
                    # Sort by timestamp
                    datapoints = sorted(cpu_response["Datapoints"], key=lambda x: x["Timestamp"])
                    latest_datapoint = datapoints[-1]
                    avg_cpu = sum(dp["Average"] for dp in datapoints) / len(datapoints)
                    max_cpu = max(dp["Maximum"] for dp in datapoints)

                    print(f"  Last 7 days CPU usage:")
                    print(f"    Average: {avg_cpu:.1f}%")
                    print(f"    Maximum: {max_cpu:.1f}%")
                    print(
                        f"    Last recorded: {latest_datapoint['Timestamp']} ({latest_datapoint['Average']:.1f}%)"
                    )

                    # Determine usage level
                    if avg_cpu < 1:
                        usage_level = "🔴 VERY LOW (<1% avg)"
                    elif avg_cpu < 5:
                        usage_level = "🟡 LOW (<5% avg)"
                    elif avg_cpu < 20:
                        usage_level = "🟢 MODERATE (5-20% avg)"
                    else:
                        usage_level = "🔵 HIGH (>20% avg)"

                    print(f"    Usage Level: {usage_level}")
                else:
                    print(f"  ⚠️  No CPU metrics available (instance may be stopped)")
                    usage_level = "❓ NO DATA"

            except ClientError as e:
                print(f"  ❌ Error getting metrics: {e}")
                usage_level = "❓ ERROR"

            # Check network activity
            try:
                network_response = cloudwatch.get_metric_statistics(
                    Namespace="AWS/EC2",
                    MetricName="NetworkIn",
                    Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,
                    Statistics=["Sum"],
                )

                if network_response["Datapoints"]:
                    total_network_in = sum(dp["Sum"] for dp in network_response["Datapoints"])
                    print(f"  Network In (7 days): {total_network_in/1024/1024:.1f} MB")
                else:
                    print(f"  Network In: No data")

            except ClientError as e:
                print(f"  Network metrics error: {e}")

            # Estimate monthly cost based on instance type
            # Rough estimates for common instance types (us-east-1 pricing)
            cost_estimates = {
                "t2.nano": 4.18,
                "t2.micro": 8.35,
                "t2.small": 16.70,
                "t2.medium": 33.41,
                "t3.nano": 3.80,
                "t3.micro": 7.59,
                "t3.small": 15.18,
                "t3.medium": 30.37,
                "m5.large": 69.12,
                "m5.xlarge": 138.24,
                "c5.large": 61.56,
                "c5.xlarge": 123.12,
            }

            estimated_monthly_cost = cost_estimates.get(instance_type, 50.0)  # Default estimate
            if state == "running":
                print(f"  Estimated monthly cost: ${estimated_monthly_cost:.2f} (if running 24/7)")
            else:
                print(f"  Estimated monthly cost: $0 (currently {state})")

            instance_info = {
                "region": region_name,
                "instance_id": instance_id,
                "name": name,
                "instance_type": instance_type,
                "state": state,
                "launch_time": launch_time,
                "usage_level": usage_level,
                "estimated_monthly_cost": estimated_monthly_cost if state == "running" else 0,
            }

            region_summary.append(instance_info)
            print()

        return region_summary

    except ClientError as e:
        print(f"❌ Error auditing instances in {region_name}: {e}")
        return []


def main():
    print("AWS EC2 Usage Audit")
    print("=" * 80)
    print("Analyzing EC2 instances and their recent usage patterns...")

    # Focus on regions where we have Elastic IPs
    target_regions = ["us-east-1", "eu-west-2"]

    all_instances = []
    total_estimated_cost = 0

    for region in target_regions:
        instances = get_instance_details_in_region(region)
        all_instances.extend(instances)

        region_cost = sum(inst["estimated_monthly_cost"] for inst in instances)
        total_estimated_cost += region_cost

    # Summary
    print("\n" + "=" * 80)
    print("🎯 OVERALL SUMMARY")
    print("=" * 80)

    running_instances = [inst for inst in all_instances if inst["state"] == "running"]
    stopped_instances = [inst for inst in all_instances if inst["state"] == "stopped"]

    print(f"Total instances found: {len(all_instances)}")
    print(f"  🟢 Running: {len(running_instances)}")
    print(f"  🔴 Stopped: {len(stopped_instances)}")
    print(f"Estimated monthly cost for running instances: ${total_estimated_cost:.2f}")

    print(f"\n💡 OPTIMIZATION RECOMMENDATIONS:")

    # Analyze usage patterns
    low_usage_instances = [
        inst
        for inst in all_instances
        if "LOW" in inst.get("usage_level", "") or "VERY LOW" in inst.get("usage_level", "")
    ]

    if low_usage_instances:
        print(f"  🔴 {len(low_usage_instances)} instances with low CPU usage:")
        for inst in low_usage_instances:
            print(f"    - {inst['name']} ({inst['instance_id']}) in {inst['region']}")
            print(f"      Usage: {inst['usage_level']}")
            print(f"      Cost: ${inst['estimated_monthly_cost']:.2f}/month")

    print(f"\n📋 OPTIONS FOR COST REDUCTION:")
    print(f"  1. STOP instances when not needed (keeps data, stops compute charges)")
    print(f"  2. TERMINATE unused instances (deletes everything, stops all charges)")
    print(f"  3. DOWNSIZE over-provisioned instances to smaller types")
    print(f"  4. SCHEDULE instances to run only when needed")
    print(f"  5. RELEASE Elastic IPs for terminated instances")

    print(f"\n⚠️  IMPORTANT NOTES:")
    print(f"  - Stopping instances keeps EBS volumes (small storage cost continues)")
    print(f"  - Elastic IPs cost money whether instance is running or not")
    print(f"  - You can restart stopped instances anytime")
    print(f"  - Terminated instances cannot be recovered")


if __name__ == "__main__":
    main()
