"""
Shared Route53 utilities to reduce code duplication.

Common Route53 operations used across multiple scripts.
"""


def parse_hosted_zone(zone):
    """
    Parse and extract key information from a Route53 hosted zone.

    Args:
        zone: Route53 hosted zone dict

    Returns:
        dict: Parsed zone information with zone_id, zone_name, is_private, record_count
    """
    zone_id = zone["Id"].split("/")[-1]  # Remove /hostedzone/ prefix
    zone_name = zone["Name"]
    config = zone.get("Config", {})
    is_private = config.get("PrivateZone", False)
    record_count = zone.get("ResourceRecordSetCount", 0)

    return {
        "zone_id": zone_id,
        "zone_name": zone_name,
        "is_private": is_private,
        "record_count": record_count,
    }
