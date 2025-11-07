#!/usr/bin/env python3

import json
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def audit_flow_logs_in_region(region_name):
    """Audit VPC Flow Logs in a specific region"""
    print(f"\n🔍 Auditing VPC Flow Logs in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)
        logs_client = boto3.client("logs", region_name=region_name)

        # Get VPC Flow Logs
        response = ec2.describe_flow_logs()
        flow_logs = response.get("FlowLogs", [])

        if not flow_logs:
            print(f"✅ No VPC Flow Logs found in {region_name}")
            return []

        region_summary = []

        for flow_log in flow_logs:
            flow_info = {
                "region": region_name,
                "flow_log_id": flow_log.get("FlowLogId"),
                "flow_log_status": flow_log.get("FlowLogStatus"),
                "resource_type": flow_log.get("ResourceType"),
                "resource_id": flow_log.get("ResourceIds", []),
                "log_destination_type": flow_log.get("LogDestinationType"),
                "log_destination": flow_log.get("LogDestination"),
                "creation_time": flow_log.get("CreationTime"),
                "tags": flow_log.get("Tags", []),
            }

            print(f"Flow Log: {flow_info['flow_log_id']}")
            print(f"  Status: {flow_info['flow_log_status']}")
            print(f"  Resource Type: {flow_info['resource_type']}")
            print(f"  Resource IDs: {flow_info['resource_id']}")
            print(f"  Destination Type: {flow_info['log_destination_type']}")
            print(f"  Destination: {flow_info['log_destination']}")
            print(f"  Created: {flow_info['creation_time']}")

            # If logging to CloudWatch, check log group size
            if flow_info["log_destination_type"] == "cloud-watch-logs":
                log_group_name = flow_info["log_destination"].split(":")[-1]
                try:
                    log_group_response = logs_client.describe_log_groups(
                        logGroupNamePrefix=log_group_name
                    )
                    for log_group in log_group_response.get("logGroups", []):
                        if log_group["logGroupName"] == log_group_name:
                            stored_bytes = log_group.get("storedBytes", 0)
                            stored_gb = stored_bytes / (1024**3)
                            # CloudWatch Logs costs ~$0.50/GB/month
                            monthly_storage_cost = stored_gb * 0.50
                            print(f"  Log Group Size: {stored_gb:.2f} GB")
                            print(f"  Estimated storage cost: ${monthly_storage_cost:.2f}/month")
                            flow_info["storage_cost"] = monthly_storage_cost
                            break
                except Exception as e:
                    print(f"  Error checking log group: {e}")

            if flow_info["tags"]:
                print("  Tags:")
                for tag in flow_info["tags"]:
                    print(f"    {tag['Key']}: {tag['Value']}")

            print()
            region_summary.append(flow_info)

        return region_summary

    except ClientError as e:
        print(f"❌ Error auditing Flow Logs in {region_name}: {e}")
        return []


def audit_additional_vpc_costs_in_region(region_name):
    """Check for other potential VPC cost sources"""
    print(f"\n🔍 Checking additional VPC cost sources in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        # Check for VPC Peering Connections
        peering_response = ec2.describe_vpc_peering_connections()
        peering_connections = peering_response.get("VpcPeeringConnections", [])
        print(f"VPC Peering Connections: {len(peering_connections)}")
        for peering in peering_connections:
            status = peering.get("Status", {}).get("Code", "Unknown")
            print(f"  Peering: {peering['VpcPeeringConnectionId']} - {status}")

        # Check for VPC Endpoints (more detailed)
        endpoints_response = ec2.describe_vpc_endpoints()
        endpoints = endpoints_response.get("VpcEndpoints", [])
        print(f"VPC Endpoints: {len(endpoints)}")
        for endpoint in endpoints:
            endpoint_type = endpoint.get("VpcEndpointType", "Unknown")
            state = endpoint.get("State", "Unknown")
            service_name = endpoint.get("ServiceName", "Unknown")
            creation_time = endpoint.get("CreationTimestamp")
            print(f"  Endpoint: {endpoint['VpcEndpointId']} ({endpoint_type})")
            print(f"    Service: {service_name}")
            print(f"    State: {state}")
            print(f"    Created: {creation_time}")

        # Check for Security Groups (large numbers can indicate complexity)
        sg_response = ec2.describe_security_groups()
        security_groups = sg_response.get("SecurityGroups", [])
        print(f"Security Groups: {len(security_groups)}")

        # Check for Network ACLs
        nacl_response = ec2.describe_network_acls()
        network_acls = nacl_response.get("NetworkAcls", [])
        print(f"Network ACLs: {len(network_acls)}")

        # Check for Route Tables
        rt_response = ec2.describe_route_tables()
        route_tables = rt_response.get("RouteTables", [])
        print(f"Route Tables: {len(route_tables)}")

        # Check for Subnets
        subnet_response = ec2.describe_subnets()
        subnets = subnet_response.get("Subnets", [])
        print(f"Subnets: {len(subnets)}")

    except ClientError as e:
        print(f"❌ Error checking additional VPC costs in {region_name}: {e}")


def main():
    print("AWS VPC Flow Logs and Additional Cost Audit")
    print("=" * 80)
    print("Analyzing VPC Flow Logs and other potential cost sources...")

    # Focus on regions where we saw VPC costs
    target_regions = ["us-east-1", "eu-west-2", "us-west-2", "us-east-2"]

    all_flow_logs = []
    total_flow_log_cost = 0

    for region in target_regions:
        flow_logs = audit_flow_logs_in_region(region)
        audit_additional_vpc_costs_in_region(region)

        all_flow_logs.extend(flow_logs)

        # Calculate flow log costs
        for flow_log in flow_logs:
            if "storage_cost" in flow_log:
                total_flow_log_cost += flow_log["storage_cost"]

    # Summary
    print("\n" + "=" * 80)
    print("🎯 FLOW LOGS & ADDITIONAL COSTS SUMMARY")
    print("=" * 80)

    print(f"Total VPC Flow Logs found: {len(all_flow_logs)}")
    print(f"Estimated Flow Logs storage cost: ${total_flow_log_cost:.2f}/month")

    if all_flow_logs:
        print(f"\n📊 Flow Logs Breakdown:")
        active_flow_logs = [fl for fl in all_flow_logs if fl["flow_log_status"] == "ACTIVE"]
        inactive_flow_logs = [fl for fl in all_flow_logs if fl["flow_log_status"] != "ACTIVE"]

        print(f"  🟢 Active Flow Logs: {len(active_flow_logs)}")
        print(f"  🔴 Inactive Flow Logs: {len(inactive_flow_logs)}")

        if active_flow_logs:
            print(f"\n💰 ACTIVE FLOW LOGS (potential cost sources):")
            for flow_log in active_flow_logs:
                print(f"  {flow_log['flow_log_id']} -> {flow_log['log_destination']}")
                if "storage_cost" in flow_log:
                    print(f"    Storage cost: ${flow_log['storage_cost']:.2f}/month")

    print(f"\n📋 COST ANALYSIS:")
    print(f"  Known Public IPv4 cost: $3.60/month")
    print(f"  Flow Logs storage cost: ${total_flow_log_cost:.2f}/month")
    print(f"  Total identified: ${3.60 + total_flow_log_cost:.2f}/month")
    print(f"  Your reported VPC cost: $9.60/month")
    print(f"  Unaccounted for: ${9.60 - 3.60 - total_flow_log_cost:.2f}/month")

    if (9.60 - 3.60 - total_flow_log_cost) > 1.0:
        print(f"\n🤔 REMAINING MYSTERY COSTS:")
        print(f"  Possible sources for the remaining ${9.60 - 3.60 - total_flow_log_cost:.2f}:")
        print(f"    - Data transfer charges (ingress/egress)")
        print(f"    - VPC DNS queries")
        print(f"    - Recently deleted resources still in billing")
        print(f"    - Resources in other regions not checked")
        print(f"    - Partial month billing calculations")


if __name__ == "__main__":
    main()
