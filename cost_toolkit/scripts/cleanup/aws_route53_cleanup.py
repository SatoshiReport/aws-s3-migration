#!/usr/bin/env python3

import json
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def delete_health_check(health_check_id):
    """Delete a Route 53 health check"""
    print(f"\n🗑️  Deleting Health Check: {health_check_id}")
    print("=" * 80)

    try:
        route53 = boto3.client("route53")

        # Get health check details first
        try:
            hc_response = route53.get_health_check(HealthCheckId=health_check_id)
            hc_config = hc_response["HealthCheck"]["HealthCheckConfig"]
            hc_type = hc_config.get("Type", "Unknown")

            if hc_type in ["HTTP", "HTTPS"]:
                fqdn = hc_config.get("FullyQualifiedDomainName", "")
                port = hc_config.get("Port", "")
                path = hc_config.get("ResourcePath", "")
                target = f"{hc_type.lower()}://{fqdn}:{port}{path}"
                print(f"  Target: {target}")

            print(f"  Type: {hc_type}")

        except ClientError as e:
            print(f"  Warning: Could not get health check details: {e}")

        # Delete the health check
        route53.delete_health_check(HealthCheckId=health_check_id)
        print(f"  ✅ Health check {health_check_id} deleted successfully")
        print(f"  💰 Monthly savings: $0.50")

        return True

    except ClientError as e:
        print(f"  ❌ Error deleting health check {health_check_id}: {e}")
        return False


def delete_hosted_zone(zone_name, zone_id):
    """Delete a Route 53 hosted zone"""
    print(f"\n🗑️  Deleting Hosted Zone: {zone_name}")
    print("=" * 80)

    try:
        route53 = boto3.client("route53")

        print(f"  Zone ID: {zone_id}")
        print(f"  Zone Name: {zone_name}")

        # Step 1: Get all records in the zone
        print(f"  Step 1: Getting all DNS records...")
        records_response = route53.list_resource_record_sets(HostedZoneId=f"/hostedzone/{zone_id}")
        records = records_response.get("ResourceRecordSets", [])

        # Step 2: Delete all records except NS and SOA (which can't be deleted)
        print(f"  Step 2: Deleting DNS records...")
        records_to_delete = []

        for record in records:
            record_type = record.get("Type", "")
            record_name = record.get("Name", "")

            # Skip NS and SOA records (these are managed by AWS and can't be deleted)
            if record_type in ["NS", "SOA"]:
                print(f"    Skipping {record_type} record: {record_name}")
                continue

            records_to_delete.append(record)
            print(f"    Will delete {record_type} record: {record_name}")

        # Delete records in batches
        if records_to_delete:
            print(f"  Deleting {len(records_to_delete)} DNS records...")

            # Create change batch
            changes = []
            for record in records_to_delete:
                changes.append({"Action": "DELETE", "ResourceRecordSet": record})

            # Submit the change batch
            change_batch = {
                "Comment": f"Deleting all records before zone deletion",
                "Changes": changes,
            }

            try:
                change_response = route53.change_resource_record_sets(
                    HostedZoneId=f"/hostedzone/{zone_id}", ChangeBatch=change_batch
                )

                change_id = change_response["ChangeInfo"]["Id"]
                print(f"    Change submitted: {change_id}")

                # Wait for changes to propagate
                print(f"    Waiting for DNS changes to propagate...")
                waiter = route53.get_waiter("resource_record_sets_changed")
                waiter.wait(Id=change_id, WaiterConfig={"Delay": 10, "MaxAttempts": 30})
                print(f"    ✅ DNS records deleted successfully")

            except ClientError as e:
                print(f"    ❌ Error deleting DNS records: {e}")
                return False
        else:
            print(f"  No custom DNS records to delete")

        # Step 3: Delete the hosted zone
        print(f"  Step 3: Deleting hosted zone...")
        route53.delete_hosted_zone(Id=f"/hostedzone/{zone_id}")
        print(f"  ✅ Hosted zone {zone_name} deleted successfully")
        print(f"  💰 Monthly savings: $0.50")

        return True

    except ClientError as e:
        print(f"  ❌ Error deleting hosted zone {zone_name}: {e}")
        return False


def main():
    print("AWS Route 53 Cleanup")
    print("=" * 80)
    print("Removing health check and specified hosted zones...")

    # Resources to delete based on the audit
    health_check_id = "ba40de25-4233-4d5c-83ee-2aa058f62fde"

    zones_to_delete = [
        ("lucasahrens.com.", "Z2UJB81SP0DSN5"),
        ("iwannabenewyork.com.", "Z02247451EYLYTZRVX4QB"),
    ]

    print(f"\n⚠️  WARNING: This will delete:")
    print(f"  - 1 health check (monitoring satoshi.report)")
    print(f"  - 2 hosted zones (lucasahrens.com, iwannabenewyork.com)")
    print(f"  - All DNS records in those zones")
    print(f"")
    print(f"💰 Total monthly savings: $1.50")
    print(f"")
    print(f"🚨 IMPORTANT:")
    print(f"  - lucasahrens.com and iwannabenewyork.com will stop working")
    print(f"  - You'll need to set up DNS elsewhere if you want to use these domains")
    print(f"  - satoshi.report will remain fully functional")

    results = []

    # Delete health check
    print(f"\n" + "=" * 80)
    print("DELETING HEALTH CHECK")
    print("=" * 80)

    hc_success = delete_health_check(health_check_id)
    results.append(("Health Check", hc_success))

    # Delete hosted zones
    print(f"\n" + "=" * 80)
    print("DELETING HOSTED ZONES")
    print("=" * 80)

    for zone_name, zone_id in zones_to_delete:
        zone_success = delete_hosted_zone(zone_name, zone_id)
        results.append((zone_name, zone_success))

        # Small delay between zone deletions
        if zone_success:
            time.sleep(5)

    # Summary
    print(f"\n" + "=" * 80)
    print("🎯 CLEANUP SUMMARY")
    print("=" * 80)

    successful_deletions = [item for item, success in results if success]
    failed_deletions = [item for item, success in results if not success]

    print(f"✅ Successfully deleted: {len(successful_deletions)}")
    for item in successful_deletions:
        print(f"  {item}")

    if failed_deletions:
        print(f"\n❌ Failed to delete: {len(failed_deletions)}")
        for item in failed_deletions:
            print(f"  {item}")

    # Calculate savings
    total_savings = 0
    if ("Health Check", True) in results:
        total_savings += 0.50

    for zone_name, zone_id in zones_to_delete:
        if (zone_name, True) in results:
            total_savings += 0.50

    print(f"\n💰 COST SAVINGS:")
    print(f"  Monthly savings: ${total_savings:.2f}")
    print(f"  Annual savings: ${total_savings * 12:.2f}")

    print(f"\n📊 REMAINING ROUTE 53 COSTS:")
    print(f"  satoshi.report hosted zone: $0.50/month")
    print(f"  DNS queries: ~$0.07/month")
    print(f"  New estimated total: ~$0.57/month (down from $1.57)")

    print(f"\n🔧 NEXT STEPS:")
    if successful_deletions:
        print(f"  1. lucasahrens.com and iwannabenewyork.com will stop resolving")
        print(f"  2. If you need these domains to work, set up DNS elsewhere:")
        print(f"     - Cloudflare (free)")
        print(f"     - Your domain registrar's DNS")
        print(f"     - Other DNS providers")
        print(f"  3. satoshi.report remains fully functional")


if __name__ == "__main__":
    main()
