#!/usr/bin/env python3

import json
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def get_instance_connection_info(instance_id, region_name):  # noqa: C901, PLR0912, PLR0915
    """Get connection information for an EC2 instance"""
    print(f"\n🔍 Getting connection info for instance {instance_id} in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        # Get instance details
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]

        print(f"Instance ID: {instance['InstanceId']}")
        print(f"Instance Type: {instance['InstanceType']}")
        print(f"State: {instance['State']['Name']}")
        print(f"Launch Time: {instance['LaunchTime']}")

        # Network information
        print(f"\n📡 NETWORK INFORMATION:")

        # Public IP (if any)
        public_ip = instance.get("PublicIpAddress")
        if public_ip:
            print(f"  Public IP: {public_ip}")
        else:
            print(f"  Public IP: None")

        # Public DNS
        public_dns = instance.get("PublicDnsName")
        if public_dns:
            print(f"  Public DNS: {public_dns}")
        else:
            print(f"  Public DNS: None")

        # Private IP
        private_ip = instance.get("PrivateIpAddress")
        if private_ip:
            print(f"  Private IP: {private_ip}")

        # Private DNS
        private_dns = instance.get("PrivateDnsName")
        if private_dns:
            print(f"  Private DNS: {private_dns}")

        # VPC and Subnet info
        vpc_id = instance.get("VpcId")
        subnet_id = instance.get("SubnetId")
        print(f"  VPC ID: {vpc_id}")
        print(f"  Subnet ID: {subnet_id}")

        # Security Groups
        security_groups = instance.get("SecurityGroups", [])
        print(f"\n🔒 SECURITY GROUPS:")
        for sg in security_groups:
            print(f"  {sg['GroupId']} ({sg['GroupName']})")

        # Check if instance has a public subnet
        subnet_response = ec2.describe_subnets(SubnetIds=[subnet_id])
        subnet = subnet_response["Subnets"][0]
        map_public_ip = subnet.get("MapPublicIpOnLaunch", False)
        print(f"\n🌐 SUBNET CONFIGURATION:")
        print(f"  Subnet auto-assigns public IP: {map_public_ip}")

        # Check route table for internet access
        rt_response = ec2.describe_route_tables(
            Filters=[{"Name": "association.subnet-id", "Values": [subnet_id]}]
        )

        has_internet_route = False
        if rt_response["RouteTables"]:
            for route_table in rt_response["RouteTables"]:
                for route in route_table.get("Routes", []):
                    if route.get("DestinationCidrBlock") == "0.0.0.0/0":
                        gateway_id = route.get("GatewayId", "")
                        if gateway_id.startswith("igw-"):
                            has_internet_route = True
                            print(f"  Internet route via: {gateway_id}")
                            break

        if not has_internet_route:
            print(f"  Internet route: None found")

        # Connection recommendations
        print(f"\n💡 CONNECTION OPTIONS:")

        if public_ip and public_dns:
            print(f"  ✅ Direct Internet Connection:")
            print(f"     SSH: ssh -i your-key.pem ec2-user@{public_ip}")
            print(f"     SSH: ssh -i your-key.pem ec2-user@{public_dns}")
        elif public_dns and not public_ip:
            print(f"  ⚠️  Public DNS available but no public IP:")
            print(f"     SSH: ssh -i your-key.pem ec2-user@{public_dns}")
            print(f"     (This may not work without a public IP)")
        else:
            print(f"  ❌ No direct internet connection available")
            print(f"  Alternative connection methods:")
            print(f"     1. AWS Systems Manager Session Manager:")
            print(f"        aws ssm start-session --target {instance_id} --region {region_name}")
            print(f"     2. VPN or Direct Connect to VPC")
            print(f"     3. Bastion host in the same VPC")
            print(f"     4. Re-assign a public IP (will cost $3.60/month)")

        # Check if SSM is available
        try:
            ssm = boto3.client("ssm", region_name=region_name)
            ssm_response = ssm.describe_instance_information(
                Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
            )

            if ssm_response["InstanceInformationList"]:
                ssm_info = ssm_response["InstanceInformationList"][0]
                print(f"\n🔧 AWS SYSTEMS MANAGER:")
                print(f"  ✅ SSM Agent Status: {ssm_info['PingStatus']}")
                print(f"  Last Ping: {ssm_info['LastPingDateTime']}")
                print(f"  Platform: {ssm_info['PlatformType']} {ssm_info['PlatformVersion']}")
                print(f"  Connection command:")
                print(f"    aws ssm start-session --target {instance_id} --region {region_name}")
            else:
                print(f"\n🔧 AWS SYSTEMS MANAGER:")
                print(f"  ❌ SSM Agent not responding or not installed")
        except Exception as e:
            print(f"\n🔧 AWS SYSTEMS MANAGER:")
            print(f"  ⚠️  Could not check SSM status: {e}")

        # Tags
        tags = instance.get("Tags", [])
        if tags:
            print(f"\n🏷️  INSTANCE TAGS:")
            for tag in tags:
                print(f"  {tag['Key']}: {tag['Value']}")

        return {
            "instance_id": instance_id,
            "public_ip": public_ip,
            "public_dns": public_dns,
            "private_ip": private_ip,
            "private_dns": private_dns,
            "has_internet_access": has_internet_route,
            "state": instance["State"]["Name"],
        }

    except ClientError as e:
        print(f"❌ Error getting instance info: {e}")
        return None


def main():
    print("AWS Instance Connection Information")
    print("=" * 80)

    # Check the specific instance
    instance_info = get_instance_connection_info("i-00c39b1ba0eba3e2d", "us-east-2")

    if instance_info:
        print(f"\n" + "=" * 80)
        print("🎯 SUMMARY")
        print("=" * 80)

        if instance_info["public_ip"] or instance_info["public_dns"]:
            print(f"✅ Instance has public connectivity")
            if instance_info["public_dns"]:
                print(f"   Primary connection: {instance_info['public_dns']}")
            if instance_info["public_ip"]:
                print(f"   IP address: {instance_info['public_ip']}")
        else:
            print(f"❌ Instance has no public connectivity")
            print(f"   Use AWS Systems Manager Session Manager for access")
            print(
                f"   Command: aws ssm start-session --target i-00c39b1ba0eba3e2d --region us-east-2"
            )


if __name__ == "__main__":
    main()
