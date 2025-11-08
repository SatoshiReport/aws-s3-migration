#!/usr/bin/env python3
"""
AWS Backup and Automated Snapshot Audit Script
Checks for AWS Backup plans, scheduled snapshots, and automated AMI creation.
"""

import os
import sys
from datetime import datetime, timezone

import boto3

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aws_utils import setup_aws_credentials

# Constants
SNAPSHOT_ANALYSIS_DAYS = 30


def get_all_aws_regions():
    """Get all available AWS regions."""
    ec2_client = boto3.client("ec2", region_name="us-east-1")
    response = ec2_client.describe_regions()
    return [region["RegionName"] for region in response["Regions"]]


def check_aws_backup_plans(region):  # noqa: C901
    """Check for AWS Backup plans in a specific region."""
    try:
        backup_client = boto3.client("backup", region_name=region)

        # List backup plans
        plans_response = backup_client.list_backup_plans()
        backup_plans = plans_response.get("BackupPlansList", [])

        if backup_plans:
            print(f"🔍 AWS Backup Plans in {region}:")
            for plan in backup_plans:
                plan_id = plan["BackupPlanId"]
                plan_name = plan["BackupPlanName"]
                creation_date = plan["CreationDate"]

                print(f"  Plan: {plan_name} ({plan_id})")
                print(f"    Created: {creation_date}")

                # Get backup plan details
                try:
                    plan_details = backup_client.get_backup_plan(BackupPlanId=plan_id)
                    rules = plan_details["BackupPlan"].get("Rules", [])

                    for rule in rules:
                        rule_name = rule["RuleName"]
                        schedule = rule.get("ScheduleExpression", "No schedule")
                        lifecycle = rule.get("Lifecycle", {})

                        print(f"    Rule: {rule_name}")
                        print(f"      Schedule: {schedule}")
                        if lifecycle:
                            print(f"      Lifecycle: {lifecycle}")
                        print()

                except Exception as e:
                    print(f"    Error getting plan details: {e}")

        # List backup jobs (recent activity)
        try:
            jobs_response = backup_client.list_backup_jobs(MaxResults=10)
            backup_jobs = jobs_response.get("BackupJobs", [])

            if backup_jobs:
                print(f"📋 Recent Backup Jobs in {region}:")
                for job in backup_jobs[:5]:  # Show last 5 jobs
                    job_id = job["BackupJobId"]
                    resource_arn = job.get("ResourceArn", "Unknown")
                    state = job["State"]
                    creation_date = job["CreationDate"]

                    print(f"  Job: {job_id}")
                    print(f"    Resource: {resource_arn}")
                    print(f"    State: {state}")
                    print(f"    Created: {creation_date}")
                    print()

        except Exception as e:
            print(f"  Error listing backup jobs: {e}")

    except Exception as e:
        if "UnrecognizedClientException" in str(e):
            return  # AWS Backup not available in this region
        print(f"  Error checking AWS Backup in {region}: {e}")


def check_data_lifecycle_manager(region):
    """Check for Amazon Data Lifecycle Manager (DLM) policies."""
    try:
        dlm_client = boto3.client("dlm", region_name=region)

        # List lifecycle policies
        policies_response = dlm_client.get_lifecycle_policies()
        policies = policies_response.get("Policies", [])

        if policies:
            print(f"📅 Data Lifecycle Manager Policies in {region}:")
            for policy in policies:
                policy_id = policy["PolicyId"]
                description = policy.get("Description", "No description")
                state = policy["State"]

                print(f"  Policy: {policy_id}")
                print(f"    Description: {description}")
                print(f"    State: {state}")

                # Get policy details
                try:
                    policy_details = dlm_client.get_lifecycle_policy(PolicyId=policy_id)
                    policy_detail = policy_details["Policy"]

                    schedules = policy_detail.get("PolicyDetails", {}).get("Schedules", [])
                    for schedule in schedules:
                        name = schedule.get("Name", "Unnamed")
                        create_rule = schedule.get("CreateRule", {})
                        interval = create_rule.get("Interval", "Unknown")
                        interval_unit = create_rule.get("IntervalUnit", "")

                        print(f"    Schedule: {name}")
                        print(f"      Frequency: Every {interval} {interval_unit}")

                        retain_rule = schedule.get("RetainRule", {})
                        if retain_rule:
                            count = retain_rule.get("Count", "Unknown")
                            print(f"      Retention: {count} snapshots")
                        print()

                except Exception as e:
                    print(f"    Error getting policy details: {e}")

    except Exception as e:
        if "UnrecognizedClientException" in str(e):
            return  # DLM not available in this region
        print(f"  Error checking DLM in {region}: {e}")


def check_scheduled_events(region):
    """Check for EventBridge rules that might trigger snapshots."""
    try:
        events_client = boto3.client("events", region_name=region)

        # List rules
        rules_response = events_client.list_rules()
        rules = rules_response.get("Rules", [])

        snapshot_rules = []
        for rule in rules:
            rule_name = rule["Name"]
            description = rule.get("Description", "")
            state = rule["State"]

            # Look for rules that might be related to snapshots/AMIs
            if any(
                keyword in rule_name.lower() or keyword in description.lower()
                for keyword in ["snapshot", "ami", "backup", "image"]
            ):
                snapshot_rules.append(rule)

        if snapshot_rules:
            print(f"⏰ EventBridge Rules (Snapshot/AMI related) in {region}:")
            for rule in snapshot_rules:
                rule_name = rule["Name"]
                description = rule.get("Description", "No description")
                state = rule["State"]
                schedule = rule.get("ScheduleExpression", "Event-driven")

                print(f"  Rule: {rule_name}")
                print(f"    Description: {description}")
                print(f"    State: {state}")
                print(f"    Schedule: {schedule}")

                # Get targets
                try:
                    targets_response = events_client.list_targets_by_rule(Rule=rule_name)
                    targets = targets_response.get("Targets", [])

                    for target in targets:
                        target_arn = target["Arn"]
                        print(f"    Target: {target_arn}")

                except Exception as e:
                    print(f"    Error getting targets: {e}")
                print()

    except Exception as e:
        print(f"  Error checking EventBridge in {region}: {e}")


def analyze_recent_snapshots(region):  # noqa: C901, PLR0912
    """Analyze recent snapshots to identify automated creation patterns."""
    try:
        ec2_client = boto3.client("ec2", region_name=region)

        # Get recent snapshots (last 30 days)
        snapshots_response = ec2_client.describe_snapshots(OwnerIds=["self"], MaxResults=50)
        snapshots = snapshots_response.get("Snapshots", [])

        # Filter recent snapshots (last 30 days)
        now = datetime.now(timezone.utc)
        recent_snapshots = []

        for snapshot in snapshots:
            start_time = snapshot["StartTime"]
            age_days = (now - start_time).days
            if age_days <= SNAPSHOT_ANALYSIS_DAYS:
                recent_snapshots.append(snapshot)

        if recent_snapshots:
            print(f"📸 Recent Snapshots Analysis in {region} (Last {SNAPSHOT_ANALYSIS_DAYS} days):")

            # Group by creation pattern
            automated_patterns = {}
            manual_snapshots = []

            for snapshot in recent_snapshots:
                description = snapshot.get("Description", "")
                snapshot_id = snapshot["SnapshotId"]
                start_time = snapshot["StartTime"]
                size = snapshot.get("VolumeSize", 0)

                # Identify automated patterns
                if "CreateImage" in description:
                    pattern = "AMI Creation (CreateImage)"
                elif "AWS Backup" in description:
                    pattern = "AWS Backup"
                elif "DLM" in description or "Data Lifecycle Manager" in description:
                    pattern = "Data Lifecycle Manager"
                elif "Created by" in description:
                    pattern = "Automated (Other)"
                else:
                    pattern = "Manual/Unknown"

                if pattern not in automated_patterns:
                    automated_patterns[pattern] = []

                automated_patterns[pattern].append(
                    {
                        "id": snapshot_id,
                        "description": description,
                        "start_time": start_time,
                        "size": size,
                    }
                )

            # Display patterns
            for pattern, snapshots_list in automated_patterns.items():
                if pattern != "Manual/Unknown":
                    print(f"  🤖 {pattern}: {len(snapshots_list)} snapshots")
                    total_size = sum(s["size"] for s in snapshots_list)
                    monthly_cost = total_size * 0.05
                    print(f"    Total size: {total_size} GB")
                    print(f"    Monthly cost: ${monthly_cost:.2f}")

                    # Show most recent examples
                    recent_examples = sorted(
                        snapshots_list, key=lambda x: x["start_time"], reverse=True
                    )[:3]
                    for example in recent_examples:
                        print(
                            f"    Example: {example['id']} ({example['start_time'].strftime('%Y-%m-%d %H:%M')})"
                        )
                        print(f"      {example['description'][:80]}...")
                    print()

    except Exception as e:
        print(f"  Error analyzing snapshots in {region}: {e}")


def main():
    """Main function to audit AWS backup and automated snapshot services."""
    setup_aws_credentials()

    print("AWS Backup and Automated Snapshot Audit")
    print("=" * 80)
    print("Checking for automated backup services and snapshot creation...")
    print()

    # Focus on regions where we have resources
    priority_regions = ["eu-west-2", "us-east-2", "us-east-1"]

    for region in priority_regions:
        print(f"🔍 Auditing {region}")
        print("=" * 80)

        # Check AWS Backup
        check_aws_backup_plans(region)

        # Check Data Lifecycle Manager
        check_data_lifecycle_manager(region)

        # Check EventBridge rules
        check_scheduled_events(region)

        # Analyze recent snapshots
        analyze_recent_snapshots(region)

        print()


if __name__ == "__main__":
    main()
