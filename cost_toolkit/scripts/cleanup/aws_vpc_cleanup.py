#!/usr/bin/env python3
"""Clean up unused VPC resources."""

from botocore.exceptions import ClientError

from cost_toolkit.common.aws_client_factory import create_client
from cost_toolkit.common.aws_common import get_all_aws_regions


def release_elastic_ips_in_region(region_name):
    """Release all Elastic IP addresses in a specific region"""
    print(f"\n🔍 Releasing Elastic IPs in {region_name}")
    print("=" * 80)

    try:
        ec2 = create_client("ec2", region=region_name)

        # Get all Elastic IP addresses
        response = ec2.describe_addresses()
        addresses = response.get("Addresses", [])

        if not addresses:
            print(f"✅ No Elastic IP addresses found in {region_name}")
            return 0

        released_count = 0
        monthly_savings = 0

        for addr in addresses:
            allocation_id = addr.get("AllocationId")
            public_ip = addr.get("PublicIp")
            association_id = addr.get("AssociationId")

            print(f"Processing IP: {public_ip} (Allocation ID: {allocation_id})")

            try:
                # If the IP is associated with an instance, disassociate it first
                if association_id:
                    print("  🔗 Disassociating from instance...")
                    ec2.disassociate_address(AssociationId=association_id)
                    print("  ✅ Disassociated successfully")

                # Release the Elastic IP
                print("  🗑️  Releasing Elastic IP...")
                ec2.release_address(AllocationId=allocation_id)
                print(f"  ✅ Released {public_ip} successfully")

                released_count += 1
                monthly_savings += 3.60  # $3.60 per month per IP

            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "InvalidAssociationID.NotFound":
                    # IP might not be associated, try to release directly
                    try:
                        ec2.release_address(AllocationId=allocation_id)
                        print(f"  ✅ Released {public_ip} successfully")
                        released_count += 1
                        monthly_savings += 3.60
                    except ClientError as e2:
                        print(f"  ❌ Failed to release {public_ip}: {e2}")
                else:
                    print(f"  ❌ Failed to process {public_ip}: {e}")

        print(f"\n📊 Region Summary for {region_name}:")
        print(f"  Released: {released_count} Elastic IPs")
        print(f"  Monthly savings: ${monthly_savings:.2f}")

    except ClientError as e:
        print(f"❌ Error accessing {region_name}: {e}")
        return 0

    return monthly_savings


def main():
    """Release all unassociated Elastic IP addresses."""
    print("AWS VPC Cleanup - Elastic IP Release")
    print("=" * 80)
    print("⚠️  WARNING: This will permanently release all Elastic IP addresses!")
    print("⚠️  Released IPs cannot be recovered - you'll get new IPs when needed.")
    print("=" * 80)

    # Confirm before proceeding
    confirmation = input("Type 'RELEASE' to confirm you want to release all Elastic IPs: ")
    if confirmation != "RELEASE":
        print("❌ Operation cancelled. No changes made.")
        return

    # Target regions where we found Elastic IPs
    target_regions = get_all_aws_regions()

    total_savings = 0

    for region in target_regions:
        savings = release_elastic_ips_in_region(region)
        total_savings += savings

    # Summary
    print("\n" + "=" * 80)
    print("🎯 CLEANUP SUMMARY")
    print("=" * 80)

    print(f"Total monthly savings: ${total_savings:.2f}")

    if total_savings > 0:
        print("\n✅ SUCCESS: Elastic IP cleanup completed!")
        print(f"💰 You will save approximately ${total_savings:.2f} per month")
        print(f"💰 Annual savings: ${total_savings * 12:.2f}")

        print("\n📋 NEXT STEPS:")
        print("  1. Your instances can still be started normally")
        print("  2. They will get new public IPs when started")
        print("  3. Update any DNS records or configurations with new IPs")
        print("  4. Consider using a load balancer if you need stable IPs")
    else:
        print("ℹ️  No Elastic IPs were found or released.")

    print("\n⚠️  IMPORTANT REMINDERS:")
    print("  - Released IP addresses cannot be recovered")
    print("  - Instances will get new public IPs when restarted")
    print("  - Update any hardcoded IP references in your applications")
    print("  - Consider using DNS names instead of IP addresses")


if __name__ == "__main__":
    main()
