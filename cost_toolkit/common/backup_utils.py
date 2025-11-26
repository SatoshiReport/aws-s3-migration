"""
Shared AWS Backup utilities to reduce code duplication.

Common backup-related operations used across audit and cleanup scripts.
"""

import boto3


def check_dlm_lifecycle_policies(region):
    """
    Check for Data Lifecycle Manager (DLM) policies in a specific region.

    Args:
        region: AWS region name

    Returns:
        list: List of DLM policies found, or empty list if none

    Raises:
        ClientError: If API call fails
    """
    dlm_client = boto3.client("dlm", region_name=region)

    policies_response = dlm_client.get_lifecycle_policies()
    policies = policies_response.get("Policies", [])

    return policies


def check_eventbridge_scheduled_rules(region):
    """
    Check for EventBridge rules that might trigger snapshots.

    Args:
        region: AWS region name

    Returns:
        list: List of EventBridge rules, or empty list if none

    Raises:
        ClientError: If API call fails
    """
    events_client = boto3.client("events", region_name=region)

    rules_response = events_client.list_rules()
    rules = rules_response.get("Rules", [])

    return rules


def check_aws_backup_plans(region):
    """
    Check for AWS Backup plans in a specific region.

    Args:
        region: AWS region name

    Returns:
        list: List of backup plans, or empty list if none

    Raises:
        ClientError: If API call fails
    """
    backup_client = boto3.client("backup", region_name=region)

    plans_response = backup_client.list_backup_plans()
    backup_plans = plans_response.get("BackupPlansList", [])

    return backup_plans


def get_backup_plan_details(backup_client, plan_id, plan_name, creation_date):
    """
    Get and print details for a specific backup plan.

    Args:
        backup_client: Boto3 Backup client
        plan_id: Backup plan ID
        plan_name: Backup plan name
        creation_date: Plan creation date

    Returns:
        dict: Backup plan details

    Raises:
        ClientError: If API call fails
    """
    print(f"  Plan: {plan_name} ({plan_id})")
    print(f"    Created: {creation_date}")

    plan_details = backup_client.get_backup_plan(BackupPlanId=plan_id)

    return plan_details
