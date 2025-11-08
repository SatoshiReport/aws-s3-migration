#!/usr/bin/env python3
"""
AWS Network Interface Audit Script
Identifies unused network interfaces across all regions for cleanup.
"""

import os
from datetime import datetime

import boto3
from dotenv import load_dotenv


def load_aws_credentials():
    """Load AWS credentials from environment file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")  # noqa: TRY003

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def get_all_regions():
    """Get list of all AWS regions"""
    ec2 = boto3.client("ec2", region_name="us-east-1")
    regions = ec2.describe_regions()["Regions"]
    return [region["RegionName"] for region in regions]


def audit_network_interfaces_in_region(region_name, aws_access_key_id, aws_secret_access_key):
    """Audit network interfaces in a specific region"""
    try:
        ec2 = boto3.client(
            "ec2",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        # Get all network interfaces
        response = ec2.describe_network_interfaces()
        network_interfaces = response["NetworkInterfaces"]

        if not network_interfaces:
            return None

        region_data = {
            "region": region_name,
            "total_interfaces": len(network_interfaces),
            "unused_interfaces": [],
            "attached_interfaces": [],
            "interface_details": [],
        }

        for eni in network_interfaces:
            interface_id = eni["NetworkInterfaceId"]
            status = eni["Status"]
            interface_type = eni.get("InterfaceType", "interface")
            attachment = eni.get("Attachment", {})

            # Get tags for better identification
            tags = {tag["Key"]: tag["Value"] for tag in eni.get("Tags", [])}
            name = tags.get("Name", "No Name")

            interface_info = {
                "interface_id": interface_id,
                "name": name,
                "status": status,
                "type": interface_type,
                "vpc_id": eni.get("VpcId", "N/A"),
                "subnet_id": eni.get("SubnetId", "N/A"),
                "private_ip": eni.get("PrivateIpAddress", "N/A"),
                "public_ip": eni.get("Association", {}).get("PublicIp", "None"),
                "attached_to": attachment.get("InstanceId", "Not attached"),
                "attachment_status": attachment.get("Status", "detached"),
                "description": eni.get("Description", "No description"),
                "tags": tags,
            }

            region_data["interface_details"].append(interface_info)

            # Categorize interfaces
            if status == "available" and not attachment:
                # Interface is not attached to anything
                region_data["unused_interfaces"].append(interface_info)
            else:
                region_data["attached_interfaces"].append(interface_info)

    except Exception as e:
        print(f"❌ Error auditing network interfaces in {region_name}: {str(e)}")
        return None

    else:
        return region_data


def main():  # noqa: C901, PLR0912, PLR0915
    """Main execution function"""
    print("AWS Network Interface Audit")
    print("=" * 60)

    try:
        # Load credentials
        aws_access_key_id, aws_secret_access_key = load_aws_credentials()

        # Get all regions
        regions = get_all_regions()
        print(f"🌍 Scanning {len(regions)} AWS regions for network interfaces...")
        print()

        total_interfaces = 0
        total_unused = 0
        regions_with_interfaces = []

        for region in regions:
            print(f"🔍 Checking region: {region}")
            region_data = audit_network_interfaces_in_region(
                region, aws_access_key_id, aws_secret_access_key
            )

            if region_data:
                regions_with_interfaces.append(region_data)
                total_interfaces += region_data["total_interfaces"]
                total_unused += len(region_data["unused_interfaces"])

                print(f"   📊 Found {region_data['total_interfaces']} network interfaces")
                print(f"   🔓 Unused: {len(region_data['unused_interfaces'])}")
                print(f"   🔗 Attached: {len(region_data['attached_interfaces'])}")
            else:
                print(f"   ✅ No network interfaces found")
            print()

        # Summary report
        print("=" * 60)
        print("📋 NETWORK INTERFACE AUDIT SUMMARY")
        print("=" * 60)
        print(f"🌍 Regions scanned: {len(regions)}")
        print(f"📊 Total network interfaces: {total_interfaces}")
        print(f"🔓 Unused interfaces: {total_unused}")
        print(f"🔗 Attached interfaces: {total_interfaces - total_unused}")
        print()

        if total_unused > 0:
            print("⚠️  UNUSED NETWORK INTERFACES FOUND")
            print("=" * 40)

            for region_data in regions_with_interfaces:
                if region_data["unused_interfaces"]:
                    print(f"\n📍 Region: {region_data['region']}")
                    print("-" * 30)

                    for interface in region_data["unused_interfaces"]:
                        print(f"   🔓 Interface: {interface['interface_id']}")
                        print(f"      Name: {interface['name']}")
                        print(f"      Type: {interface['type']}")
                        print(f"      VPC: {interface['vpc_id']}")
                        print(f"      Subnet: {interface['subnet_id']}")
                        print(f"      Private IP: {interface['private_ip']}")
                        print(f"      Description: {interface['description']}")
                        print(f"      Status: {interface['status']}")
                        print()

            print("💡 CLEANUP RECOMMENDATIONS:")
            print("   • Unused network interfaces can be safely deleted")
            print("   • No cost impact but improves account hygiene")
            print("   • Consider creating cleanup script for bulk deletion")
        else:
            print("🎉 No unused network interfaces found!")
            print("   Your AWS account has clean network interface configuration.")

        # Detailed report for attached interfaces
        if total_interfaces > total_unused:
            print("\n" + "=" * 60)
            print("🔗 ATTACHED NETWORK INTERFACES DETAILS")
            print("=" * 60)

            for region_data in regions_with_interfaces:
                if region_data["attached_interfaces"]:
                    print(f"\n📍 Region: {region_data['region']}")
                    print("-" * 30)

                    for interface in region_data["attached_interfaces"]:
                        print(f"   🔗 Interface: {interface['interface_id']}")
                        print(f"      Name: {interface['name']}")
                        print(f"      Type: {interface['type']}")
                        print(f"      Attached to: {interface['attached_to']}")
                        print(f"      Status: {interface['status']}")
                        print(f"      VPC: {interface['vpc_id']}")
                        print(f"      Private IP: {interface['private_ip']}")
                        print(f"      Public IP: {interface['public_ip']}")
                        print()

    except Exception as e:
        print(f"❌ Critical error during network interface audit: {str(e)}")
        raise


if __name__ == "__main__":
    main()
