"""
Shared VPC cleanup utilities.

This module provides reusable functions for VPC and related resource cleanup
to eliminate duplicate cleanup code across scripts.
"""

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
    for igw in igw_response.get("InternetGateways", []):
        igw_id = igw["InternetGatewayId"]
        print(f"  Detaching IGW {igw_id} from VPC {vpc_id}")
        try:
            ec2_client.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
            print(f"  ✅ IGW {igw_id} detached")

            print(f"  Deleting IGW {igw_id}")
            ec2_client.delete_internet_gateway(InternetGatewayId=igw_id)
            print(f"  ✅ IGW {igw_id} deleted")
            deleted_count += 1
        except ClientError as e:
            print(f"  ❌ Error with IGW {igw_id}: {e}")

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
    for endpoint in endpoints_response.get("VpcEndpoints", []):
        if endpoint["State"] != "deleted":
            endpoint_id = endpoint["VpcEndpointId"]
            print(f"  Deleting VPC Endpoint {endpoint_id}")
            try:
                ec2_client.delete_vpc_endpoint(VpcEndpointId=endpoint_id)
                print(f"  ✅ VPC Endpoint {endpoint_id} deleted")
                deleted_count += 1
            except ClientError as e:
                print(f"  ❌ Error deleting endpoint {endpoint_id}: {e}")

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
    for nat in nat_response.get("NatGateways", []):
        if nat["State"] not in ["deleted", "deleting"]:
            nat_id = nat["NatGatewayId"]
            print(f"  Deleting NAT Gateway {nat_id}")
            try:
                ec2_client.delete_nat_gateway(NatGatewayId=nat_id)
                print(f"  ✅ NAT Gateway {nat_id} deletion initiated")
                deleted_count += 1
            except ClientError as e:
                print(f"  ❌ Error deleting NAT Gateway {nat_id}: {e}")

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
    for sg in sg_response.get("SecurityGroups", []):
        if skip_default and sg["GroupName"] == "default":
            continue

        sg_id = sg["GroupId"]
        print(f"  Deleting Security Group {sg_id} ({sg['GroupName']})")
        try:
            ec2_client.delete_security_group(GroupId=sg_id)
            print(f"  ✅ Security Group {sg_id} deleted")
            deleted_count += 1
        except ClientError as e:
            print(f"  ❌ Error deleting security group {sg_id}: {e}")

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
    for nacl in nacl_response.get("NetworkAcls", []):
        if skip_default and nacl["IsDefault"]:
            continue

        nacl_id = nacl["NetworkAclId"]
        print(f"  Deleting Network ACL {nacl_id}")
        try:
            ec2_client.delete_network_acl(NetworkAclId=nacl_id)
            print(f"  ✅ Network ACL {nacl_id} deleted")
            deleted_count += 1
        except ClientError as e:
            print(f"  ❌ Error deleting network ACL {nacl_id}: {e}")

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
    for rt in rt_response.get("RouteTables", []):
        if skip_main:
            is_main = any(assoc.get("Main", False) for assoc in rt.get("Associations", []))
            if is_main:
                continue

        rt_id = rt["RouteTableId"]
        print(f"  Deleting Route Table {rt_id}")
        try:
            ec2_client.delete_route_table(RouteTableId=rt_id)
            print(f"  ✅ Route Table {rt_id} deleted")
            deleted_count += 1
        except ClientError as e:
            print(f"  ❌ Error deleting route table {rt_id}: {e}")

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
    for subnet in subnet_response.get("Subnets", []):
        subnet_id = subnet["SubnetId"]
        print(f"  Deleting Subnet {subnet_id}")
        try:
            ec2_client.delete_subnet(SubnetId=subnet_id)
            print(f"  ✅ Subnet {subnet_id} deleted")
            deleted_count += 1
        except ClientError as e:
            print(f"  ❌ Error deleting subnet {subnet_id}: {e}")

    return deleted_count


def release_elastic_ips(ec2_client, vpc_id=None):
    """
    Release Elastic IPs associated with a VPC or all unassociated Elastic IPs.

    Args:
        ec2_client: Boto3 EC2 client instance
        vpc_id: Optional VPC ID to filter by (if None, releases all unassociated EIPs)

    Returns:
        int: Number of Elastic IPs successfully released
    """
    print("Releasing Elastic IPs...")

    if vpc_id:
        addresses = ec2_client.describe_addresses(Filters=[{"Name": "domain", "Values": ["vpc"]}])
    else:
        addresses = ec2_client.describe_addresses()

    released_count = 0
    for address in addresses.get("Addresses", []):
        # Only release unassociated EIPs
        if "AssociationId" not in address:
            allocation_id = address.get("AllocationId")
            public_ip = address.get("PublicIp")

            if allocation_id:
                print(f"  Releasing EIP {public_ip} (allocation: {allocation_id})")
                try:
                    ec2_client.release_address(AllocationId=allocation_id)
                    print(f"  ✅ EIP {public_ip} released")
                    released_count += 1
                except ClientError as e:
                    print(f"  ❌ Error releasing EIP {public_ip}: {e}")

    return released_count


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
    for eni in eni_response.get("NetworkInterfaces", []):
        # Only delete ENIs that are available (not attached)
        if eni["Status"] == "available":
            eni_id = eni["NetworkInterfaceId"]
            print(f"  Deleting Network Interface {eni_id}")
            try:
                ec2_client.delete_network_interface(NetworkInterfaceId=eni_id)
                print(f"  ✅ Network Interface {eni_id} deleted")
                deleted_count += 1
            except ClientError as e:
                print(f"  ❌ Error deleting ENI {eni_id}: {e}")

    return deleted_count


def delete_vpc_and_dependencies(ec2_client, vpc_id):
    """
    Delete a VPC and all its dependencies in the correct order.

    This is a comprehensive cleanup function that attempts to delete all
    resources associated with a VPC before deleting the VPC itself.

    Args:
        ec2_client: Boto3 EC2 client instance
        vpc_id: VPC ID to delete

    Returns:
        bool: True if VPC was successfully deleted, False otherwise
    """
    print(f"\n🗑️  Deleting VPC {vpc_id}")
    print("=" * 80)

    try:
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
        ec2_client.delete_vpc(VpcId=vpc_id)
        print(f"  ✅ VPC {vpc_id} deleted successfully")
    except ClientError as e:
        print(f"❌ Error during VPC deletion process: {e}")
        return False

    return True
