#!/usr/bin/env python3
"""
AWS Billing Report Script
Gets detailed billing information for the past month including services, regions, and costs.
"""

import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta

import boto3
import botocore.exceptions
from dotenv import load_dotenv

PENDING_DELETION_TARGET = 4


def clear_screen():
    """Clear the terminal screen without invoking a shell."""
    try:
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "cls"], check=False)
        else:
            subprocess.run(["clear"], check=False)
    except FileNotFoundError:
        print("\033c", end="")


def setup_aws_credentials():
    """Load AWS credentials from .env file"""
    # Load environment variables from .env file
    load_dotenv(os.path.expanduser("~/.env"))

    # Check if credentials are loaded
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        print("⚠️  AWS credentials not found in ~/.env file.")
        print("Please ensure ~/.env contains:")
        print("  AWS_ACCESS_KEY_ID=your-access-key")
        print("  AWS_SECRET_ACCESS_KEY=your-secret-key")
        print("  AWS_DEFAULT_REGION=us-east-1")
        return False

    return True


def get_date_range():
    """Get the date range for the current month to today"""
    end_date = datetime.now().date()
    start_date = end_date.replace(day=1)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def check_global_accelerator_status():
    """Check if Global Accelerator is disabled"""
    try:
        ga_client = boto3.client("globalaccelerator", region_name="us-west-2")
        response = ga_client.list_accelerators()

        disabled_count = 0
        total_count = len(response["Accelerators"])

        for accelerator in response["Accelerators"]:
            if not accelerator["Enabled"]:
                disabled_count += 1

        if total_count > 0 and disabled_count == total_count:
            return True, f"✅ RESOLVED - All {total_count} accelerators disabled"
        elif disabled_count > 0:
            return True, f"🔄 PARTIAL - {disabled_count}/{total_count} accelerators disabled"
        else:
            return False, f"❌ ACTIVE - {total_count} accelerators still enabled"

    except botocore.exceptions.ClientError as e:
        if "AccessDenied" in str(e):
            return None, "⚠️ UNKNOWN - No permission to check Global Accelerator status"
        return None, f"⚠️ ERROR - {str(e)}"
    except Exception as e:
        return None, f"⚠️ ERROR - {str(e)}"


def check_lightsail_status():
    """Check if Lightsail instances and databases are stopped"""
    try:
        # Check all regions where we had Lightsail resources
        regions = ["eu-central-1", "us-east-1", "us-west-2"]
        stopped_instances = 0
        total_instances = 0
        stopped_databases = 0
        total_databases = 0

        for region in regions:
            try:
                lightsail_client = boto3.client("lightsail", region_name=region)

                # Check instances
                instances_response = lightsail_client.get_instances()
                for instance in instances_response["instances"]:
                    total_instances += 1
                    if instance["state"]["name"] == "stopped":
                        stopped_instances += 1

                # Check databases
                databases_response = lightsail_client.get_relational_databases()
                for database in databases_response["relationalDatabases"]:
                    total_databases += 1
                    if database["relationalDatabaseBlueprintId"] and database["masterDatabaseName"]:
                        # Check if database is stopped (not running)
                        if "stopped" in database.get("state", "").lower():
                            stopped_databases += 1

            except botocore.exceptions.ClientError:
                # Region might not have Lightsail or no permissions
                continue

        total_resources = total_instances + total_databases
        stopped_resources = stopped_instances + stopped_databases

        if total_resources > 0 and stopped_resources == total_resources:
            return (
                True,
                f"✅ RESOLVED - All Lightsail resources stopped ({stopped_instances} instances, {stopped_databases} databases)",
            )
        elif stopped_resources > 0:
            return (
                True,
                f"🔄 PARTIAL - {stopped_resources}/{total_resources} Lightsail resources stopped",
            )
        elif total_resources > 0:
            return False, f"❌ ACTIVE - {total_resources} Lightsail resources still running"
        else:
            return True, "✅ RESOLVED - No Lightsail resources found"

    except Exception as e:
        return None, f"⚠️ ERROR - {str(e)}"


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
                cw_client = boto3.client("cloudwatch", region_name=region)
                synthetics_client = boto3.client("synthetics", region_name=region)

                # Check canaries
                try:
                    canaries_response = synthetics_client.describe_canaries()
                    for canary in canaries_response["Canaries"]:
                        total_canaries += 1
                        if canary["Status"]["State"] == "STOPPED":
                            stopped_canaries += 1
                except botocore.exceptions.ClientError:
                    # Synthetics might not be available in this region
                    pass

                # Check alarms
                try:
                    alarms_response = cw_client.describe_alarms()
                    for alarm in alarms_response["MetricAlarms"]:
                        total_alarms += 1
                        if not alarm["ActionsEnabled"]:
                            disabled_alarms += 1
                except botocore.exceptions.ClientError:
                    pass

            except botocore.exceptions.ClientError:
                continue

        canaries_resolved = total_canaries == 0 or stopped_canaries == total_canaries
        alarms_resolved = total_alarms == 0 or disabled_alarms == total_alarms

        if canaries_resolved and alarms_resolved:
            status_parts = []
            if total_canaries > 0:
                status_parts.append(f"{stopped_canaries} canaries stopped")
            if total_alarms > 0:
                status_parts.append(f"{disabled_alarms} alarms disabled")
            if not status_parts:
                status_parts.append("no active resources")
            return True, f"✅ RESOLVED - CloudWatch optimized ({', '.join(status_parts)})"
        else:
            active_parts = []
            if total_canaries > stopped_canaries:
                active_parts.append(f"{total_canaries - stopped_canaries} canaries running")
            if total_alarms > disabled_alarms:
                active_parts.append(f"{total_alarms - disabled_alarms} alarms enabled")
            return False, f"❌ ACTIVE - {', '.join(active_parts)}"

    except Exception as e:
        return None, f"⚠️ ERROR - {str(e)}"


def check_lambda_status():
    """Check if Lambda functions have been deleted"""
    try:
        regions = ["us-east-1", "us-east-2", "us-west-2"]
        total_functions = 0

        for region in regions:
            try:
                lambda_client = boto3.client("lambda", region_name=region)
                response = lambda_client.list_functions()
                total_functions += len(response["Functions"])

            except botocore.exceptions.ClientError:
                # Region might not have Lambda or no permissions
                continue

        if total_functions == 0:
            return True, "✅ RESOLVED - All Lambda functions deleted"
        else:
            return False, f"❌ ACTIVE - {total_functions} Lambda functions still exist"

    except Exception as e:
        return None, f"⚠️ ERROR - {str(e)}"


def check_efs_status():
    """Check if EFS file systems have been deleted"""
    try:
        regions = ["us-east-1", "us-east-2"]
        total_filesystems = 0

        for region in regions:
            try:
                efs_client = boto3.client("efs", region_name=region)
                response = efs_client.describe_file_systems()
                total_filesystems += len(response["FileSystems"])

            except botocore.exceptions.ClientError:
                # Region might not have EFS or no permissions
                continue

        if total_filesystems == 0:
            return True, "✅ RESOLVED - All EFS file systems deleted"
        else:
            return False, f"❌ ACTIVE - {total_filesystems} EFS file systems still exist"

    except Exception as e:
        return None, f"⚠️ ERROR - {str(e)}"


def check_route53_status():
    """Check if specific Route 53 hosted zones have been deleted"""
    try:
        setup_aws_credentials()
        route53_client = boto3.client("route53")

        # Zones that should be deleted
        target_zones = ["88.176.35.in-addr.arpa", "apicentral.ai"]

        # List all hosted zones
        response = route53_client.list_hosted_zones()
        hosted_zones = response.get("HostedZones", [])

        existing_target_zones = []
        for zone in hosted_zones:
            zone_name = zone["Name"].rstrip(".")  # Remove trailing dot
            if zone_name in target_zones:
                existing_target_zones.append(zone_name)

        if len(existing_target_zones) == 0:
            return (
                True,
                "✅ RESOLVED - Target hosted zones deleted (88.176.35.in-addr.arpa, apicentral.ai)",
            )
        else:
            return (
                False,
                f"❌ ACTIVE - {len(existing_target_zones)} target zones still exist: {', '.join(existing_target_zones)}",
            )

    except Exception as e:
        return None, f"⚠️ ERROR - {str(e)}"


def check_kms_status():
    """Check if KMS keys have been scheduled for deletion"""
    try:
        setup_aws_credentials()

        # Regions where we had KMS keys
        regions_to_check = ["us-west-1", "eu-west-1", "us-east-1"]

        # Key IDs that should be deleted
        target_keys = [
            "09e32e6e-12cf-4dd1-ad49-b651bf81e152",  # us-west-1 WorkMail
            "36eabc4d-f9ec-4c48-a44c-0a3e267f096d",  # eu-west-1 WorkMail
            "fd385fc7-d349-4dfa-87a5-aa032d47e5bb",  # eu-west-1 WorkMail
            "6e4195b1-7e5d-4b9c-863b-0d33bbb8f71b",  # us-east-1 S3
        ]

        pending_deletion_count = 0

        for region in regions_to_check:
            try:
                kms_client = boto3.client("kms", region_name=region)

                # Check each target key in this region
                for key_id in target_keys:
                    try:
                        key_details = kms_client.describe_key(KeyId=key_id)
                        key_state = key_details["KeyMetadata"]["KeyState"]

                        if key_state == "PendingDeletion":
                            pending_deletion_count += 1

                    except botocore.exceptions.ClientError as e:
                        if "NotFoundException" in str(e):
                            # Key already deleted
                            pending_deletion_count += 1
                        # If it's a different region, key won't be found - that's expected
                        continue

            except botocore.exceptions.ClientError:
                # Region might not be accessible
                continue

        if pending_deletion_count >= PENDING_DELETION_TARGET:
            return True, (
                "✅ RESOLVED - All "
                f"{PENDING_DELETION_TARGET} KMS keys scheduled for deletion (saves $4/month)"
            )
        elif pending_deletion_count > 0:
            return False, (
                f"⚠️ PARTIAL - {pending_deletion_count}/{PENDING_DELETION_TARGET} "
                "KMS keys scheduled for deletion"
            )
        else:
            return False, "❌ ACTIVE - KMS keys still active"

    except Exception as e:
        return None, f"⚠️ ERROR - {str(e)}"


def check_vpc_status():
    """Check VPC Elastic IP status"""
    try:
        # Check regions where we had Elastic IPs
        regions_to_check = ["us-east-1", "eu-west-2"]

        total_elastic_ips = 0

        for region in regions_to_check:
            try:
                ec2 = boto3.client("ec2", region_name=region)
                response = ec2.describe_addresses()
                addresses = response.get("Addresses", [])
                total_elastic_ips += len(addresses)
            except botocore.exceptions.ClientError:
                continue

        if total_elastic_ips == 0:
            return True, "✅ RESOLVED - All Elastic IPs released (saves $14.40/month)"
        elif total_elastic_ips <= 1:
            return (
                False,
                f"📝 NOTED - {total_elastic_ips} Elastic IP locked by AWS (requires Support contact)",
            )
        else:
            return False, f"🔴 UNRESOLVED - {total_elastic_ips} Elastic IPs still allocated"

    except Exception as e:
        return None, f"⚠️ ERROR - {str(e)}"


def get_resolved_services_status():
    """Dynamically check the status of services that can be optimized"""
    resolved_services = {}

    # Check Global Accelerator
    ga_resolved, ga_status = check_global_accelerator_status()
    if ga_resolved is not None:
        resolved_services["AWS GLOBAL ACCELERATOR"] = ga_status

    # Check Lightsail
    ls_resolved, ls_status = check_lightsail_status()
    if ls_resolved is not None:
        resolved_services["AMAZON LIGHTSAIL"] = ls_status

    # Check CloudWatch
    cw_resolved, cw_status = check_cloudwatch_status()
    if cw_resolved is not None:
        resolved_services["AMAZONCLOUDWATCH"] = cw_status

    # Check Lambda
    lambda_resolved, lambda_status = check_lambda_status()
    if lambda_resolved is not None:
        resolved_services["AWS LAMBDA"] = lambda_status

    # Check EFS
    efs_resolved, efs_status = check_efs_status()
    if efs_resolved is not None:
        resolved_services["AMAZON ELASTIC FILE SYSTEM"] = efs_status

    # Check Route 53
    r53_resolved, r53_status = check_route53_status()
    if r53_resolved is not None:
        resolved_services["AMAZON ROUTE 53"] = r53_status

    # Check KMS
    kms_resolved, kms_status = check_kms_status()
    if kms_resolved is not None:
        resolved_services["AWS KEY MANAGEMENT SERVICE"] = kms_status

    # Check VPC
    vpc_resolved, vpc_status = check_vpc_status()
    if vpc_resolved is not None:
        resolved_services["AMAZON VIRTUAL PRIVATE CLOUD"] = vpc_status

    # Add noted services (recognized but decided not to optimize)
    resolved_services["AMAZONWORKMAIL"] = "📝 NOTED - Service recognized, no optimization planned"
    resolved_services["TAX"] = "📝 NOTED - Service recognized, no optimization planned"
    resolved_services["AMAZON RELATIONAL DATABASE SERVICE"] = (
        "📝 NOTED - Aurora deleted, MariaDB stopped (can restart when needed)"
    )

    return resolved_services


def get_combined_billing_data():
    """Retrieve both cost and usage data from AWS Cost Explorer"""
    setup_aws_credentials()

    # Create Cost Explorer client
    ce_client = boto3.client("ce", region_name="us-east-1")

    start_date, end_date = get_date_range()

    print(f"Retrieving billing data from {start_date} to {end_date}")
    print("=" * 80)

    try:
        # Get cost and usage data grouped by service and region
        cost_response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["BlendedCost", "UsageQuantity"],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "REGION"},
            ],
        )

        # Get detailed usage data grouped by service and usage type
        usage_response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UsageQuantity"],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "USAGE_TYPE"},
            ],
        )

        return cost_response, usage_response

    except Exception as e:
        print(f"Error retrieving billing data: {str(e)}")
        return None, None


def format_combined_billing_report(cost_data, usage_data):
    """Format and display the combined billing report with costs and usage details"""
    if not cost_data or "ResultsByTime" not in cost_data:
        print("No billing data available")
        return

    total_cost = 0.0
    service_costs = defaultdict(lambda: {"cost": 0.0, "regions": defaultdict(float)})
    service_usage = defaultdict(list)

    # Process cost data
    for result in cost_data["ResultsByTime"]:
        period_start = result["TimePeriod"]["Start"]
        period_end = result["TimePeriod"]["End"]

        print(f"\nBilling Period: {period_start} to {period_end}")
        print("-" * 80)

        for group in result["Groups"]:
            # Extract service and region from the group keys
            keys = group["Keys"]
            service = keys[0] if len(keys) > 0 else "Unknown Service"
            region = keys[1] if len(keys) > 1 else "Unknown Region"

            # Get cost information
            cost_amount = float(group["Metrics"]["BlendedCost"]["Amount"])

            if cost_amount > 0:  # Only show services with actual costs
                service_costs[service]["cost"] += cost_amount
                service_costs[service]["regions"][region] += cost_amount
                total_cost += cost_amount

    # Process usage data
    if usage_data and "ResultsByTime" in usage_data:
        for result in usage_data["ResultsByTime"]:
            for group in result["Groups"]:
                keys = group["Keys"]
                service = keys[0] if len(keys) > 0 else "Unknown Service"
                usage_type = keys[1] if len(keys) > 1 else "Unknown Usage Type"

                quantity = float(group["Metrics"]["UsageQuantity"]["Amount"])
                unit = group["Metrics"]["UsageQuantity"]["Unit"]

                if quantity > 0:
                    service_usage[service].append((usage_type, quantity, unit))

    # Get dynamic status of resolved services
    resolved_services = get_resolved_services_status()

    # Display combined report
    print(f"\nCOMBINED AWS BILLING & USAGE REPORT")
    print("=" * 120)

    # Separate services into three categories: unresolved, noted, and resolved
    resolved_services_list = []
    noted_services_list = []
    unresolved_services_list = []

    for service, data in service_costs.items():
        status_message = resolved_services.get(service.upper(), "")
        if status_message and "✅ RESOLVED" in status_message:
            resolved_services_list.append((service, data))
        elif status_message and "📝 NOTED" in status_message:
            noted_services_list.append((service, data))
        else:
            unresolved_services_list.append((service, data))

    # Sort all lists by cost (highest first)
    unresolved_services_list.sort(key=lambda x: x[1]["cost"], reverse=True)
    noted_services_list.sort(key=lambda x: x[1]["cost"], reverse=True)
    resolved_services_list.sort(key=lambda x: x[1]["cost"], reverse=True)

    # Combine lists: unresolved first, then noted, then resolved
    sorted_services = unresolved_services_list + noted_services_list + resolved_services_list

    for service, data in sorted_services:
        service_cost = data["cost"]
        percentage = (service_cost / total_cost * 100) if total_cost > 0 else 0

        # Check if this service has been resolved
        status_message = resolved_services.get(service.upper(), "")

        print(f"\n{service.upper()}")
        print("=" * 120)
        print(f"Total Cost: ${service_cost:,.2f} ({percentage:.1f}% of total)")

        # Show resolution status if applicable
        if status_message:
            print(f"🔧 STATUS: {status_message}")

        # Show regional breakdown
        print(f"\nRegional Breakdown:")
        print(f"{'Region':<25} {'Cost':<15} {'% of Service':<15}")
        print("-" * 55)

        sorted_regions = sorted(data["regions"].items(), key=lambda x: x[1], reverse=True)
        for region, region_cost in sorted_regions:
            if region_cost > 0:
                region_percentage = (region_cost / service_cost * 100) if service_cost > 0 else 0
                print(f"{region:<25} ${region_cost:>12.2f} {region_percentage:>12.1f}%")

        # Show usage details for this service
        if service in service_usage and service_usage[service]:
            print(f"\nUsage Details:")
            print(f"{'Usage Type':<50} {'Quantity':<20} {'Unit':<15}")
            print("-" * 85)

            # Sort usage by quantity (highest first) and show top 10
            sorted_usage = sorted(service_usage[service], key=lambda x: x[1], reverse=True)[:10]
            for usage_type, quantity, unit in sorted_usage:
                print(f"{usage_type:<50} {quantity:>17,.2f} {unit:<15}")

        print("-" * 120)

    print(f"\nTOTAL AWS COST: ${total_cost:,.2f}")
    print("=" * 120)


def main():
    """Main function to run the billing report"""
    # Clear screen before running
    clear_screen()

    print("AWS Billing Report Generator")
    print("=" * 80)

    # Get combined billing and usage data
    cost_data, usage_data = get_combined_billing_data()
    if cost_data:
        format_combined_billing_report(cost_data, usage_data)
    else:
        print("Failed to retrieve billing data. Please check your AWS credentials and permissions.")


if __name__ == "__main__":
    main()
