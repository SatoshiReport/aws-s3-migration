#!/usr/bin/env python3
"""Clean up and manage EC2 instances."""

from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError

from cost_toolkit.common.aws_client_factory import create_client, create_ec2_client
from cost_toolkit.common.aws_common import extract_tag_value, get_instance_details


def terminate_instance(instance_id, region_name):
    """
    Terminate an EC2 instance.
    Delegates to canonical implementation in aws_ec2_operations.
    """
    print(f"\n🗑️  Terminating instance {instance_id} in {region_name}")
    print("=" * 80)

    try:
        ec2 = create_ec2_client(region=region_name)

        # Get instance details first using canonical function
        details = get_instance_details(ec2, instance_id)
        if not details:
            print(
                f"  ❌ Error terminating instance {instance_id}: Could not retrieve instance details"
            )
            return False

        instance_type = details["instance_type"]
        state = details["state"]
        name_tag = details["name"]

        print(f"  Instance: {instance_id}")
        print(f"  Name: {name_tag}")
        print(f"  Type: {instance_type}")
        print(f"  Current State: {state}")

        if state == "terminated":
            print("  ✅ Instance already terminated")
            return True

        # Terminate the instance
        ec2.terminate_instances(InstanceIds=[instance_id])
        print(f"  ✅ Termination initiated for {instance_id}")
        print("  💰 This will stop EBS storage charges for attached volumes")

    except ClientError as e:
        print(f"  ❌ Error terminating instance {instance_id}: {e}")
        return False

    return True


def rename_instance(instance_id, new_name, region_name):
    """Rename an EC2 instance by updating its Name tag"""
    print(f"\n🏷️  Renaming instance {instance_id} to '{new_name}' in {region_name}")
    print("=" * 80)

    try:
        ec2 = create_client("ec2", region=region_name)

        # Update the Name tag
        ec2.create_tags(Resources=[instance_id], Tags=[{"Key": "Name", "Value": new_name}])

        print(f"  ✅ Instance {instance_id} renamed to '{new_name}'")

    except ClientError as e:
        print(f"  ❌ Error renaming instance {instance_id}: {e}")
        return False

    return True


def _get_instance_name_tag(instance):
    """Extract instance name from tags. Delegates to canonical implementation."""
    name = extract_tag_value(instance, "Name")
    if name is None:
        return "Unknown"
    return name


def _get_last_activity_from_metrics(cloudwatch, instance_id):
    """Get last activity time from CloudWatch CPU metrics."""
    try:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=90)  # Look back 90 days

        metrics_response = cloudwatch.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,  # 1 hour periods
            Statistics=["Average"],
        )

        datapoints = metrics_response.get("Datapoints", [])
        if datapoints:
            datapoints.sort(key=lambda x: x["Timestamp"])
            last_activity = datapoints[-1]["Timestamp"]
            print(f"  Last Activity (CPU metrics): {last_activity}")
        else:
            print("  Last Activity: No CPU metrics found (may not have run recently)")

    except ClientError as e:
        print(f"  Last Activity: Could not retrieve metrics - {e}")


def _print_instance_details(instance_id, name_tag, instance_type, state, launch_time):
    """Print formatted instance details."""
    print(f"  Instance: {instance_id}")
    print(f"  Name: {name_tag}")
    print(f"  Type: {instance_type}")
    print(f"  State: {state}")
    print(f"  Launch Time: {launch_time}")


def _print_instance_age(launch_time):
    """Calculate and print instance age."""
    if launch_time:
        age = datetime.now(timezone.utc) - launch_time
        print(f"  Age: {age.days} days")


def get_instance_detailed_info(instance_id, region_name):
    """Get detailed information about an instance including creation and last run times"""
    print(f"\n🔍 Getting detailed info for {instance_id} in {region_name}")
    print("=" * 80)

    try:
        ec2 = create_client("ec2", region=region_name)
        cloudwatch = create_client("cloudwatch", region=region_name)

        # Get instance details
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]

        instance_type = instance["InstanceType"]
        state = instance["State"]["Name"]
        launch_time = instance.get("LaunchTime")
        name_tag = _get_instance_name_tag(instance)

        _print_instance_details(instance_id, name_tag, instance_type, state, launch_time)
        _get_last_activity_from_metrics(cloudwatch, instance_id)
        _print_instance_age(launch_time)

    except ClientError as e:
        print(f"  ❌ Error getting instance info: {e}")
        return None
    return {
        "instance_id": instance_id,
        "name": name_tag,
        "instance_type": instance_type,
        "state": state,
        "launch_time": launch_time,
        "region": region_name,
    }


def _calculate_ebs_savings(name):
    """Calculate EBS savings for a terminated instance."""
    savings_map = {
        "Talker GPU": 5.12,
        "Model": 5.12,
        "mufasa": 0.64,
    }
    if name not in savings_map:
        return 0
    return savings_map[name]


def _terminate_instances(instances_to_terminate):
    """Terminate a list of instances."""
    termination_results = []
    estimated_savings = 0

    for instance_id, region, name in instances_to_terminate:
        success = terminate_instance(instance_id, region)
        termination_results.append((instance_id, name, success))

        if success:
            estimated_savings += _calculate_ebs_savings(name)

    return termination_results, estimated_savings


def _analyze_instances(instances_to_analyze):
    """Analyze a list of instances."""
    instance_details = []
    for instance_id, region in instances_to_analyze:
        details = get_instance_detailed_info(instance_id, region)
        if details:
            instance_details.append(details)
    return instance_details


def _print_summary(termination_results, rename_success, instance_details, estimated_savings):
    """Print operation summary."""
    print("\n" + "=" * 80)
    print("🎯 OPERATION SUMMARY")
    print("=" * 80)

    successful_terminations = [result for result in termination_results if result[2]]
    failed_terminations = [result for result in termination_results if not result[2]]

    print(f"✅ Successfully terminated: {len(successful_terminations)}")
    for instance_id, name, _ in successful_terminations:
        print(f"  {instance_id} ({name})")

    if failed_terminations:
        print(f"\n❌ Failed to terminate: {len(failed_terminations)}")
        for instance_id, name, _ in failed_terminations:
            print(f"  {instance_id} ({name})")

    print(f"\n🏷️  Instance rename: {'✅ Success' if rename_success else '❌ Failed'}")

    print("\n📊 EU-WEST-2 INSTANCE ANALYSIS:")
    for details in instance_details:
        print(f"  {details['instance_id']} ({details['name']}):")
        print(f"    Type: {details['instance_type']}")
        print(f"    Created: {details['launch_time']}")
        print(f"    State: {details['state']}")

    print("\n💰 COST IMPACT:")
    print(f"  Estimated monthly savings: ${estimated_savings:.2f}")
    print("  Terminated instances will stop incurring EBS storage costs")
    print("  Remaining active instance: i-00c39b1ba0eba3e2d (now named 'mufasa')")


def main():
    """Analyze and clean up EC2 instances."""
    print("AWS EC2 Instance Cleanup and Analysis")
    print("=" * 80)

    instances_to_terminate = [
        ("i-032b756f4ad7b1821", "us-east-1", "Talker GPU"),
        ("i-079d5fb7d85c5e9ae", "us-east-1", "Model"),
        ("i-0cfce47f50e3c34f", "us-east-1", "mufasa"),
    ]

    instance_to_rename = ("i-00c39b1ba0eba3e2d", "us-east-2", "mufasa")

    instances_to_analyze = [
        ("i-0635f4a0de21cbc37", "eu-west-2"),
        ("i-09ff569745467b037", "eu-west-2"),
        ("i-05ad29f28fc8a8fdc", "eu-west-2"),
    ]

    print("\n⚠️  WARNING: This will:")
    print("  - TERMINATE 3 instances (Talker GPU, Model, mufasa)")
    print("  - DELETE their attached EBS volumes")
    print("  - RENAME i-00c39b1ba0eba3e2d to 'mufasa'")
    print("  - ANALYZE 3 instances in eu-west-2")

    print("\n" + "=" * 80)
    print("PHASE 1: TERMINATING INSTANCES")
    print("=" * 80)

    termination_results, estimated_savings = _terminate_instances(instances_to_terminate)

    print("\n" + "=" * 80)
    print("PHASE 2: RENAMING INSTANCE")
    print("=" * 80)

    rename_success = rename_instance(
        instance_to_rename[0], instance_to_rename[2], instance_to_rename[1]
    )

    print("\n" + "=" * 80)
    print("PHASE 3: ANALYZING EU-WEST-2 INSTANCES")
    print("=" * 80)

    instance_details = _analyze_instances(instances_to_analyze)

    _print_summary(termination_results, rename_success, instance_details, estimated_savings)


if __name__ == "__main__":
    main()
