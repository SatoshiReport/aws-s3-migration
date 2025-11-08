#!/usr/bin/env python3
"""
AWS Elastic IP Audit Script
Audits all Elastic IP addresses across all AWS regions to identify:
- Allocated but unassociated Elastic IPs (these incur charges)
- Associated Elastic IPs and their attachments
- Cost implications and recommendations

Unassociated Elastic IPs cost $0.005 per hour ($3.65/month each)
"""

import os
import sys
from datetime import datetime

import boto3
from dotenv import load_dotenv


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")  # noqa: TRY003

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def get_all_regions():
    """Get list of all available AWS regions"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    ec2_client = boto3.client(
        "ec2",
        region_name="us-east-1",  # Use us-east-1 to get all regions
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    try:
        response = ec2_client.describe_regions()
        return [region["RegionName"] for region in response["Regions"]]
    except Exception as e:
        print(f"⚠️  Could not get all regions, using common ones: {e}")
        # Fallback to common regions
        return [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-west-3",
            "eu-central-1",
            "ap-southeast-1",
            "ap-southeast-2",
            "ap-northeast-1",
        ]


def audit_elastic_ips_in_region(region, aws_access_key_id, aws_secret_access_key):
    """Audit Elastic IPs in a specific region"""
    try:
        ec2_client = boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        # Get all Elastic IPs
        response = ec2_client.describe_addresses()
        addresses = response.get("Addresses", [])

        if not addresses:
            return None

        region_data = {
            "region": region,
            "total_eips": len(addresses),
            "associated_eips": [],
            "unassociated_eips": [],
            "total_monthly_cost": 0,
        }

        for address in addresses:
            eip_data = {
                "allocation_id": address.get("AllocationId", "N/A"),
                "public_ip": address.get("PublicIp", "N/A"),
                "domain": address.get("Domain", "N/A"),
                "instance_id": address.get("InstanceId", None),
                "association_id": address.get("AssociationId", None),
                "network_interface_id": address.get("NetworkInterfaceId", None),
                "private_ip": address.get("PrivateIpAddress", None),
                "tags": address.get("Tags", []),
            }

            # Check if EIP is associated
            if eip_data["instance_id"] or eip_data["network_interface_id"]:
                region_data["associated_eips"].append(eip_data)
            else:
                # Unassociated EIPs cost $0.005/hour = $3.65/month
                eip_data["monthly_cost"] = 3.65
                region_data["unassociated_eips"].append(eip_data)
                region_data["total_monthly_cost"] += 3.65

    except Exception as e:
        print(f"   ❌ Error auditing region {region}: {e}")
        return None

    else:
        return region_data


def get_instance_name(ec2_client, instance_id):
    """Get the name tag of an EC2 instance"""
    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                for tag in instance.get("Tags", []):
                    if tag["Key"] == "Name":
                        return tag["Value"]
    except:
        return "Unknown"
    else:
        return "Unnamed"


def audit_all_elastic_ips():  # noqa: C901, PLR0912, PLR0915
    """Audit Elastic IPs across all AWS regions"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    print("AWS Elastic IP Audit")
    print("=" * 80)
    print("Scanning all regions for Elastic IP addresses...")
    print("⚠️  Note: Unassociated Elastic IPs cost $0.005/hour ($3.65/month each)")
    print()

    regions = get_all_regions()
    total_eips = 0
    total_unassociated = 0
    total_monthly_cost = 0
    regions_with_eips = []

    for region in regions:
        print(f"🔍 Auditing region: {region}")

        region_data = audit_elastic_ips_in_region(region, aws_access_key_id, aws_secret_access_key)

        if region_data:
            regions_with_eips.append(region_data)
            total_eips += region_data["total_eips"]
            total_unassociated += len(region_data["unassociated_eips"])
            total_monthly_cost += region_data["total_monthly_cost"]

            print(f"   📍 Found {region_data['total_eips']} Elastic IP(s)")
            if region_data["unassociated_eips"]:
                print(
                    f"   ⚠️  {len(region_data['unassociated_eips'])} unassociated (costing ${region_data['total_monthly_cost']:.2f}/month)"
                )
        else:
            print(f"   ✅ No Elastic IPs found")

    print()
    print("=" * 80)
    print("🎯 ELASTIC IP AUDIT RESULTS")
    print("=" * 80)

    if not regions_with_eips:
        print("✅ No Elastic IPs found in any region")
        print("💰 No Elastic IP costs detected")
        return

    print(f"📊 Total Elastic IPs found: {total_eips}")
    print(f"⚠️  Unassociated Elastic IPs: {total_unassociated}")
    print(f"💰 Monthly cost from unassociated EIPs: ${total_monthly_cost:.2f}")
    print(f"💰 Annual cost from unassociated EIPs: ${total_monthly_cost * 12:.2f}")
    print()

    # Detailed breakdown by region
    for region_data in regions_with_eips:
        region = region_data["region"]
        print(f"📍 Region: {region}")
        print("-" * 40)

        # Show associated EIPs
        if region_data["associated_eips"]:
            print(f"✅ Associated Elastic IPs ({len(region_data['associated_eips'])}):")

            ec2_client = boto3.client(
                "ec2",
                region_name=region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )

            for eip in region_data["associated_eips"]:
                attachment = "Unknown"
                if eip["instance_id"]:
                    instance_name = get_instance_name(ec2_client, eip["instance_id"])
                    attachment = f"Instance: {eip['instance_id']} ({instance_name})"
                elif eip["network_interface_id"]:
                    attachment = f"Network Interface: {eip['network_interface_id']}"

                print(f"   • {eip['public_ip']} → {attachment}")

        # Show unassociated EIPs (these cost money!)
        if region_data["unassociated_eips"]:
            print(
                f"⚠️  Unassociated Elastic IPs ({len(region_data['unassociated_eips'])}) - COSTING MONEY:"
            )
            for eip in region_data["unassociated_eips"]:
                tags_str = ""
                if eip["tags"]:
                    tag_names = [f"{tag['Key']}:{tag['Value']}" for tag in eip["tags"]]
                    tags_str = f" (Tags: {', '.join(tag_names)})"

                print(
                    f"   • {eip['public_ip']} (ID: {eip['allocation_id']}) - ${eip['monthly_cost']:.2f}/month{tags_str}"
                )

        print()

    # Recommendations
    if total_unassociated > 0:
        print("💡 RECOMMENDATIONS:")
        print("=" * 80)
        print("1. Release unused Elastic IPs to eliminate charges")
        print("2. Associate Elastic IPs with running instances if needed")
        print("3. Consider using dynamic public IPs for non-production workloads")
        print()
        print("🔧 Commands to release unassociated Elastic IPs:")
        for region_data in regions_with_eips:
            if region_data["unassociated_eips"]:
                for eip in region_data["unassociated_eips"]:
                    print(
                        f"   aws ec2 release-address --allocation-id {eip['allocation_id']} --region {region_data['region']}"
                    )
        print()
        print(f"💰 Total potential monthly savings: ${total_monthly_cost:.2f}")
        print(f"💰 Total potential annual savings: ${total_monthly_cost * 12:.2f}")


if __name__ == "__main__":
    try:
        audit_all_elastic_ips()
    except Exception as e:
        print(f"❌ Script failed: {e}")
        sys.exit(1)
