"""
Extended service status checking functions for AWS billing optimization.
Contains additional AWS service check functions.
"""

import boto3
import botocore.exceptions
from botocore.exceptions import ClientError

from .service_checks import (
    PENDING_DELETION_TARGET,
    check_cloudwatch_status,
    check_global_accelerator_status,
    check_lightsail_status,
)


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
                continue

        if total_functions == 0:
            return True, "✅ RESOLVED - All Lambda functions deleted"

    except ClientError as e:
        return None, f"⚠️ ERROR - {str(e)}"

    return False, f"❌ ACTIVE - {total_functions} Lambda functions still exist"


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
                continue

        if total_filesystems == 0:
            return True, "✅ RESOLVED - All EFS file systems deleted"

    except ClientError as e:
        return None, f"⚠️ ERROR - {str(e)}"

    return False, f"❌ ACTIVE - {total_filesystems} EFS file systems still exist"


def check_route53_status():
    """Check if specific Route 53 hosted zones have been deleted"""
    try:
        route53_client = boto3.client("route53")

        # Zones that should be deleted
        target_zones = ["88.176.35.in-addr.arpa", "apicentral.ai"]

        # List all hosted zones
        response = route53_client.list_hosted_zones()
        hosted_zones = response.get("HostedZones", [])

        existing_target_zones = []
        for zone in hosted_zones:
            zone_name = zone["Name"].rstrip(".")
            if zone_name in target_zones:
                existing_target_zones.append(zone_name)

        if len(existing_target_zones) == 0:
            return (
                True,
                "✅ RESOLVED - Target hosted zones deleted (88.176.35.in-addr.arpa, apicentral.ai)",
            )
        return (
            False,
            f"❌ ACTIVE - {len(existing_target_zones)} target zones still exist: "
            f"{', '.join(existing_target_zones)}",
        )

    except ClientError as e:
        return None, f"⚠️ ERROR - {str(e)}"


def _check_kms_key_status(kms_client, key_id):
    """Check if a single KMS key is pending deletion or already deleted."""
    try:
        key_details = kms_client.describe_key(KeyId=key_id)
        key_state = key_details["KeyMetadata"]["KeyState"]
    except botocore.exceptions.ClientError as e:
        if "NotFoundException" in str(e):
            return True
        return False
    return key_state == "PendingDeletion"


def _format_kms_status(pending_deletion_count, pending_deletion_target):
    """Format status message for KMS keys."""
    if pending_deletion_count >= pending_deletion_target:
        return True, (
            "✅ RESOLVED - All "
            f"{pending_deletion_target} KMS keys scheduled for deletion (saves $4/month)"
        )
    if pending_deletion_count > 0:
        return False, (
            f"⚠️ PARTIAL - {pending_deletion_count}/{pending_deletion_target} "
            "KMS keys scheduled for deletion"
        )
    return False, "❌ ACTIVE - KMS keys still active"


def check_kms_status():
    """Check if KMS keys have been scheduled for deletion"""
    try:
        regions_to_check = ["us-west-1", "eu-west-1", "us-east-1"]

        target_keys = [
            "09e32e6e-12cf-4dd1-ad49-b651bf81e152",
            "36eabc4d-f9ec-4c48-a44c-0a3e267f096d",
            "fd385fc7-d349-4dfa-87a5-aa032d47e5bb",
            "6e4195b1-7e5d-4b9c-863b-0d33bbb8f71b",
        ]

        pending_deletion_count = 0

        for region in regions_to_check:
            try:
                kms_client = boto3.client("kms", region_name=region)

                for key_id in target_keys:
                    if _check_kms_key_status(kms_client, key_id):
                        pending_deletion_count += 1

            except botocore.exceptions.ClientError:
                continue

        return _format_kms_status(pending_deletion_count, PENDING_DELETION_TARGET)

    except ClientError as e:
        return None, f"⚠️ ERROR - {str(e)}"


def check_vpc_status():
    """Check VPC Elastic IP status"""
    try:
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
        if total_elastic_ips <= 1:
            return (
                False,
                f"📝 NOTED - {total_elastic_ips} Elastic IP locked by AWS "
                "(requires Support contact)",
            )

    except ClientError as e:
        return None, f"⚠️ ERROR - {str(e)}"

    return False, f"🔴 UNRESOLVED - {total_elastic_ips} Elastic IPs still allocated"


def _add_service_status(resolved_services, service_name, check_func):
    """Add service status to resolved_services if check returns a status."""
    resolved, status = check_func()
    if resolved is not None:
        resolved_services[service_name] = status


def get_resolved_services_status():
    """Dynamically check the status of services that can be optimized"""
    resolved_services = {}

    service_checks = [
        ("AWS GLOBAL ACCELERATOR", check_global_accelerator_status),
        ("AMAZON LIGHTSAIL", check_lightsail_status),
        ("AMAZONCLOUDWATCH", check_cloudwatch_status),
        ("AWS LAMBDA", check_lambda_status),
        ("AMAZON ELASTIC FILE SYSTEM", check_efs_status),
        ("AMAZON ROUTE 53", check_route53_status),
        ("AWS KEY MANAGEMENT SERVICE", check_kms_status),
        ("AMAZON VIRTUAL PRIVATE CLOUD", check_vpc_status),
    ]

    for service_name, check_func in service_checks:
        _add_service_status(resolved_services, service_name, check_func)

    resolved_services["AMAZONWORKMAIL"] = "📝 NOTED - Service recognized, no optimization planned"
    resolved_services["TAX"] = "📝 NOTED - Service recognized, no optimization planned"
    resolved_services["AMAZON RELATIONAL DATABASE SERVICE"] = (
        "📝 NOTED - Aurora deleted, MariaDB stopped (can restart when needed)"
    )

    return resolved_services


if __name__ == "__main__":
    pass
