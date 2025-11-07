#!/usr/bin/env python3

import json
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def delete_vpc_and_dependencies(vpc_id, region_name):
    """Delete a VPC and all its dependencies in the correct order"""
    print(f"\n🗑️  Deleting VPC {vpc_id} in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        # Step 1: Detach and delete Internet Gateways
        print(f"Step 1: Detaching and deleting Internet Gateways...")
        igw_response = ec2.describe_internet_gateways(
            Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
        )

        for igw in igw_response.get("InternetGateways", []):
            igw_id = igw["InternetGatewayId"]
            print(f"  Detaching IGW {igw_id} from VPC {vpc_id}")
            try:
                ec2.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
                print(f"  ✅ IGW {igw_id} detached")

                print(f"  Deleting IGW {igw_id}")
                ec2.delete_internet_gateway(InternetGatewayId=igw_id)
                print(f"  ✅ IGW {igw_id} deleted")
            except ClientError as e:
                print(f"  ❌ Error with IGW {igw_id}: {e}")

        # Step 2: Delete VPC Endpoints
        print(f"Step 2: Deleting VPC Endpoints...")
        endpoints_response = ec2.describe_vpc_endpoints(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        )

        for endpoint in endpoints_response.get("VpcEndpoints", []):
            if endpoint["State"] != "deleted":
                endpoint_id = endpoint["VpcEndpointId"]
                print(f"  Deleting VPC Endpoint {endpoint_id}")
                try:
                    ec2.delete_vpc_endpoint(VpcEndpointId=endpoint_id)
                    print(f"  ✅ VPC Endpoint {endpoint_id} deleted")
                except ClientError as e:
                    print(f"  ❌ Error deleting endpoint {endpoint_id}: {e}")

        # Step 3: Delete NAT Gateways (if any)
        print(f"Step 3: Deleting NAT Gateways...")
        nat_response = ec2.describe_nat_gateways(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])

        for nat in nat_response.get("NatGateways", []):
            if nat["State"] not in ["deleted", "deleting"]:
                nat_id = nat["NatGatewayId"]
                print(f"  Deleting NAT Gateway {nat_id}")
                try:
                    ec2.delete_nat_gateway(NatGatewayId=nat_id)
                    print(f"  ✅ NAT Gateway {nat_id} deletion initiated")
                except ClientError as e:
                    print(f"  ❌ Error deleting NAT Gateway {nat_id}: {e}")

        # Step 4: Delete Security Groups (except default)
        print(f"Step 4: Deleting Security Groups...")
        sg_response = ec2.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])

        for sg in sg_response.get("SecurityGroups", []):
            if sg["GroupName"] != "default":
                sg_id = sg["GroupId"]
                print(f"  Deleting Security Group {sg_id} ({sg['GroupName']})")
                try:
                    ec2.delete_security_group(GroupId=sg_id)
                    print(f"  ✅ Security Group {sg_id} deleted")
                except ClientError as e:
                    print(f"  ❌ Error deleting security group {sg_id}: {e}")

        # Step 5: Delete Network ACLs (except default)
        print(f"Step 5: Deleting Network ACLs...")
        nacl_response = ec2.describe_network_acls(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])

        for nacl in nacl_response.get("NetworkAcls", []):
            if not nacl["IsDefault"]:
                nacl_id = nacl["NetworkAclId"]
                print(f"  Deleting Network ACL {nacl_id}")
                try:
                    ec2.delete_network_acl(NetworkAclId=nacl_id)
                    print(f"  ✅ Network ACL {nacl_id} deleted")
                except ClientError as e:
                    print(f"  ❌ Error deleting network ACL {nacl_id}: {e}")

        # Step 6: Delete Route Tables (except main)
        print(f"Step 6: Deleting Route Tables...")
        rt_response = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])

        for rt in rt_response.get("RouteTables", []):
            # Check if it's the main route table
            is_main = any(assoc.get("Main", False) for assoc in rt.get("Associations", []))
            if not is_main:
                rt_id = rt["RouteTableId"]
                print(f"  Deleting Route Table {rt_id}")
                try:
                    ec2.delete_route_table(RouteTableId=rt_id)
                    print(f"  ✅ Route Table {rt_id} deleted")
                except ClientError as e:
                    print(f"  ❌ Error deleting route table {rt_id}: {e}")

        # Step 7: Delete Subnets
        print(f"Step 7: Deleting Subnets...")
        subnet_response = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])

        for subnet in subnet_response.get("Subnets", []):
            subnet_id = subnet["SubnetId"]
            print(f"  Deleting Subnet {subnet_id}")
            try:
                ec2.delete_subnet(SubnetId=subnet_id)
                print(f"  ✅ Subnet {subnet_id} deleted")
            except ClientError as e:
                print(f"  ❌ Error deleting subnet {subnet_id}: {e}")

        # Step 8: Delete the VPC itself
        print(f"Step 8: Deleting VPC...")
        print(f"  Deleting VPC {vpc_id}")
        try:
            ec2.delete_vpc(VpcId=vpc_id)
            print(f"  ✅ VPC {vpc_id} deleted successfully")
            return True
        except ClientError as e:
            print(f"  ❌ Error deleting VPC {vpc_id}: {e}")
            return False

    except ClientError as e:
        print(f"❌ Error during VPC deletion process: {e}")
        return False


def main():
    print("AWS VPC Safe Deletion")
    print("=" * 80)
    print("Deleting VPCs that have no blocking resources...")

    # VPCs identified as safe to delete
    safe_vpcs = [
        ("vpc-05df0c91efb98a80a", "us-east-1"),
        ("vpc-56008731", "us-east-1"),
        ("vpc-013655b59190e0c16", "us-east-1"),
        ("vpc-0de5c0820b60ba40f", "us-west-2"),
    ]

    deletion_results = []

    for vpc_id, region in safe_vpcs:
        print(f"\n" + "=" * 80)
        print(f"DELETING VPC {vpc_id} in {region}")
        print("=" * 80)

        success = delete_vpc_and_dependencies(vpc_id, region)
        deletion_results.append((vpc_id, region, success))

        if success:
            print(f"✅ VPC {vpc_id} deletion completed successfully")
        else:
            print(f"❌ VPC {vpc_id} deletion failed")

        # Small delay between deletions
        time.sleep(2)

    # Summary
    print(f"\n" + "=" * 80)
    print("🎯 DELETION SUMMARY")
    print("=" * 80)

    successful_deletions = [result for result in deletion_results if result[2]]
    failed_deletions = [result for result in deletion_results if not result[2]]

    print(f"✅ Successfully deleted VPCs: {len(successful_deletions)}")
    for vpc_id, region, _ in successful_deletions:
        print(f"  {vpc_id} ({region})")

    if failed_deletions:
        print(f"\n❌ Failed to delete VPCs: {len(failed_deletions)}")
        for vpc_id, region, _ in failed_deletions:
            print(f"  {vpc_id} ({region})")

    print(f"\n💰 COST IMPACT:")
    if successful_deletions:
        print(f"  Deleted {len(successful_deletions)} unused VPCs and their resources")
        print(f"  This should reduce infrastructure complexity")
        print(f"  Main cost savings will come from removing the public IP ($3.60/month)")

    print(f"\n📋 REMAINING TASKS:")
    print(f"  1. Remove public IP from instance i-00c39b1ba0eba3e2d (requires stop/start)")
    print(f"  2. Consider if remaining VPCs with resources are still needed")
    print(f"  3. Monitor billing to confirm cost reduction")


if __name__ == "__main__":
    main()
