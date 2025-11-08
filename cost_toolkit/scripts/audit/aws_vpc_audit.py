#!/usr/bin/env python3

import json
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def get_all_regions():
    """Get list of all AWS regions"""
    ec2 = boto3.client("ec2", region_name="us-east-1")
    try:
        response = ec2.describe_regions()
        return [region["RegionName"] for region in response["Regions"]]
    except ClientError as e:
        print(f"Error getting regions: {e}")
        return ["us-east-1", "us-east-2", "us-west-2", "eu-west-1", "eu-west-2"]


def audit_elastic_ips_in_region(region_name):
    """Audit Elastic IP addresses in a specific region"""
    print(f"\n🔍 Auditing Elastic IPs in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        # Get all Elastic IP addresses
        response = ec2.describe_addresses()
        addresses = response.get("Addresses", [])

        if not addresses:
            print(f"✅ No Elastic IP addresses found in {region_name}")
            return []

        region_summary = []
        total_cost_estimate = 0

        for addr in addresses:
            ip_info = {
                "region": region_name,
                "public_ip": addr.get("PublicIp", "N/A"),
                "allocation_id": addr.get("AllocationId", "N/A"),
                "association_id": addr.get("AssociationId"),
                "instance_id": addr.get("InstanceId"),
                "network_interface_id": addr.get("NetworkInterfaceId"),
                "domain": addr.get("Domain", "N/A"),
                "tags": addr.get("Tags", []),
            }

            # Determine status
            if addr.get("AssociationId"):
                status = "🟢 IN USE"
                cost_per_hour = 0.005  # $0.005/hour for in-use
            else:
                status = "🔴 IDLE (COSTING MONEY)"
                cost_per_hour = 0.005  # $0.005/hour for idle

            monthly_cost = cost_per_hour * 24 * 30  # Approximate monthly cost
            total_cost_estimate += monthly_cost

            ip_info["status"] = status
            ip_info["monthly_cost_estimate"] = monthly_cost

            print(f"Public IP: {ip_info['public_ip']}")
            print(f"  Status: {status}")
            print(f"  Allocation ID: {ip_info['allocation_id']}")
            print(
                f"  Associated with: {ip_info['instance_id'] or ip_info['network_interface_id'] or 'Nothing'}"
            )
            print(f"  Domain: {ip_info['domain']}")
            print(f"  Estimated monthly cost: ${monthly_cost:.2f}")

            # Show tags if any
            if ip_info["tags"]:
                print("  Tags:")
                for tag in ip_info["tags"]:
                    print(f"    {tag['Key']}: {tag['Value']}")

            print()
            region_summary.append(ip_info)

        print(f"📊 Region Summary for {region_name}:")
        print(f"  Total Elastic IPs: {len(addresses)}")
        print(f"  Estimated monthly cost: ${total_cost_estimate:.2f}")

    except ClientError as e:
        if e.response["Error"]["Code"] == "UnauthorizedOperation":
            print(f"❌ No permission to access {region_name}")
        else:
            print(f"❌ Error auditing {region_name}: {e}")
        return []

    else:
        return region_summary


def audit_nat_gateways_in_region(region_name):
    """Audit NAT Gateways in a specific region"""
    print(f"\n🔍 Auditing NAT Gateways in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        response = ec2.describe_nat_gateways()
        nat_gateways = response.get("NatGateways", [])

        if not nat_gateways:
            print(f"✅ No NAT Gateways found in {region_name}")
            return []

        region_summary = []

        for nat in nat_gateways:
            nat_info = {
                "region": region_name,
                "nat_gateway_id": nat.get("NatGatewayId"),
                "state": nat.get("State"),
                "vpc_id": nat.get("VpcId"),
                "subnet_id": nat.get("SubnetId"),
                "create_time": nat.get("CreateTime"),
                "tags": nat.get("Tags", []),
            }

            # NAT Gateway costs approximately $0.045/hour + data processing
            monthly_cost_estimate = 0.045 * 24 * 30  # ~$32.40/month base cost

            print(f"NAT Gateway: {nat_info['nat_gateway_id']}")
            print(f"  State: {nat_info['state']}")
            print(f"  VPC: {nat_info['vpc_id']}")
            print(f"  Subnet: {nat_info['subnet_id']}")
            print(f"  Created: {nat_info['create_time']}")
            print(
                f"  Estimated monthly cost: ${monthly_cost_estimate:.2f} (base + data processing)"
            )

            if nat_info["tags"]:
                print("  Tags:")
                for tag in nat_info["tags"]:
                    print(f"    {tag['Key']}: {tag['Value']}")

            print()
            region_summary.append(nat_info)

    except ClientError as e:
        print(f"❌ Error auditing NAT Gateways in {region_name}: {e}")
        return []

    else:
        return region_summary


def main():
    print("AWS VPC Cost Audit")
    print("=" * 80)
    print("Analyzing Public IPv4 addresses and other VPC resources that incur costs...")

    # Focus on regions where we saw VPC costs
    target_regions = ["us-east-1", "eu-west-2", "us-west-2", "us-east-2"]

    all_elastic_ips = []
    all_nat_gateways = []
    total_estimated_cost = 0

    for region in target_regions:
        elastic_ips = audit_elastic_ips_in_region(region)
        nat_gateways = audit_nat_gateways_in_region(region)

        all_elastic_ips.extend(elastic_ips)
        all_nat_gateways.extend(nat_gateways)

        region_cost = sum(ip["monthly_cost_estimate"] for ip in elastic_ips)
        total_estimated_cost += region_cost

    # Summary
    print("\n" + "=" * 80)
    print("🎯 OVERALL SUMMARY")
    print("=" * 80)

    print(f"Total Elastic IP addresses found: {len(all_elastic_ips)}")
    print(f"Total NAT Gateways found: {len(all_nat_gateways)}")
    print(f"Estimated monthly cost for Elastic IPs: ${total_estimated_cost:.2f}")

    # Categorize IPs
    idle_ips = [ip for ip in all_elastic_ips if "IDLE" in ip["status"]]
    in_use_ips = [ip for ip in all_elastic_ips if "IN USE" in ip["status"]]

    print(f"\n📊 Elastic IP Breakdown:")
    print(f"  🔴 Idle (costing money): {len(idle_ips)} IPs")
    print(f"  🟢 In use: {len(in_use_ips)} IPs")

    if idle_ips:
        print(f"\n💰 COST OPTIMIZATION OPPORTUNITY:")
        print(
            f"  Releasing {len(idle_ips)} idle Elastic IPs could save ~${sum(ip['monthly_cost_estimate'] for ip in idle_ips):.2f}/month"
        )
        print(f"  These IPs are not associated with any resources and are just costing money.")

    print(f"\n📋 RECOMMENDATIONS:")
    print(f"  1. Review idle Elastic IPs - can they be released?")
    print(f"  2. Consider if all in-use IPs are actually needed")
    print(f"  3. Note: Released IPs cannot be recovered (you get a new IP if you allocate again)")
    print(f"  4. Alternative: Keep critical IPs, release unused ones")


if __name__ == "__main__":
    main()
