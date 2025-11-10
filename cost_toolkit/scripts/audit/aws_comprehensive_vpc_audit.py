#!/usr/bin/env python3
"""
AWS Comprehensive VPC Audit Script
Audits all VPC resources across regions to identify unused components that can be cleaned up:
- VPCs and their usage
- Subnets and their attachments
- Security Groups and their usage
- Network ACLs
- Internet Gateways
- Route Tables
- Network Interfaces
- VPC Endpoints

Identifies orphaned resources that may be left over from terminated instances.
"""

import os
import sys

import boto3
from botocore.exceptions import ClientError
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


def get_resource_name(tags):
    """Extract Name tag from resource tags"""
    if not tags:
        return "Unnamed"
    for tag in tags:
        if tag["Key"] == "Name":
            return tag["Value"]
    return "Unnamed"


def _get_active_instances(ec2_client):
    """Get all active instances in the region."""
    instances_response = ec2_client.describe_instances(
        Filters=[
            {"Name": "instance-state-name", "Values": ["running", "stopped", "stopping", "pending"]}
        ]
    )
    active_instances = []
    for reservation in instances_response["Reservations"]:
        for instance in reservation["Instances"]:
            active_instances.append(
                {
                    "instance_id": instance["InstanceId"],
                    "vpc_id": instance.get("VpcId"),
                    "state": instance["State"]["Name"],
                    "name": get_resource_name(instance.get("Tags", [])),
                }
            )
    return active_instances


def _collect_vpc_subnets(ec2_client, vpc_id):
    """Collect all subnets for a VPC."""
    subnets_response = ec2_client.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
    subnets = []
    for subnet in subnets_response.get("Subnets", []):
        subnets.append(
            {
                "subnet_id": subnet["SubnetId"],
                "name": get_resource_name(subnet.get("Tags", [])),
                "cidr": subnet["CidrBlock"],
                "availability_zone": subnet["AvailabilityZone"],
                "available_ips": subnet["AvailableIpAddressCount"],
            }
        )
    return subnets


def _collect_vpc_security_groups(ec2_client, vpc_id):
    """Collect all security groups for a VPC."""
    sg_response = ec2_client.describe_security_groups(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )
    security_groups = []
    for sg in sg_response.get("SecurityGroups", []):
        security_groups.append(
            {
                "group_id": sg["GroupId"],
                "name": sg["GroupName"],
                "description": sg["Description"],
                "is_default": sg["GroupName"] == "default",
            }
        )
    return security_groups


def _collect_vpc_route_tables(ec2_client, vpc_id):
    """Collect all route tables for a VPC."""
    rt_response = ec2_client.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
    route_tables = []
    for rt in rt_response.get("RouteTables", []):
        route_tables.append(
            {
                "route_table_id": rt["RouteTableId"],
                "name": get_resource_name(rt.get("Tags", [])),
                "is_main": any(assoc.get("Main", False) for assoc in rt.get("Associations", [])),
                "associations": len(rt.get("Associations", [])),
                "routes": len(rt.get("Routes", [])),
            }
        )
    return route_tables


def _collect_vpc_internet_gateways(ec2_client, vpc_id):
    """Collect all internet gateways attached to a VPC."""
    igw_response = ec2_client.describe_internet_gateways(
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
    )
    internet_gateways = []
    for igw in igw_response.get("InternetGateways", []):
        internet_gateways.append(
            {
                "gateway_id": igw["InternetGatewayId"],
                "name": get_resource_name(igw.get("Tags", [])),
                "state": igw["Attachments"][0]["State"] if igw.get("Attachments") else "detached",
            }
        )
    return internet_gateways


def _collect_vpc_nat_gateways(ec2_client, vpc_id):
    """Collect all NAT gateways in a VPC."""
    nat_response = ec2_client.describe_nat_gateways(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )
    nat_gateways = []
    for nat in nat_response.get("NatGateways", []):
        nat_gateways.append(
            {
                "nat_gateway_id": nat["NatGatewayId"],
                "name": get_resource_name(nat.get("Tags", [])),
                "state": nat["State"],
                "subnet_id": nat["SubnetId"],
            }
        )
    return nat_gateways


def _collect_unused_security_groups(ec2_client):
    """Collect security groups not attached to any instances."""
    unused_security_groups = []
    all_sgs_response = ec2_client.describe_security_groups()
    for sg in all_sgs_response.get("SecurityGroups", []):
        if sg["GroupName"] != "default":
            sg_instances = ec2_client.describe_instances(
                Filters=[{"Name": "instance.group-id", "Values": [sg["GroupId"]]}]
            )
            if not sg_instances["Reservations"]:
                unused_security_groups.append(
                    {
                        "group_id": sg["GroupId"],
                        "name": sg["GroupName"],
                        "description": sg["Description"],
                        "vpc_id": sg["VpcId"],
                    }
                )
    return unused_security_groups


def _collect_unused_network_interfaces(ec2_client):
    """Collect unattached network interfaces."""
    unused_interfaces = []
    eni_response = ec2_client.describe_network_interfaces(
        Filters=[{"Name": "status", "Values": ["available"]}]
    )
    for eni in eni_response.get("NetworkInterfaces", []):
        if not eni.get("Attachment"):
            unused_interfaces.append(
                {
                    "interface_id": eni["NetworkInterfaceId"],
                    "name": get_resource_name(eni.get("TagSet", [])),
                    "vpc_id": eni["VpcId"],
                    "subnet_id": eni["SubnetId"],
                    "private_ip": eni["PrivateIpAddress"],
                }
            )
    return unused_interfaces


def _collect_vpc_endpoints(ec2_client):
    """Collect all VPC endpoints."""
    vpc_endpoints = []
    vpce_response = ec2_client.describe_vpc_endpoints()
    for vpce in vpce_response.get("VpcEndpoints", []):
        vpc_endpoints.append(
            {
                "endpoint_id": vpce["VpcEndpointId"],
                "service_name": vpce["ServiceName"],
                "vpc_id": vpce["VpcId"],
                "state": vpce["State"],
                "endpoint_type": vpce["VpcEndpointType"],
            }
        )
    return vpc_endpoints


def audit_vpc_resources_in_region(region, aws_access_key_id, aws_secret_access_key):
    """Audit VPC resources in a specific region"""
    try:
        ec2_client = boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        region_data = {
            "region": region,
            "vpcs": [],
            "unused_security_groups": [],
            "unused_network_interfaces": [],
            "vpc_endpoints": [],
            "internet_gateways": [],
            "nat_gateways": [],
            "route_tables": [],
            "network_acls": [],
        }

        vpcs_response = ec2_client.describe_vpcs()
        vpcs = vpcs_response.get("Vpcs", [])

        if not vpcs:
            return None

        active_instances = _get_active_instances(ec2_client)

        for vpc in vpcs:
            vpc_id = vpc["VpcId"]
            vpc_name = get_resource_name(vpc.get("Tags", []))
            is_default = vpc.get("IsDefault", False)

            vpc_instances = [inst for inst in active_instances if inst["vpc_id"] == vpc_id]

            vpc_data = {
                "vpc_id": vpc_id,
                "name": vpc_name,
                "cidr": vpc["CidrBlock"],
                "is_default": is_default,
                "state": vpc["State"],
                "instances": vpc_instances,
                "instance_count": len(vpc_instances),
                "subnets": _collect_vpc_subnets(ec2_client, vpc_id),
                "security_groups": _collect_vpc_security_groups(ec2_client, vpc_id),
                "route_tables": _collect_vpc_route_tables(ec2_client, vpc_id),
                "internet_gateways": _collect_vpc_internet_gateways(ec2_client, vpc_id),
                "nat_gateways": _collect_vpc_nat_gateways(ec2_client, vpc_id),
            }

            region_data["vpcs"].append(vpc_data)

        region_data["unused_security_groups"] = _collect_unused_security_groups(ec2_client)
        region_data["unused_network_interfaces"] = _collect_unused_network_interfaces(ec2_client)
        region_data["vpc_endpoints"] = _collect_vpc_endpoints(ec2_client)

    except ClientError as e:
        print(f"   ❌ Error auditing region {region}: {e}")
        return None

    return region_data


def _print_vpc_details(vpc):
    """Print details for a single VPC."""
    print(f"🏠 VPC: {vpc['vpc_id']} ({vpc['name']})")
    print(f"   CIDR: {vpc['cidr']}")
    print(f"   Default VPC: {vpc['is_default']}")
    print(f"   Active instances: {vpc['instance_count']}")

    if vpc["instances"]:
        for instance in vpc["instances"]:
            print(f"     • {instance['instance_id']} ({instance['name']}) - {instance['state']}")

    print(f"   Subnets: {len(vpc['subnets'])}")
    print(f"   Security Groups: {len(vpc['security_groups'])}")
    print(f"   Route Tables: {len(vpc['route_tables'])}")
    print(f"   Internet Gateways: {len(vpc['internet_gateways'])}")
    print(f"   NAT Gateways: {len(vpc['nat_gateways'])}")
    print()


def _print_unused_resources(region_data):
    """Print unused resources for a region."""
    if region_data["unused_security_groups"]:
        print("🔶 Unused Security Groups (can be deleted):")
        for sg in region_data["unused_security_groups"]:
            print(f"   • {sg['group_id']} ({sg['name']}) in VPC {sg['vpc_id']}")

    if region_data["unused_network_interfaces"]:
        print("🔶 Unused Network Interfaces (can be deleted):")
        for eni in region_data["unused_network_interfaces"]:
            print(f"   • {eni['interface_id']} ({eni['name']}) - {eni['private_ip']}")

    if region_data["vpc_endpoints"]:
        print("🔗 VPC Endpoints (review if needed):")
        for vpce in region_data["vpc_endpoints"]:
            print(f"   • {vpce['endpoint_id']} - {vpce['service_name']} ({vpce['state']})")

    print()


def _print_cleanup_recommendations(total_unused_resources):
    """Print cleanup recommendations."""
    if total_unused_resources > 0:
        print("💡 CLEANUP RECOMMENDATIONS:")
        print("=" * 80)
        print("1. Delete unused security groups (no cost but good hygiene)")
        print("2. Delete unused network interfaces (no cost but good hygiene)")
        print("3. Review VPC endpoints - some may have hourly charges")
        print("4. Consider consolidating VPCs if you have multiple unused ones")
        print()
        print("🔧 Cleanup commands will be provided after confirmation")


def _has_region_resources(region_data):
    """Check if region has any resources worth reporting."""
    if not region_data:
        return False
    return bool(
        region_data["vpcs"]
        or region_data["unused_security_groups"]
        or region_data["unused_network_interfaces"]
        or region_data["vpc_endpoints"]
    )


def _print_region_summary(region_data):
    """Print summary for a single region."""
    print(f"   📍 Found {len(region_data['vpcs'])} VPC(s)")
    if region_data["unused_security_groups"]:
        print(f"   🔶 {len(region_data['unused_security_groups'])} unused security groups")
    if region_data["unused_network_interfaces"]:
        print(f"   🔶 {len(region_data['unused_network_interfaces'])} unused network interfaces")
    if region_data["vpc_endpoints"]:
        print(f"   🔗 {len(region_data['vpc_endpoints'])} VPC endpoints")


def _print_detailed_results(regions_with_resources):
    """Print detailed results for all regions with resources."""
    for region_data in regions_with_resources:
        region = region_data["region"]
        print(f"📍 Region: {region}")
        print("-" * 50)

        for vpc in region_data["vpcs"]:
            _print_vpc_details(vpc)

        _print_unused_resources(region_data)


def audit_comprehensive_vpc():
    """Audit VPC resources across key AWS regions"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    print("AWS Comprehensive VPC Audit")
    print("=" * 80)
    print("Analyzing VPC resources and identifying cleanup opportunities...")
    print()

    regions = ["us-east-1", "us-east-2", "eu-west-2", "us-west-2"]

    total_vpcs = 0
    total_unused_resources = 0
    regions_with_resources = []

    for region in regions:
        print(f"🔍 Auditing region: {region}")

        region_data = audit_vpc_resources_in_region(
            region, aws_access_key_id, aws_secret_access_key
        )

        if _has_region_resources(region_data):
            regions_with_resources.append(region_data)
            total_vpcs += len(region_data["vpcs"])
            total_unused_resources += len(region_data["unused_security_groups"]) + len(
                region_data["unused_network_interfaces"]
            )
            _print_region_summary(region_data)
        else:
            print("   ✅ No VPC resources found")

    print()
    print("=" * 80)
    print("🎯 COMPREHENSIVE VPC AUDIT RESULTS")
    print("=" * 80)

    if not regions_with_resources:
        print("✅ No VPC resources found in audited regions")
        return

    print(f"📊 Total VPCs found: {total_vpcs}")
    print(f"🔶 Total unused resources: {total_unused_resources}")
    print()

    _print_detailed_results(regions_with_resources)
    _print_cleanup_recommendations(total_unused_resources)


if __name__ == "__main__":
    try:
        audit_comprehensive_vpc()
    except ClientError as e:
        print(f"❌ Script failed: {e}")
        sys.exit(1)
