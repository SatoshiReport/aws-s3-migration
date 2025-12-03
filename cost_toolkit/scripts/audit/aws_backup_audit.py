#!/usr/bin/env python3
"""
AWS Backup and Automated Snapshot Audit Script
Checks for AWS Backup plans, scheduled snapshots, and automated AMI creation.
"""

from datetime import datetime, timezone

from botocore.exceptions import ClientError

from cost_toolkit.common.aws_client_factory import create_client
from cost_toolkit.common.aws_common import get_all_aws_regions
from cost_toolkit.common.backup_utils import check_aws_backup_plans as get_backup_plans
from cost_toolkit.common.backup_utils import (
    check_dlm_lifecycle_policies,
    check_eventbridge_scheduled_rules,
    is_backup_related_rule,
)
from cost_toolkit.common.cost_utils import calculate_snapshot_cost
from cost_toolkit.scripts.aws_utils import setup_aws_credentials

# Constants
SNAPSHOT_ANALYSIS_DAYS = 30


def _require_field(payload: dict, field: str, context: str):
    """Raise if an expected field is missing."""
    if field not in payload:
        raise RuntimeError(f"{context} missing required field '{field}'")
    return payload[field]


def _display_backup_plan(backup_client, plan):
    """Display details for a single backup plan."""
    plan_id = plan["BackupPlanId"]
    plan_name = plan["BackupPlanName"]
    creation_date = plan["CreationDate"]

    print(f"  Plan: {plan_name} ({plan_id})")
    print(f"    Created: {creation_date}")

    try:
        plan_details = backup_client.get_backup_plan(BackupPlanId=plan_id)
        backup_plan = plan_details["BackupPlan"]
        if "Rules" not in backup_plan:
            raise RuntimeError("Backup plan missing Rules payload")
        rules = backup_plan["Rules"]
        _display_backup_rules(rules)
    except ClientError as e:
        print(f"    Error getting plan details: {e}")


def _display_backup_rules(rules):
    """Display backup plan rules."""
    for rule in rules:
        rule_name = rule.get("RuleName")
        schedule = rule.get("ScheduleExpression") or "No schedule"
        lifecycle = rule.get("Lifecycle")

        print(f"    Rule: {rule_name}")
        print(f"      Schedule: {schedule}")
        if lifecycle is not None:
            print(f"      Lifecycle: {lifecycle}")
        print()


def _display_backup_jobs(backup_client, region):
    """Display recent backup jobs."""
    try:
        jobs_response = backup_client.list_backup_jobs(MaxResults=10)
        backup_jobs = _require_field(jobs_response, "BackupJobs", "Backup jobs response")

        if backup_jobs:
            print(f"📋 Recent Backup Jobs in {region}:")
            for job in backup_jobs[:5]:
                _display_single_job(job)
    except ClientError as e:
        print(f"  Error listing backup jobs: {e}")


def _display_single_job(job):
    """Display details for a single backup job."""
    job_id = job["BackupJobId"]
    resource_arn = job.get("ResourceArn")
    state = _require_field(job, "State", "Backup job")
    creation_date = _require_field(job, "CreationDate", "Backup job")

    print(f"  Job: {job_id}")
    if resource_arn:
        print(f"    Resource: {resource_arn}")
    print(f"    State: {state}")
    print(f"    Created: {creation_date}")
    print()


def check_aws_backup_plans(region):
    """Check for AWS Backup plans in a specific region."""
    try:
        backup_client = create_client("backup", region=region)
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

        policy_details_section = _require_field(
            policy_detail, "PolicyDetails", "Lifecycle policy details"
        )
        schedules = _require_field(
            policy_details_section, "Schedules", "Lifecycle policy schedules"
        )
        for schedule in schedules:
            _display_single_schedule(schedule)
    except ClientError as e:
        print(f"    Error getting policy details: {e}")


def _display_single_schedule(schedule):
    """Display a single policy schedule."""
    name = _require_field(schedule, "Name", "Lifecycle schedule")
    create_rule = _require_field(schedule, "CreateRule", "Lifecycle schedule")
    interval = _require_field(create_rule, "Interval", "Lifecycle schedule create rule")
    interval_unit = _require_field(create_rule, "IntervalUnit", "Lifecycle schedule create rule")

    print(f"    Schedule: {name}")
    print(f"      Frequency: Every {interval} {interval_unit}")

    retain_rule = schedule.get("RetainRule")
    if retain_rule is not None:
        count = _require_field(retain_rule, "Count", "Lifecycle retain rule")
        print(f"      Retention: {count} snapshots")
    print()


def check_data_lifecycle_manager(region):
    """Check for Amazon Data Lifecycle Manager (DLM) policies."""
    policies = check_dlm_lifecycle_policies(region)

    if policies:
        try:
            dlm_client = create_client("dlm", region=region)
            print(f"📅 Data Lifecycle Manager Policies in {region}:")
            for policy in policies:
                policy_id = policy["PolicyId"]
                description = policy.get("Description")
                state = policy["State"]

                print(f"  Policy: {policy_id}")
                print(f"    Description: {description}")
                print(f"    State: {state}")

                _display_policy_schedules(dlm_client, policy_id)

        except ClientError as e:
            if "UnrecognizedClientException" in str(e):
                return
            print(f"  Error checking DLM in {region}: {e}")


def _display_rule_details(events_client, rule):
    """Display details for a single EventBridge rule."""
    rule_name = rule["Name"]
    description = rule.get("Description")
    state = _require_field(rule, "State", "EventBridge rule")
    schedule = rule.get("ScheduleExpression") or "Event-driven"

    print(f"  Rule: {rule_name}")
    print(f"    Description: {description}")
    print(f"    State: {state}")
    print(f"    Schedule: {schedule}")

    # Get targets
    try:
        targets_response = events_client.list_targets_by_rule(Rule=rule_name)
        targets = _require_field(targets_response, "Targets", "EventBridge targets response")

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
        events_client = create_client("events", region=region)
        snapshot_rules = [rule for rule in rules if is_backup_related_rule(rule)]

        if snapshot_rules:
            print(f"⏰ EventBridge Rules (Snapshot/AMI related) in {region}:")
            for rule in snapshot_rules:
                _display_rule_details(events_client, rule)


def _categorize_snapshot(snapshot):
    """Categorize a snapshot by its creation pattern."""
    description = _require_field(snapshot, "Description", "Snapshot")
    snapshot_id = snapshot["SnapshotId"]
    start_time = snapshot["StartTime"]
    size = _require_field(snapshot, "VolumeSize", "Snapshot")

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
    monthly_cost = calculate_snapshot_cost(total_size)
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
        ec2_client = create_client("ec2", region=region)

        snapshots_response = ec2_client.describe_snapshots(OwnerIds=["self"], MaxResults=50)
        snapshots = _require_field(snapshots_response, "Snapshots", "Snapshots response")

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

    # Check all regions
    regions = get_all_aws_regions()

    for region in regions:
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
