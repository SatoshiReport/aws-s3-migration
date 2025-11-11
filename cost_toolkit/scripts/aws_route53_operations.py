#!/usr/bin/env python3
"""
AWS Route53 Operations Module
Common Route53 API operations extracted to reduce code duplication.
"""

from typing import Optional

from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_client_factory import create_route53_client


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
    return response.get("HostedZones", [])


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
    return response.get("HostedZone", {})


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
    return response.get("ResourceRecordSets", [])


def create_hosted_zone(
    name: str,
    caller_reference: str,
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
    return response.get("HostedZone", {})


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
    return response.get("ChangeInfo", {})


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
    return response.get("ChangeInfo", {})


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
    # For now, returning empty list as this is a different service
    # This can be expanded if needed
    _ = (aws_access_key_id, aws_secret_access_key)  # Reserved for future use
    return []


def get_hosted_zone_cost(hosted_zone_count: int, query_count: int = 0) -> dict:
    """
    Calculate the cost of Route53 hosted zones.

    Args:
        hosted_zone_count: Number of hosted zones
        query_count: Number of queries per month (for query cost estimation)

    Returns:
        dict: Cost breakdown including monthly and annual costs
    """
    # Pricing as of 2024: $0.50 per hosted zone per month
    hosted_zone_monthly_cost = hosted_zone_count * 0.50

    # Query pricing: First 1 billion queries/month: $0.40 per million
    query_monthly_cost = 0.0
    if query_count > 0:
        millions_of_queries = query_count / 1_000_000
        query_monthly_cost = millions_of_queries * 0.40

    total_monthly_cost = hosted_zone_monthly_cost + query_monthly_cost

    return {
        "hosted_zone_count": hosted_zone_count,
        "hosted_zone_monthly_cost": hosted_zone_monthly_cost,
        "query_count": query_count,
        "query_monthly_cost": query_monthly_cost,
        "total_monthly_cost": total_monthly_cost,
        "total_annual_cost": total_monthly_cost * 12,
    }
