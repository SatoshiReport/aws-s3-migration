#!/usr/bin/env python3

import json

import boto3
from botocore.exceptions import ClientError


def audit_kms_keys():
    """Audit KMS keys across all regions to identify where they're being used"""

    # Get all AWS regions
    ec2 = boto3.client("ec2", region_name="us-east-1")
    regions = [region["RegionName"] for region in ec2.describe_regions()["Regions"]]

    print("AWS KMS Key Usage Audit")
    print("=" * 80)

    total_keys = 0
    total_cost_estimate = 0

    for region in regions:
        try:
            kms = boto3.client("kms", region_name=region)

            # List all keys in this region
            keys = kms.list_keys()

            if not keys["Keys"]:
                continue

            print(f"\nRegion: {region}")
            print("-" * 40)

            region_keys = 0

            for key in keys["Keys"]:
                key_id = key["KeyId"]

                try:
                    # Get key details
                    key_details = kms.describe_key(KeyId=key_id)
                    key_info = key_details["KeyMetadata"]

                    # Skip AWS managed keys (they're free)
                    if key_info["KeyManager"] == "AWS":
                        continue

                    region_keys += 1
                    total_keys += 1

                    print(f"Key ID: {key_id}")
                    print(f"  Description: {key_info.get('Description', 'No description')}")
                    print(f"  Key Manager: {key_info['KeyManager']}")
                    print(f"  Key State: {key_info['KeyState']}")
                    print(f"  Creation Date: {key_info['CreationDate']}")

                    # Estimate cost ($1/month for customer-managed keys)
                    if key_info["KeyState"] in ["Enabled", "Disabled"]:
                        total_cost_estimate += 1
                        print(f"  Estimated Cost: $1.00/month")

                    # Try to find key usage
                    try:
                        aliases = kms.list_aliases(KeyId=key_id)
                        if aliases["Aliases"]:
                            print(
                                f"  Aliases: {[alias['AliasName'] for alias in aliases['Aliases']]}"
                            )
                    except ClientError:
                        pass

                    # Check key grants (shows what services are using the key)
                    try:
                        grants = kms.list_grants(KeyId=key_id)
                        if grants["Grants"]:
                            print(f"  Active Grants: {len(grants['Grants'])}")
                            for grant in grants["Grants"][:3]:  # Show first 3 grants
                                print(f"    - Grantee: {grant.get('GranteePrincipal', 'Unknown')}")
                                print(f"      Operations: {grant.get('Operations', [])}")
                    except ClientError:
                        pass

                    print()

                except ClientError as e:
                    if "AccessDenied" not in str(e):
                        print(f"  Error accessing key {key_id}: {e}")

            if region_keys > 0:
                print(f"Customer-managed keys in {region}: {region_keys}")

        except ClientError as e:
            if "not available" not in str(e).lower():
                print(f"Error accessing region {region}: {e}")

    print("\n" + "=" * 80)
    print(f"SUMMARY:")
    print(f"Total customer-managed KMS keys: {total_keys}")
    print(f"Estimated monthly cost: ${total_cost_estimate:.2f}")
    print(f"Note: AWS-managed keys (free) are not included in this count")

    # Additional check for VPN-related resources
    print("\n" + "=" * 80)
    print("CHECKING FOR VPN-RELATED KMS USAGE:")
    print("-" * 40)

    for region in ["us-east-1", "us-west-1", "eu-west-1"]:  # Regions with KMS costs
        try:
            ec2 = boto3.client("ec2", region_name=region)

            # Check for VPN connections
            vpn_connections = ec2.describe_vpn_connections()
            if vpn_connections["VpnConnections"]:
                print(f"\nRegion {region} - VPN Connections found:")
                for vpn in vpn_connections["VpnConnections"]:
                    print(f"  VPN ID: {vpn['VpnConnectionId']}")
                    print(f"  State: {vpn['State']}")
                    print(f"  Type: {vpn['Type']}")

            # Check for Customer Gateways
            customer_gateways = ec2.describe_customer_gateways()
            if customer_gateways["CustomerGateways"]:
                print(f"\nRegion {region} - Customer Gateways found:")
                for cgw in customer_gateways["CustomerGateways"]:
                    print(f"  Gateway ID: {cgw['CustomerGatewayId']}")
                    print(f"  State: {cgw['State']}")
                    print(f"  Type: {cgw['Type']}")

            # Check for VPN Gateways
            vpn_gateways = ec2.describe_vpn_gateways()
            if vpn_gateways["VpnGateways"]:
                print(f"\nRegion {region} - VPN Gateways found:")
                for vgw in vpn_gateways["VpnGateways"]:
                    print(f"  Gateway ID: {vgw['VpnGatewayId']}")
                    print(f"  State: {vgw['State']}")
                    print(f"  Type: {vgw['Type']}")

        except ClientError as e:
            print(f"Error checking VPN resources in {region}: {e}")


if __name__ == "__main__":
    audit_kms_keys()
