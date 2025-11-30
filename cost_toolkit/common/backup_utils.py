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
    policies = policies_response["Policies"]

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
    rules = rules_response["Rules"]

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
    backup_plans = plans_response["BackupPlansList"]

    return backup_plans


def is_backup_related_rule(rule):
    """
    Check if an EventBridge rule is related to snapshots/AMIs.

    Args:
        rule: EventBridge rule dictionary

    Returns:
        bool: True if related to backup/snapshot, False otherwise
    """
    rule_name = rule["Name"]
    description = rule.get("Description") if "Description" in rule else ""
    # Combined list from both files: snapshot, ami, backup, image, createimage
    keywords = ["snapshot", "ami", "backup", "image", "createimage"]
    return any(
        keyword in rule_name.lower() or keyword in description.lower()
        for keyword in keywords
    )
