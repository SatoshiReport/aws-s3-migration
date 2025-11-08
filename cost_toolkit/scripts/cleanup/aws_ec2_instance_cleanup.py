#!/usr/bin/env python3

import json
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def terminate_instance(instance_id, region_name):
    """Terminate an EC2 instance"""
    print(f"\n🗑️  Terminating instance {instance_id} in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        # Get instance details first
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]

        instance_type = instance["InstanceType"]
        state = instance["State"]["Name"]
        name_tag = "Unknown"

        for tag in instance.get("Tags", []):
            if tag["Key"] == "Name":
                name_tag = tag["Value"]
                break

        print(f"  Instance: {instance_id}")
        print(f"  Name: {name_tag}")
        print(f"  Type: {instance_type}")
        print(f"  Current State: {state}")

        if state == "terminated":
            print(f"  ✅ Instance already terminated")
            return True

        # Terminate the instance
        ec2.terminate_instances(InstanceIds=[instance_id])
        print(f"  ✅ Termination initiated for {instance_id}")
        print(f"  💰 This will stop EBS storage charges for attached volumes")

    except ClientError as e:
        print(f"  ❌ Error terminating instance {instance_id}: {e}")
        return False

    else:
        return True


def rename_instance(instance_id, new_name, region_name):
    """Rename an EC2 instance by updating its Name tag"""
    print(f"\n🏷️  Renaming instance {instance_id} to '{new_name}' in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        # Update the Name tag
        ec2.create_tags(Resources=[instance_id], Tags=[{"Key": "Name", "Value": new_name}])

        print(f"  ✅ Instance {instance_id} renamed to '{new_name}'")

    except ClientError as e:
        print(f"  ❌ Error renaming instance {instance_id}: {e}")
        return False

    else:
        return True


def get_instance_detailed_info(instance_id, region_name):
    """Get detailed information about an instance including creation and last run times"""
    print(f"\n🔍 Getting detailed info for {instance_id} in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)
        cloudwatch = boto3.client("cloudwatch", region_name=region_name)

        # Get instance details
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]

        instance_type = instance["InstanceType"]
        state = instance["State"]["Name"]
        launch_time = instance.get("LaunchTime")

        name_tag = "Unknown"
        for tag in instance.get("Tags", []):
            if tag["Key"] == "Name":
                name_tag = tag["Value"]
                break

        print(f"  Instance: {instance_id}")
        print(f"  Name: {name_tag}")
        print(f"  Type: {instance_type}")
        print(f"  State: {state}")
        print(f"  Launch Time: {launch_time}")

        # Try to get last activity from CloudWatch metrics
        try:
            # Get CPU utilization to determine last activity
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
                # Sort by timestamp and get the most recent
                datapoints.sort(key=lambda x: x["Timestamp"])
                last_activity = datapoints[-1]["Timestamp"]
                print(f"  Last Activity (CPU metrics): {last_activity}")
            else:
                print(f"  Last Activity: No CPU metrics found (may not have run recently)")

        except Exception as e:
            print(f"  Last Activity: Could not retrieve metrics - {e}")

        # Calculate age
        if launch_time:
            age = datetime.now(timezone.utc) - launch_time
            print(f"  Age: {age.days} days")

    except ClientError as e:
        print(f"  ❌ Error getting instance info: {e}")
        return None
    else:
        return {
            "instance_id": instance_id,
            "name": name_tag,
            "instance_type": instance_type,
            "state": state,
            "launch_time": launch_time,
            "region": region_name,
        }


def main():  # noqa: C901, PLR0912, PLR0915
    print("AWS EC2 Instance Cleanup and Analysis")
    print("=" * 80)

    # Instances to terminate
    instances_to_terminate = [
        ("i-032b756f4ad7b1821", "us-east-1", "Talker GPU"),
        ("i-079d5fb7d85c5e9ae", "us-east-1", "Model"),
        ("i-0cfce47f50e3c34ff", "us-east-1", "mufasa"),
    ]

    # Instance to rename
    instance_to_rename = ("i-00c39b1ba0eba3e2d", "us-east-2", "mufasa")

    # Instances to analyze
    instances_to_analyze = [
        ("i-0635f4a0de21cbc37", "eu-west-2"),
        ("i-09ff569745467b037", "eu-west-2"),
        ("i-05ad29f28fc8a8fdc", "eu-west-2"),
    ]

    print(f"\n⚠️  WARNING: This will:")
    print(f"  - TERMINATE 3 instances (Talker GPU, Model, mufasa)")
    print(f"  - DELETE their attached EBS volumes")
    print(f"  - RENAME i-00c39b1ba0eba3e2d to 'mufasa'")
    print(f"  - ANALYZE 3 instances in eu-west-2")

    # Phase 1: Terminate instances
    print(f"\n" + "=" * 80)
    print("PHASE 1: TERMINATING INSTANCES")
    print("=" * 80)

    termination_results = []
    estimated_savings = 0

    for instance_id, region, name in instances_to_terminate:
        success = terminate_instance(instance_id, region)
        termination_results.append((instance_id, name, success))

        if success:
            # Calculate savings (approximate EBS costs)
            if name == "Talker GPU":
                estimated_savings += 5.12  # 64GB volume
            elif name == "Model":
                estimated_savings += 5.12  # 64GB volume
            elif name == "mufasa":
                estimated_savings += 0.64  # 8GB volume

    # Phase 2: Rename instance
    print(f"\n" + "=" * 80)
    print("PHASE 2: RENAMING INSTANCE")
    print("=" * 80)

    rename_success = rename_instance(
        instance_to_rename[0], instance_to_rename[2], instance_to_rename[1]
    )

    # Phase 3: Analyze remaining instances
    print(f"\n" + "=" * 80)
    print("PHASE 3: ANALYZING EU-WEST-2 INSTANCES")
    print("=" * 80)

    instance_details = []
    for instance_id, region in instances_to_analyze:
        details = get_instance_detailed_info(instance_id, region)
        if details:
            instance_details.append(details)

    # Summary
    print(f"\n" + "=" * 80)
    print("🎯 OPERATION SUMMARY")
    print("=" * 80)

    # Termination results
    successful_terminations = [result for result in termination_results if result[2]]
    failed_terminations = [result for result in termination_results if not result[2]]

    print(f"✅ Successfully terminated: {len(successful_terminations)}")
    for instance_id, name, _ in successful_terminations:
        print(f"  {instance_id} ({name})")

    if failed_terminations:
        print(f"\n❌ Failed to terminate: {len(failed_terminations)}")
        for instance_id, name, _ in failed_terminations:
            print(f"  {instance_id} ({name})")

    # Rename result
    print(f"\n🏷️  Instance rename: {'✅ Success' if rename_success else '❌ Failed'}")

    # Instance analysis summary
    print(f"\n📊 EU-WEST-2 INSTANCE ANALYSIS:")
    for details in instance_details:
        print(f"  {details['instance_id']} ({details['name']}):")
        print(f"    Type: {details['instance_type']}")
        print(f"    Created: {details['launch_time']}")
        print(f"    State: {details['state']}")

    # Cost impact
    print(f"\n💰 COST IMPACT:")
    print(f"  Estimated monthly savings: ${estimated_savings:.2f}")
    print(f"  Terminated instances will stop incurring EBS storage costs")
    print(f"  Remaining active instance: i-00c39b1ba0eba3e2d (now named 'mufasa')")


if __name__ == "__main__":
    from datetime import timedelta

    main()
