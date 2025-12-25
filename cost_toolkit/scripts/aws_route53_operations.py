#!/usr/bin/env python3
"""
AWS Route53 Operations Module
Common Route53 API operations extracted to reduce code duplication.
"""

from typing import Optional

from botocore.exceptions import ClientError

from cost_toolkit.common.aws_client_factory import create_route53_client


def list_hosted_zones(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> list[dict]:
    """
    List all Route53 hosted zones in the account.

    Args:
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        list: List of hosted zone dictionaries

    Raises:
        ClientError: If API call fails
    """
    route53_client = create_route53_client(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    response = route53_client.list_hosted_zones()
    hosted_zones = []
    if "HostedZones" in response:
        hosted_zones = response["HostedZones"]
    return hosted_zones


def get_hosted_zone(
    hosted_zone_id: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> dict:
    """
    Get details about a specific Route53 hosted zone.

    Args:
        hosted_zone_id: Hosted zone ID
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        dict: Hosted zone data

    Raises:
        ClientError: If API call fails
    """
    route53_client = create_route53_client(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    response = route53_client.get_hosted_zone(Id=hosted_zone_id)
    return response["HostedZone"]


def list_resource_record_sets(
    hosted_zone_id: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> list[dict]:
    """
    List all resource record sets in a hosted zone.

    Args:
        hosted_zone_id: Hosted zone ID
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        list: List of resource record set dictionaries

    Raises:
        ClientError: If API call fails
    """
    route53_client = create_route53_client(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    response = route53_client.list_resource_record_sets(HostedZoneId=hosted_zone_id)
    resource_record_sets = []
    if "ResourceRecordSets" in response:
        resource_record_sets = response["ResourceRecordSets"]
    return resource_record_sets


def create_hosted_zone(
    name: str,
    caller_reference: str,
    *,
    comment: Optional[str] = None,
    private_zone: bool = False,
    vpc_config: Optional[tuple[str, str]] = None,
    credentials: Optional[tuple[str, str]] = None,
) -> dict:
    """
    Create a new Route53 hosted zone.

    Args:
        name: Domain name for the hosted zone
        caller_reference: Unique string to ensure idempotency
        comment: Optional comment describing the hosted zone
        private_zone: Whether this is a private hosted zone
        vpc_config: Optional tuple of (vpc_id, vpc_region) for private zones
        credentials: Optional tuple of (aws_access_key_id, aws_secret_access_key)

    Returns:
        dict: Created hosted zone data

    Raises:
        ClientError: If API call fails
    """
    aws_access_key_id = credentials[0] if credentials else None
    aws_secret_access_key = credentials[1] if credentials else None

    route53_client = create_route53_client(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    params = {
        "Name": name,
        "CallerReference": caller_reference,
    }

    if comment:
        params["HostedZoneConfig"] = {"Comment": comment, "PrivateZone": private_zone}

    if private_zone and vpc_config:
        vpc_id, vpc_region = vpc_config
        params["VPC"] = {"VPCRegion": vpc_region, "VPCId": vpc_id}

    response = route53_client.create_hosted_zone(**params)
    return response["HostedZone"]


def delete_hosted_zone(
    hosted_zone_id: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> bool:
    """
    Delete a Route53 hosted zone.

    Args:
        hosted_zone_id: Hosted zone ID to delete
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        route53_client = create_route53_client(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        route53_client.delete_hosted_zone(Id=hosted_zone_id)
        print(f"✅ Deleted hosted zone: {hosted_zone_id}")

    except ClientError as e:
        print(f"❌ Failed to delete hosted zone {hosted_zone_id}: {str(e)}")
        return False
    return True


def change_resource_record_sets(
    hosted_zone_id: str,
    changes: list[dict],
    comment: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> dict:
    """
    Make changes to resource record sets in a hosted zone.

    Args:
        hosted_zone_id: Hosted zone ID
        changes: List of change dictionaries (Action, ResourceRecordSet)
        comment: Optional comment describing the changes
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        dict: Change info including change ID and status

    Raises:
        ClientError: If API call fails
    """
    route53_client = create_route53_client(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    params = {
        "HostedZoneId": hosted_zone_id,
        "ChangeBatch": {"Changes": changes},
    }

    if comment:
        params["ChangeBatch"]["Comment"] = comment

    response = route53_client.change_resource_record_sets(**params)
    return response["ChangeInfo"]


def get_change(
    change_id: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> dict:
    """
    Get the status of a Route53 change request.

    Args:
        change_id: Change ID to check
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        dict: Change info including status (PENDING or INSYNC)

    Raises:
        ClientError: If API call fails
    """
    route53_client = create_route53_client(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    response = route53_client.get_change(Id=change_id)
    return response["ChangeInfo"]


def list_domains(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> list[dict]:
    """
    List all registered domains in Route53 Domains.

    Args:
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        list: List of domain dictionaries

    Raises:
        ClientError: If API call fails
    """
    # Note: This requires route53domains client, not route53
    # For now, fail fast so the caller knows this path is not implemented.
    _ = (aws_access_key_id, aws_secret_access_key)  # Reserved for future use
    raise NotImplementedError("Route53Domains listing is not implemented; use boto3 route53domains client directly.")


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit("This module is library-only; use a CLI that imports it.")
