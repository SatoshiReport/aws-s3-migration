#!/usr/bin/env python3
"""
AWS Backup and Automated Snapshot Audit Script
Checks for AWS Backup plans, scheduled snapshots, and automated AMI creation.
"""

from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from cost_toolkit.common.backup_utils import check_aws_backup_plans as get_backup_plans
from cost_toolkit.common.backup_utils import (
    check_dlm_lifecycle_policies,
    check_eventbridge_scheduled_rules,
)
from cost_toolkit.scripts.aws_utils import setup_aws_credentials

# Constants
SNAPSHOT_ANALYSIS_DAYS = 30


def get_all_aws_regions():
    """Get all available AWS regions."""
    ec2_client = boto3.client("ec2", region_name="us-east-1")
    response = ec2_client.describe_regions()
    return [region["RegionName"] for region in response["Regions"]]


def _display_backup_plan(backup_client, plan):
    """Display details for a single backup plan."""
    plan_id = plan["BackupPlanId"]
    plan_name = plan["BackupPlanName"]
    creation_date = plan["CreationDate"]

    print(f"  Plan: {plan_name} ({plan_id})")
    print(f"    Created: {creation_date}")

    try:
        plan_details = backup_client.get_backup_plan(BackupPlanId=plan_id)
        rules = plan_details["BackupPlan"].get("Rules", [])
        _display_backup_rules(rules)
    except ClientError as e:
        print(f"    Error getting plan details: {e}")


def _display_backup_rules(rules):
    """Display backup plan rules."""
    for rule in rules:
        rule_name = rule["RuleName"]
        schedule = rule.get("ScheduleExpression", "No schedule")
        lifecycle = rule.get("Lifecycle", {})

        print(f"    Rule: {rule_name}")
        print(f"      Schedule: {schedule}")
        if lifecycle:
            print(f"      Lifecycle: {lifecycle}")
        print()


def _display_backup_jobs(backup_client, region):
    """Display recent backup jobs."""
    try:
        jobs_response = backup_client.list_backup_jobs(MaxResults=10)
        backup_jobs = jobs_response.get("BackupJobs", [])

        if backup_jobs:
            print(f"📋 Recent Backup Jobs in {region}:")
            for job in backup_jobs[:5]:
                _display_single_job(job)
    except ClientError as e:
        print(f"  Error listing backup jobs: {e}")


def _display_single_job(job):
    """Display details for a single backup job."""
    job_id = job["BackupJobId"]
    resource_arn = job.get("ResourceArn", "Unknown")
    state = job["State"]
    creation_date = job["CreationDate"]

    print(f"  Job: {job_id}")
    print(f"    Resource: {resource_arn}")
    print(f"    State: {state}")
    print(f"    Created: {creation_date}")
    print()


def check_aws_backup_plans(region):
    """Check for AWS Backup plans in a specific region."""
    try:
        backup_client = boto3.client("backup", region_name=region)
        backup_plans = get_backup_plans(region)

        if backup_plans:
            print(f"🔍 AWS Backup Plans in {region}:")
            for plan in backup_plans:
                _display_backup_plan(backup_client, plan)

        _display_backup_jobs(backup_client, region)

    except ClientError as e:
        if "UnrecognizedClientException" in str(e):
            return
        print(f"  Error checking AWS Backup in {region}: {e}")


def _display_policy_schedules(dlm_client, policy_id):
    """Display lifecycle policy schedules."""
    try:
        policy_details = dlm_client.get_lifecycle_policy(PolicyId=policy_id)
        policy_detail = policy_details["Policy"]

        schedules = policy_detail.get("PolicyDetails", {}).get("Schedules", [])
        for schedule in schedules:
            _display_single_schedule(schedule)
    except ClientError as e:
        print(f"    Error getting policy details: {e}")


def _display_single_schedule(schedule):
    """Display a single policy schedule."""
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


def check_data_lifecycle_manager(region):
    """Check for Amazon Data Lifecycle Manager (DLM) policies."""
    policies = check_dlm_lifecycle_policies(region)

    if policies:
        try:
            dlm_client = boto3.client("dlm", region_name=region)
            print(f"📅 Data Lifecycle Manager Policies in {region}:")
            for policy in policies:
                policy_id = policy["PolicyId"]
                description = policy.get("Description", "No description")
                state = policy["State"]

                print(f"  Policy: {policy_id}")
                print(f"    Description: {description}")
                print(f"    State: {state}")

                _display_policy_schedules(dlm_client, policy_id)

        except ClientError as e:
            if "UnrecognizedClientException" in str(e):
                return
            print(f"  Error checking DLM in {region}: {e}")


def _is_snapshot_related_rule(rule):
    """Check if an EventBridge rule is related to snapshots/AMIs."""
    rule_name = rule["Name"]
    description = rule.get("Description", "")
    return any(
        keyword in rule_name.lower() or keyword in description.lower()
        for keyword in ["snapshot", "ami", "backup", "image"]
    )


def _display_rule_details(events_client, rule):
    """Display details for a single EventBridge rule."""
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

    except ClientError as e:
        print(f"    Error getting targets: {e}")
    print()


def check_scheduled_events(region):
    """Check for EventBridge rules that might trigger snapshots."""
    rules = check_eventbridge_scheduled_rules(region)

    if rules:
        events_client = boto3.client("events", region_name=region)
        snapshot_rules = [rule for rule in rules if _is_snapshot_related_rule(rule)]

        if snapshot_rules:
            print(f"⏰ EventBridge Rules (Snapshot/AMI related) in {region}:")
            for rule in snapshot_rules:
                _display_rule_details(events_client, rule)


def _categorize_snapshot(snapshot):
    """Categorize a snapshot by its creation pattern."""
    description = snapshot.get("Description", "")
    snapshot_id = snapshot["SnapshotId"]
    start_time = snapshot["StartTime"]
    size = snapshot.get("VolumeSize", 0)

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

    return pattern, {
        "id": snapshot_id,
        "description": description,
        "start_time": start_time,
        "size": size,
    }


def _display_snapshot_pattern(pattern, snapshots_list):
    """Display information for a snapshot pattern."""
    if pattern == "Manual/Unknown":
        return

    print(f"  🤖 {pattern}: {len(snapshots_list)} snapshots")
    total_size = sum(s["size"] for s in snapshots_list)
    monthly_cost = total_size * 0.05
    print(f"    Total size: {total_size} GB")
    print(f"    Monthly cost: ${monthly_cost:.2f}")

    recent_examples = sorted(snapshots_list, key=lambda x: x["start_time"], reverse=True)[:3]
    for example in recent_examples:
        print(f"    Example: {example['id']} ({example['start_time'].strftime('%Y-%m-%d %H:%M')})")
        print(f"      {example['description'][:80]}...")
    print()


def analyze_recent_snapshots(region):
    """Analyze recent snapshots to identify automated creation patterns."""
    try:
        ec2_client = boto3.client("ec2", region_name=region)

        snapshots_response = ec2_client.describe_snapshots(OwnerIds=["self"], MaxResults=50)
        snapshots = snapshots_response.get("Snapshots", [])

        now = datetime.now(timezone.utc)
        recent_snapshots = [
            s for s in snapshots if (now - s["StartTime"]).days <= SNAPSHOT_ANALYSIS_DAYS
        ]

        if recent_snapshots:
            print(f"📸 Recent Snapshots Analysis in {region} (Last {SNAPSHOT_ANALYSIS_DAYS} days):")

            automated_patterns = {}
            for snapshot in recent_snapshots:
                pattern, snapshot_info = _categorize_snapshot(snapshot)
                if pattern not in automated_patterns:
                    automated_patterns[pattern] = []
                automated_patterns[pattern].append(snapshot_info)

            for pattern, snapshots_list in automated_patterns.items():
                _display_snapshot_pattern(pattern, snapshots_list)

    except ClientError as e:
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
