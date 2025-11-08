#!/usr/bin/env python3

import json
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

# Route 53 constants
COST_VARIANCE_THRESHOLD = 0.50  # Acceptable cost difference in dollars
DEFAULT_DNS_RECORD_COUNT = 2  # NS and SOA records
EXPECTED_HOSTED_ZONE_COUNT_1 = 3  # Common configuration
EXPECTED_HOSTED_ZONE_COUNT_2 = 2  # Alternative configuration
EXPECTED_HEALTH_CHECK_COUNT = 2  # Common health check count


def audit_route53_hosted_zones():
    """Audit Route 53 hosted zones and their costs"""
    print(f"\n🔍 Auditing Route 53 Hosted Zones")
    print("=" * 80)

    try:
        route53 = boto3.client("route53")

        # Get all hosted zones
        response = route53.list_hosted_zones()
        hosted_zones = response.get("HostedZones", [])

        if not hosted_zones:
            print("✅ No hosted zones found")
            return []

        zone_details = []
        total_monthly_cost = 0

        for zone in hosted_zones:
            zone_id = zone["Id"].split("/")[-1]  # Remove /hostedzone/ prefix
            zone_name = zone["Name"]
            is_private = zone.get("Config", {}).get("PrivateZone", False)
            record_count = zone.get("ResourceRecordSetCount", 0)

            # Calculate costs
            # Public hosted zones: $0.50/month
            # Private hosted zones: $0.50/month
            monthly_cost = 0.50
            total_monthly_cost += monthly_cost

            zone_info = {
                "zone_id": zone_id,
                "zone_name": zone_name,
                "is_private": is_private,
                "record_count": record_count,
                "monthly_cost": monthly_cost,
            }

            print(f"Hosted Zone: {zone_name}")
            print(f"  Zone ID: {zone_id}")
            print(f"  Type: {'Private' if is_private else 'Public'}")
            print(f"  Record Count: {record_count}")
            print(f"  Monthly Cost: ${monthly_cost:.2f}")

            # Get records for this zone
            try:
                records_response = route53.list_resource_record_sets(HostedZoneId=zone["Id"])
                records = records_response.get("ResourceRecordSets", [])

                print(f"  Records:")
                for record in records:
                    record_name = record.get("Name", "")
                    record_type = record.get("Type", "")
                    ttl = record.get("TTL", "N/A")

                    if record_type in ["NS", "SOA"]:
                        continue  # Skip default records

                    print(f"    {record_name} ({record_type}) TTL: {ttl}")

                    # Check for resource records
                    resource_records = record.get("ResourceRecords", [])
                    for rr in resource_records:
                        print(f"      -> {rr.get('Value', '')}")

                    # Check for alias records
                    alias_target = record.get("AliasTarget")
                    if alias_target:
                        print(f"      -> ALIAS: {alias_target.get('DNSName', '')}")

            except ClientError as e:
                print(f"  ❌ Error getting records: {e}")

            print()
            zone_details.append(zone_info)

        print(f"📊 Hosted Zones Summary:")
        print(f"  Total zones: {len(hosted_zones)}")
        print(f"  Estimated monthly cost: ${total_monthly_cost:.2f}")

    except ClientError as e:
        print(f"❌ Error auditing Route 53: {e}")
        return []

    else:
        return zone_details


def audit_route53_health_checks():
    """Audit Route 53 health checks"""
    print(f"\n🔍 Auditing Route 53 Health Checks")
    print("=" * 80)

    try:
        route53 = boto3.client("route53")

        response = route53.list_health_checks()
        health_checks = response.get("HealthChecks", [])

        if not health_checks:
            print("✅ No health checks found")
            return []

        health_check_details = []
        total_monthly_cost = 0

        for hc in health_checks:
            hc_id = hc["Id"]
            hc_config = hc.get("HealthCheckConfig", {})
            hc_type = hc_config.get("Type", "Unknown")

            # Health checks cost $0.50/month each
            monthly_cost = 0.50
            total_monthly_cost += monthly_cost

            print(f"Health Check: {hc_id}")
            print(f"  Type: {hc_type}")
            print(f"  Monthly Cost: ${monthly_cost:.2f}")

            if hc_type in {"HTTP", "HTTPS"}:
                fqdn = hc_config.get("FullyQualifiedDomainName", "")
                port = hc_config.get("Port", "")
                path = hc_config.get("ResourcePath", "")
                print(f"  Target: {hc_type.lower()}://{fqdn}:{port}{path}")

            health_check_details.append(
                {"id": hc_id, "type": hc_type, "monthly_cost": monthly_cost}
            )
            print()

        print(f"📊 Health Checks Summary:")
        print(f"  Total health checks: {len(health_checks)}")
        print(f"  Estimated monthly cost: ${total_monthly_cost:.2f}")

    except ClientError as e:
        print(f"❌ Error auditing health checks: {e}")
        return []

    else:
        return health_check_details


def audit_route53_resolver_endpoints():
    """Audit Route 53 Resolver endpoints"""
    print(f"\n🔍 Auditing Route 53 Resolver Endpoints")
    print("=" * 80)

    try:
        route53resolver = boto3.client("route53resolver")

        # Get resolver endpoints
        response = route53resolver.list_resolver_endpoints()
        endpoints = response.get("ResolverEndpoints", [])

        if not endpoints:
            print("✅ No resolver endpoints found")
            return []

        endpoint_details = []
        total_monthly_cost = 0

        for endpoint in endpoints:
            endpoint_id = endpoint["Id"]
            endpoint_name = endpoint.get("Name", "Unnamed")
            direction = endpoint.get("Direction", "Unknown")
            status = endpoint.get("Status", "Unknown")

            # Resolver endpoints cost ~$0.125/hour = ~$90/month
            monthly_cost = 90.0
            total_monthly_cost += monthly_cost

            print(f"Resolver Endpoint: {endpoint_name}")
            print(f"  ID: {endpoint_id}")
            print(f"  Direction: {direction}")
            print(f"  Status: {status}")
            print(f"  Monthly Cost: ${monthly_cost:.2f}")

            endpoint_details.append(
                {
                    "id": endpoint_id,
                    "name": endpoint_name,
                    "direction": direction,
                    "status": status,
                    "monthly_cost": monthly_cost,
                }
            )
            print()

        print(f"📊 Resolver Endpoints Summary:")
        print(f"  Total endpoints: {len(endpoints)}")
        print(f"  Estimated monthly cost: ${total_monthly_cost:.2f}")

    except ClientError as e:
        print(f"❌ Error auditing resolver endpoints: {e}")
        return []

    else:
        return endpoint_details


def main():  # noqa: PLR0912
    print("AWS Route 53 Cost Audit")
    print("=" * 80)
    print("Analyzing Route 53 resources that could be costing $1.57...")

    # Audit different Route 53 components
    hosted_zones = audit_route53_hosted_zones()
    health_checks = audit_route53_health_checks()
    resolver_endpoints = audit_route53_resolver_endpoints()

    # Calculate total costs
    total_hosted_zone_cost = sum(zone["monthly_cost"] for zone in hosted_zones)
    total_health_check_cost = sum(hc["monthly_cost"] for hc in health_checks)
    total_resolver_cost = sum(ep["monthly_cost"] for ep in resolver_endpoints)

    total_estimated_cost = total_hosted_zone_cost + total_health_check_cost + total_resolver_cost

    # Summary
    print("\n" + "=" * 80)
    print("🎯 ROUTE 53 COST BREAKDOWN")
    print("=" * 80)

    print(f"Hosted Zones: ${total_hosted_zone_cost:.2f}/month ({len(hosted_zones)} zones)")
    print(f"Health Checks: ${total_health_check_cost:.2f}/month ({len(health_checks)} checks)")
    print(
        f"Resolver Endpoints: ${total_resolver_cost:.2f}/month ({len(resolver_endpoints)} endpoints)"
    )
    print(f"Total Estimated: ${total_estimated_cost:.2f}/month")
    print(f"Your Reported Cost: $1.57")

    # Analysis
    print(f"\n💡 COST ANALYSIS:")
    if abs(total_estimated_cost - 1.57) < COST_VARIANCE_THRESHOLD:
        print(f"  ✅ Estimated cost closely matches reported cost")
    else:
        print(f"  ⚠️  Estimated cost differs from reported cost")

    # Recommendations
    print(f"\n📋 OPTIMIZATION OPPORTUNITIES:")

    if hosted_zones:
        print(f"  Hosted Zones ({len(hosted_zones)} zones):")
        for zone in hosted_zones:
            if zone["record_count"] <= DEFAULT_DNS_RECORD_COUNT:  # Only NS and SOA records
                print(f"    🗑️  {zone['zone_name']} - appears unused (only default records)")
            else:
                print(
                    f"    ✅ {zone['zone_name']} - has {zone['record_count']} records (likely in use)"
                )

    if health_checks:
        print(f"  Health Checks ({len(health_checks)} checks):")
        print(f"    💡 Review if all health checks are necessary")
        print(f"    💰 Each health check costs $0.50/month")

    if resolver_endpoints:
        print(f"  Resolver Endpoints ({len(resolver_endpoints)} endpoints):")
        print(f"    ⚠️  Very expensive! Each endpoint costs ~$90/month")
        print(f"    🔍 Review if resolver endpoints are actually needed")

    print(f"\n🎯 LIKELY EXPLANATION FOR $1.57:")
    if len(hosted_zones) == EXPECTED_HOSTED_ZONE_COUNT_1:
        print(f"  3 hosted zones × $0.50 = $1.50/month")
        print(f"  Plus DNS queries and other small charges = ~$1.57")
    elif (
        len(hosted_zones) == EXPECTED_HOSTED_ZONE_COUNT_2
        and len(health_checks) == EXPECTED_HEALTH_CHECK_COUNT
    ):
        print(f"  2 hosted zones × $0.50 + 2 health checks × $0.50 = $2.00/month")
        print(f"  Partial month billing could explain $1.57")
    else:
        print(f"  Route 53 charges include:")
        print(f"    - Hosted zones: $0.50/month each")
        print(f"    - DNS queries: $0.40 per million queries")
        print(f"    - Health checks: $0.50/month each")


if __name__ == "__main__":
    main()
