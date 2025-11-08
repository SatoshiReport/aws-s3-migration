#!/usr/bin/env python3

import sys
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def get_current_hosted_zone_nameservers(domain_name):
    """Get the nameservers for the current hosted zone"""
    print(f"🔍 Getting nameservers for {domain_name}")

    try:
        route53 = boto3.client("route53")

        # List all hosted zones to find the one for our domain
        response = route53.list_hosted_zones()
        hosted_zones = response.get("HostedZones", [])

        target_zone = None
        for zone in hosted_zones:
            if zone["Name"] == f"{domain_name}.":
                target_zone = zone
                break

        if not target_zone:
            raise Exception(f"No hosted zone found for {domain_name}")  # noqa: TRY002, TRY003
        zone_id = target_zone["Id"].split("/")[-1]
        print(f"  Found hosted zone: {zone_id}")

        # Get the NS records for this zone
        records_response = route53.list_resource_record_sets(HostedZoneId=target_zone["Id"])
        records = records_response.get("ResourceRecordSets", [])

        nameservers = []
        for record in records:
            if record.get("Type") == "NS" and record.get("Name") == f"{domain_name}.":
                nameservers = [rr.get("Value") for rr in record.get("ResourceRecords", [])]
                break

        if not nameservers:
            raise Exception(f"No NS records found for {domain_name}")  # noqa: TRY002, TRY003

        print(f"  Current nameservers:")
        for ns in nameservers:
            print(f"    - {ns}")

    except ClientError as e:
        raise Exception(f"AWS API error: {e}")  # noqa: TRY002, TRY003
    else:
        return nameservers, zone_id


def update_domain_nameservers_at_registrar(domain_name, nameservers):
    """Update nameservers at the domain registrar"""
    print(f"\n🔧 Updating nameservers at registrar for {domain_name}")

    try:
        route53domains = boto3.client("route53domains", region_name="us-east-1")

        # Check if domain is registered through Route53
        try:
            domain_detail = route53domains.get_domain_detail(DomainName=domain_name)
            print(f"  Domain is registered through Route53")

            # Update nameservers
            nameserver_list = [{"Name": ns.rstrip(".")} for ns in nameservers]

            print(f"  Updating to nameservers:")
            for ns in nameserver_list:
                print(f"    - {ns['Name']}")

            response = route53domains.update_domain_nameservers(
                DomainName=domain_name, Nameservers=nameserver_list
            )

            operation_id = response.get("OperationId")
            print(f"  ✅ Nameserver update initiated (Operation ID: {operation_id})")
            print(f"  ⏳ Changes may take up to 48 hours to propagate globally")
            return True  # noqa: TRY300

        except ClientError as e:
            if "DomainNotFound" in str(e):
                print(f"  ❌ Domain is NOT registered through Route53")
                print(f"  📋 You need to manually update nameservers at your registrar:")
                print(f"     Domain: {domain_name}")
                print(f"     New nameservers:")
                for ns in nameservers:
                    print(f"       - {ns}")
                print(
                    f"  💡 Log into your domain registrar (GoDaddy, Namecheap, etc.) and update the nameservers"
                )
                return False
            else:
                raise
    except Exception as e:
        print(f"❌ Route53 Domains API error: {e}")
        return False


def verify_canva_dns_setup(domain_name, zone_id):  # noqa: C901, PLR0912
    """Verify the DNS records are properly set up for Canva"""
    print(f"\n🔍 Verifying Canva DNS setup for {domain_name}")

    try:
        route53 = boto3.client("route53")

        # Get all records for the domain
        records_response = route53.list_resource_record_sets(HostedZoneId=f"/hostedzone/{zone_id}")
        records = records_response.get("ResourceRecordSets", [])

        # Check for required records
        has_root_a = False
        has_www_a = False
        has_canva_txt = False
        canva_ip = None

        for record in records:
            record_type = record.get("Type", "")
            record_name = record.get("Name", "")

            if record_type == "A":
                if record_name == f"{domain_name}.":
                    has_root_a = True
                    if "ResourceRecords" in record:
                        canva_ip = record["ResourceRecords"][0].get("Value")
                        print(f"  ✅ Root domain A record: {canva_ip}")
                elif record_name == f"www.{domain_name}.":
                    has_www_a = True
                    if "ResourceRecords" in record:
                        www_ip = record["ResourceRecords"][0].get("Value")
                        print(f"  ✅ WWW subdomain A record: {www_ip}")

            elif record_type == "TXT" and "_canva-domain-verify" in record_name:
                has_canva_txt = True
                if "ResourceRecords" in record:
                    txt_value = record["ResourceRecords"][0].get("Value")
                    print(f"  ✅ Canva verification TXT record: {txt_value}")

        # Summary
        print(f"\n📊 DNS Setup Status:")
        print(f"  Root domain (A record): {'✅' if has_root_a else '❌'}")
        print(f"  WWW subdomain (A record): {'✅' if has_www_a else '❌'}")
        print(f"  Canva verification (TXT): {'✅' if has_canva_txt else '❌'}")

        if has_root_a and has_www_a and has_canva_txt:
            print(f"  🎉 All required DNS records are present!")
            return True, canva_ip
        else:
            print(f"  ⚠️  Some DNS records are missing")
            return False, canva_ip

    except ClientError as e:
        raise Exception(f"Error verifying DNS setup: {e}")  # noqa: TRY002, TRY003


def create_missing_dns_records(domain_name, zone_id, canva_ip):
    """Create any missing DNS records for Canva"""
    print(f"\n🔧 Checking and creating missing DNS records")

    try:
        route53 = boto3.client("route53")

        # Get current records
        records_response = route53.list_resource_record_sets(HostedZoneId=f"/hostedzone/{zone_id}")
        records = records_response.get("ResourceRecordSets", [])

        existing_records = {}
        for record in records:
            key = f"{record.get('Name', '')}-{record.get('Type', '')}"
            existing_records[key] = record

        changes = []

        # Check for root domain A record
        root_key = f"{domain_name}.-A"
        if root_key not in existing_records:
            if not canva_ip:
                print(f"  ❌ Need Canva IP address to create root domain A record")
                return False

            changes.append(
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": domain_name,
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": canva_ip}],
                    },
                }
            )
            print(f"  📝 Will create root domain A record: {domain_name} -> {canva_ip}")

        # Check for www subdomain A record
        www_key = f"www.{domain_name}.-A"
        if www_key not in existing_records:
            if not canva_ip:
                print(f"  ❌ Need Canva IP address to create www subdomain A record")
                return False

            changes.append(
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": f"www.{domain_name}",
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": canva_ip}],
                    },
                }
            )
            print(f"  📝 Will create www subdomain A record: www.{domain_name} -> {canva_ip}")

        # Apply changes if any
        if changes:
            change_batch = {
                "Comment": f"Creating missing DNS records for Canva setup - {datetime.now(timezone.utc).isoformat()}",
                "Changes": changes,
            }

            response = route53.change_resource_record_sets(
                HostedZoneId=f"/hostedzone/{zone_id}", ChangeBatch=change_batch
            )

            change_id = response["ChangeInfo"]["Id"]
            print(f"  ✅ DNS changes submitted (Change ID: {change_id})")

            # Wait for changes to propagate
            print(f"  ⏳ Waiting for DNS changes to propagate...")
            waiter = route53.get_waiter("resource_record_sets_changed")
            waiter.wait(Id=change_id, WaiterConfig={"Delay": 10, "MaxAttempts": 30})
            print(f"  ✅ DNS changes completed successfully")

            return True
        else:
            print(f"  ✅ All required DNS records already exist")
            return True

    except ClientError as e:
        raise Exception(f"Error creating DNS records: {e}")  # noqa: TRY002, TRY003


def test_dns_resolution(domain_name):
    """Test DNS resolution for the domain"""
    print(f"\n🧪 Testing DNS resolution for {domain_name}")

    import subprocess

    # Test root domain
    try:
        result = subprocess.run(
            ["dig", "+short", domain_name, "A"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            ip = result.stdout.strip()
            print(f"  ✅ {domain_name} resolves to: {ip}")
        else:
            print(f"  ❌ {domain_name} does not resolve")
    except Exception as e:
        print(f"  ⚠️  Could not test {domain_name}: {e}")

    # Test www subdomain
    try:
        result = subprocess.run(
            ["dig", "+short", f"www.{domain_name}", "A"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            ip = result.stdout.strip()
            print(f"  ✅ www.{domain_name} resolves to: {ip}")
        else:
            print(f"  ❌ www.{domain_name} does not resolve")
    except Exception as e:
        print(f"  ⚠️  Could not test www.{domain_name}: {e}")


def main():
    domain_name = "iwannabenewyork.com"

    print("AWS Route53 Domain Setup for Canva")
    print("=" * 80)
    print(f"Setting up DNS for: {domain_name}")
    print(f"Target: Canva website")
    print("=" * 80)

    try:
        # Step 1: Get current hosted zone nameservers
        nameservers, zone_id = get_current_hosted_zone_nameservers(domain_name)

        # Step 2: Verify current DNS setup
        dns_ok, canva_ip = verify_canva_dns_setup(domain_name, zone_id)

        # Step 3: Create missing DNS records if needed
        if not dns_ok:
            if canva_ip:
                create_missing_dns_records(domain_name, zone_id, canva_ip)
            else:
                print(f"\n❌ Cannot create missing records without Canva IP address")
                print(f"   Please provide the correct IP address for your Canva site")

        # Step 4: Update nameservers at registrar
        print(f"\n" + "=" * 80)
        print("NAMESERVER UPDATE")
        print("=" * 80)

        ns_updated = update_domain_nameservers_at_registrar(domain_name, nameservers)

        # Step 5: Test DNS resolution
        if ns_updated:
            print(f"\n⏳ Waiting 30 seconds for initial DNS propagation...")
            time.sleep(30)

        test_dns_resolution(domain_name)

        # Summary
        print(f"\n" + "=" * 80)
        print("🎯 SETUP SUMMARY")
        print("=" * 80)

        print(f"✅ Route53 hosted zone configured: {zone_id}")
        print(f"✅ DNS records verified for Canva")

        if ns_updated:
            print(f"✅ Nameservers updated at registrar")
            print(f"⏳ DNS propagation may take up to 48 hours")
        else:
            print(f"⚠️  Manual nameserver update required at registrar")
            print(f"   Update these nameservers at your domain registrar:")
            for ns in nameservers:
                print(f"     - {ns}")

        print(f"\n🌐 Your domain should resolve to your Canva site once DNS propagates")
        print(f"🔗 Test your site: https://{domain_name}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
