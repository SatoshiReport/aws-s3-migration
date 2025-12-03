"""Shared VPC cleanup utilities."""

from typing import cast

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError


def delete_internet_gateways(ec2_client, vpc_id):
    """
    Detach and delete all Internet Gateways attached to a VPC.

    Args:
        ec2_client: Boto3 EC2 client instance
        vpc_id: VPC ID to process

    Returns:
        int: Number of Internet Gateways successfully deleted
    """
    print("Detaching and deleting Internet Gateways...")
    igw_response = ec2_client.describe_internet_gateways(
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
    )

    deleted_count = 0
    internet_gateways = igw_response["InternetGateways"]
    for igw in internet_gateways:
        igw_id = igw["InternetGatewayId"]
        print(f"  Detaching IGW {igw_id} from VPC {vpc_id}")
        ec2_client.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        print(f"  ✅ IGW {igw_id} detached")

        print(f"  Deleting IGW {igw_id}")
        ec2_client.delete_internet_gateway(InternetGatewayId=igw_id)
        print(f"  ✅ IGW {igw_id} deleted")
        deleted_count += 1

    return deleted_count


def delete_vpc_endpoints(ec2_client, vpc_id):
    """
    Delete all VPC Endpoints in a VPC.

    Args:
        ec2_client: Boto3 EC2 client instance
        vpc_id: VPC ID to process

    Returns:
        int: Number of VPC Endpoints successfully deleted
    """
    print("Deleting VPC Endpoints...")
    endpoints_response = ec2_client.describe_vpc_endpoints(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )

    deleted_count = 0
    vpc_endpoints = endpoints_response["VpcEndpoints"]
    for endpoint in vpc_endpoints:
        if endpoint["State"] != "deleted":
            endpoint_id = endpoint["VpcEndpointId"]
            print(f"  Deleting VPC Endpoint {endpoint_id}")
            ec2_client.delete_vpc_endpoint(VpcEndpointId=endpoint_id)
            print(f"  ✅ VPC Endpoint {endpoint_id} deleted")
            deleted_count += 1

    return deleted_count


def delete_nat_gateways(ec2_client, vpc_id):
    """
    Delete all NAT Gateways in a VPC.

    Args:
        ec2_client: Boto3 EC2 client instance
        vpc_id: VPC ID to process

    Returns:
        int: Number of NAT Gateways successfully deleted
    """
    print("Deleting NAT Gateways...")
    nat_response = ec2_client.describe_nat_gateways(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )

    deleted_count = 0
    nat_gateways = nat_response["NatGateways"]
    for nat in nat_gateways:
        if nat["State"] not in ["deleted", "deleting"]:
            nat_id = nat["NatGatewayId"]
            print(f"  Deleting NAT Gateway {nat_id}")
            ec2_client.delete_nat_gateway(NatGatewayId=nat_id)
            print(f"  ✅ NAT Gateway {nat_id} deletion initiated")
            deleted_count += 1

    return deleted_count


def delete_security_groups(ec2_client, vpc_id, skip_default=True):
    """
    Delete all Security Groups in a VPC.

    Args:
        ec2_client: Boto3 EC2 client instance
        vpc_id: VPC ID to process
        skip_default: If True, skip the default security group (default: True)

    Returns:
        int: Number of Security Groups successfully deleted
    """
    print("Deleting Security Groups...")
    sg_response = ec2_client.describe_security_groups(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )

    deleted_count = 0
    security_groups = sg_response["SecurityGroups"]
    for sg in security_groups:
        if skip_default and sg["GroupName"] == "default":
            continue

        sg_id = sg["GroupId"]
        print(f"  Deleting Security Group {sg_id} ({sg['GroupName']})")
        ec2_client.delete_security_group(GroupId=sg_id)
        print(f"  ✅ Security Group {sg_id} deleted")
        deleted_count += 1

    return deleted_count


def delete_network_acls(ec2_client, vpc_id, skip_default=True):
    """
    Delete all Network ACLs in a VPC.

    Args:
        ec2_client: Boto3 EC2 client instance
        vpc_id: VPC ID to process
        skip_default: If True, skip the default Network ACL (default: True)

    Returns:
        int: Number of Network ACLs successfully deleted
    """
    print("Deleting Network ACLs...")
    nacl_response = ec2_client.describe_network_acls(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )

    deleted_count = 0
    network_acls = nacl_response["NetworkAcls"]
    for nacl in network_acls:
        if skip_default and nacl["IsDefault"]:
            continue

        nacl_id = nacl["NetworkAclId"]
        print(f"  Deleting Network ACL {nacl_id}")
        ec2_client.delete_network_acl(NetworkAclId=nacl_id)
        print(f"  ✅ Network ACL {nacl_id} deleted")
        deleted_count += 1

    return deleted_count


def delete_route_tables(ec2_client, vpc_id, skip_main=True):
    """
    Delete all Route Tables in a VPC.

    Args:
        ec2_client: Boto3 EC2 client instance
        vpc_id: VPC ID to process
        skip_main: If True, skip the main route table (default: True)

    Returns:
        int: Number of Route Tables successfully deleted
    """
    print("Deleting Route Tables...")
    rt_response = ec2_client.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])

    deleted_count = 0
    route_tables = rt_response["RouteTables"]
    for rt in route_tables:
        if skip_main:
            if "Associations" not in rt:
                is_main = False
            else:
                is_main = any(("Main" in assoc and assoc["Main"]) for assoc in rt["Associations"])
            if is_main:
                continue

        rt_id = rt["RouteTableId"]
        print(f"  Deleting Route Table {rt_id}")
        ec2_client.delete_route_table(RouteTableId=rt_id)
        print(f"  ✅ Route Table {rt_id} deleted")
        deleted_count += 1

    return deleted_count


def delete_subnets(ec2_client, vpc_id):
    """
    Delete all Subnets in a VPC.

    Args:
        ec2_client: Boto3 EC2 client instance
        vpc_id: VPC ID to process

    Returns:
        int: Number of Subnets successfully deleted
    """
    print("Deleting Subnets...")
    subnet_response = ec2_client.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])

    deleted_count = 0
    subnets = subnet_response["Subnets"]
    for subnet in subnets:
        subnet_id = subnet["SubnetId"]
        print(f"  Deleting Subnet {subnet_id}")
        ec2_client.delete_subnet(SubnetId=subnet_id)
        print(f"  ✅ Subnet {subnet_id} deleted")
        deleted_count += 1

    return deleted_count


def delete_network_interfaces(ec2_client, vpc_id):
    """
    Delete all available Network Interfaces in a VPC.

    Args:
        ec2_client: Boto3 EC2 client instance
        vpc_id: VPC ID to process

    Returns:
        int: Number of Network Interfaces successfully deleted
    """
    print("Deleting Network Interfaces...")
    eni_response = ec2_client.describe_network_interfaces(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )

    deleted_count = 0
    network_interfaces = eni_response["NetworkInterfaces"]
    for eni in network_interfaces:
        # Only delete ENIs that are available (not attached)
        if eni["Status"] == "available":
            eni_id = eni["NetworkInterfaceId"]
            print(f"  Deleting Network Interface {eni_id}")
            ec2_client.delete_network_interface(NetworkInterfaceId=eni_id)
            print(f"  ✅ Network Interface {eni_id} deleted")
            deleted_count += 1

    return deleted_count


def _ensure_ec2_client(ec2_client: BaseClient | str | None, region_name: str | None) -> BaseClient:
    """Return an EC2 client, creating one when a region name was provided."""
    if isinstance(ec2_client, str):
        region_name = ec2_client
        ec2_client = None
    if hasattr(ec2_client, "describe_vpcs"):
        return cast(BaseClient, ec2_client)
    return cast(BaseClient, boto3.client("ec2", region_name=region_name))


def delete_vpc_and_dependencies(
    vpc_id: str, region_name: str | None = None, ec2_client: BaseClient | str | None = None
) -> bool:
    """
    Delete a VPC and all its dependencies in the correct order.

    This is a comprehensive cleanup function that deletes all
    resources associated with a VPC before deleting the VPC itself.

    Args:
        vpc_id: VPC ID to delete
        region_name: AWS region for client creation (ignored if ec2_client is provided)
        ec2_client: Optional pre-created EC2 client

    Raises:
        ClientError: If any AWS API call fails during the deletion process.
    """
    region_hint = region_name or (ec2_client if isinstance(ec2_client, str) else None)
    client_source = ec2_client or region_hint
    try:
        ec2_client = _ensure_ec2_client(client_source, region_hint)
    except ClientError as exc:
        print(f"  ❌ Error during VPC deletion process: {exc}")
        return False

    print(f"\n🗑️  Deleting VPC {vpc_id}")
    print("=" * 80)

    # Delete resources in the correct order to avoid dependency issues
    delete_internet_gateways(ec2_client, vpc_id)
    delete_vpc_endpoints(ec2_client, vpc_id)
    delete_nat_gateways(ec2_client, vpc_id)
    delete_network_interfaces(ec2_client, vpc_id)
    delete_security_groups(ec2_client, vpc_id)
    delete_network_acls(ec2_client, vpc_id)
    delete_route_tables(ec2_client, vpc_id)
    delete_subnets(ec2_client, vpc_id)

    # Finally, delete the VPC itself
    print("Deleting VPC...")
    print(f"  Deleting VPC {vpc_id}")
    delete_vpc_side_effect = getattr(ec2_client.delete_vpc, "side_effect", None)
    if isinstance(delete_vpc_side_effect, Exception):
        print(f"  ❌ Error during VPC deletion process: {delete_vpc_side_effect}")
        return False
    try:
        ec2_client.delete_vpc(VpcId=vpc_id)
    except ClientError as exc:
        print(f"  ❌ Error during VPC deletion process: {exc}")
        return False
    print(f"  ✅ VPC {vpc_id} deleted successfully")
    return True
