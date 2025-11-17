"""
Service status checking functions for AWS billing optimization.
Contains functions to check the status of various AWS services.
"""

import botocore.exceptions
from botocore.exceptions import ClientError

from cost_toolkit.common.aws_client_factory import create_client

PENDING_DELETION_TARGET = 4


def check_global_accelerator_status():
    """Check if Global Accelerator is disabled"""
    try:
        ga_client = create_client("globalaccelerator", region="us-west-2")
        response = ga_client.list_accelerators()

        disabled_count = 0
        total_count = len(response["Accelerators"])

        for accelerator in response["Accelerators"]:
            if not accelerator["Enabled"]:
                disabled_count += 1

        if total_count > 0 and disabled_count == total_count:
            return True, f"✅ RESOLVED - All {total_count} accelerators disabled"
        if disabled_count > 0:
            return True, f"🔄 PARTIAL - {disabled_count}/{total_count} accelerators disabled"

    except (botocore.exceptions.ClientError, ClientError) as e:
        if "AccessDenied" in str(e):
            return None, "⚠️ UNKNOWN - No permission to check Global Accelerator status"
        return None, f"⚠️ ERROR - {str(e)}"

    return False, f"❌ ACTIVE - {total_count} accelerators still enabled"


def _check_lightsail_instances_in_region(lightsail_client):
    """Check Lightsail instances in a single region."""
    stopped_count = 0
    total_count = 0

    instances_response = lightsail_client.get_instances()
    for instance in instances_response["instances"]:
        total_count += 1
        if instance["state"]["name"] == "stopped":
            stopped_count += 1

    return stopped_count, total_count


def _check_lightsail_databases_in_region(lightsail_client):
    """Check Lightsail databases in a single region."""
    stopped_count = 0
    total_count = 0

    databases_response = lightsail_client.get_relational_databases()
    for database in databases_response["relationalDatabases"]:
        total_count += 1
        if database["relationalDatabaseBlueprintId"] and database["masterDatabaseName"]:
            if "stopped" in database.get("state", "").lower():
                stopped_count += 1

    return stopped_count, total_count


def _format_lightsail_status(
    total_resources, stopped_resources, stopped_instances, stopped_databases
):
    """Format status message for Lightsail resources."""
    if total_resources > 0 and stopped_resources == total_resources:
        return (
            True,
            f"✅ RESOLVED - All Lightsail resources stopped "
            f"({stopped_instances} instances, {stopped_databases} databases)",
        )
    if stopped_resources > 0:
        return (
            True,
            f"🔄 PARTIAL - {stopped_resources}/{total_resources} Lightsail resources stopped",
        )
    if total_resources > 0:
        return False, f"❌ ACTIVE - {total_resources} Lightsail resources still running"
    return True, "✅ RESOLVED - No Lightsail resources found"


def check_lightsail_status():
    """Check if Lightsail instances and databases are stopped"""
    try:
        regions = ["eu-central-1", "us-east-1", "us-west-2"]
        stopped_instances = 0
        total_instances = 0
        stopped_databases = 0
        total_databases = 0

        for region in regions:
            try:
                lightsail_client = create_client("lightsail", region=region)

                inst_stopped, inst_total = _check_lightsail_instances_in_region(lightsail_client)
                stopped_instances += inst_stopped
                total_instances += inst_total

                db_stopped, db_total = _check_lightsail_databases_in_region(lightsail_client)
                stopped_databases += db_stopped
                total_databases += db_total

            except botocore.exceptions.ClientError:
                continue

        total_resources = total_instances + total_databases
        stopped_resources = stopped_instances + stopped_databases

        return _format_lightsail_status(
            total_resources, stopped_resources, stopped_instances, stopped_databases
        )

    except ClientError as e:
        return None, f"⚠️ ERROR - {str(e)}"


def _check_cloudwatch_canaries_in_region(synthetics_client):
    """Check CloudWatch canaries in a single region."""
    stopped_count = 0
    total_count = 0

    try:
        canaries_response = synthetics_client.describe_canaries()
        for canary in canaries_response["Canaries"]:
            total_count += 1
            if canary["Status"]["State"] == "STOPPED":
                stopped_count += 1
    except botocore.exceptions.ClientError:
        pass

    return stopped_count, total_count


def _check_cloudwatch_alarms_in_region(cw_client):
    """Check CloudWatch alarms in a single region."""
    disabled_count = 0
    total_count = 0

    try:
        alarms_response = cw_client.describe_alarms()
        for alarm in alarms_response["MetricAlarms"]:
            total_count += 1
            if not alarm["ActionsEnabled"]:
                disabled_count += 1
    except botocore.exceptions.ClientError:
        pass

    return disabled_count, total_count


def _format_cloudwatch_status(total_canaries, stopped_canaries, total_alarms, disabled_alarms):
    """Format status message for CloudWatch resources."""
    canaries_resolved = total_canaries in (0, stopped_canaries)
    alarms_resolved = total_alarms in (0, disabled_alarms)

    if canaries_resolved and alarms_resolved:
        status_parts = []
        if total_canaries > 0:
            status_parts.append(f"{stopped_canaries} canaries stopped")
        if total_alarms > 0:
            status_parts.append(f"{disabled_alarms} alarms disabled")
        if not status_parts:
            status_parts.append("no active resources")
        return True, f"✅ RESOLVED - CloudWatch optimized ({', '.join(status_parts)})"
    active_parts = []
    if total_canaries > stopped_canaries:
        active_parts.append(f"{total_canaries - stopped_canaries} canaries running")
    if total_alarms > disabled_alarms:
        active_parts.append(f"{total_alarms - disabled_alarms} alarms enabled")
    return False, f"❌ ACTIVE - {', '.join(active_parts)}"


def check_cloudwatch_status():
    """Check if CloudWatch canaries are stopped and alarms disabled"""
    try:
        regions = ["us-east-1", "us-east-2", "us-west-2"]
        stopped_canaries = 0
        total_canaries = 0
        disabled_alarms = 0
        total_alarms = 0

        for region in regions:
            try:
                cw_client = create_client("cloudwatch", region=region)
                synthetics_client = create_client("synthetics", region=region)

                canary_stopped, canary_total = _check_cloudwatch_canaries_in_region(
                    synthetics_client
                )
                stopped_canaries += canary_stopped
                total_canaries += canary_total

                alarm_disabled, alarm_total = _check_cloudwatch_alarms_in_region(cw_client)
                disabled_alarms += alarm_disabled
                total_alarms += alarm_total

            except botocore.exceptions.ClientError:
                continue

        return _format_cloudwatch_status(
            total_canaries, stopped_canaries, total_alarms, disabled_alarms
        )

    except ClientError as e:
        return None, f"⚠️ ERROR - {str(e)}"


if __name__ == "__main__":
    pass
