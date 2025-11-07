#!/usr/bin/env python3
"""
AWS RDS and Network Interface Correlation Audit
Identifies which RDS instances are using which network interfaces and determines cleanup opportunities.
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
        raise ValueError("AWS credentials not found in ~/.env file")

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def get_all_regions():
    """Get list of all AWS regions"""
    ec2 = boto3.client("ec2", region_name="us-east-1")
    regions = ec2.describe_regions()["Regions"]
    return [region["RegionName"] for region in regions]


def audit_rds_instances_in_region(region_name, aws_access_key_id, aws_secret_access_key):
    """Audit RDS instances in a specific region"""
    try:
        rds = boto3.client(
            "rds",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        # Get RDS instances
        instances_response = rds.describe_db_instances()
        instances = instances_response["DBInstances"]

        # Get RDS clusters (for serverless)
        clusters_response = rds.describe_db_clusters()
        clusters = clusters_response["DBClusters"]

        if not instances and not clusters:
            return None

        region_data = {
            "region": region_name,
            "instances": [],
            "clusters": [],
            "total_instances": len(instances),
            "total_clusters": len(clusters),
        }

        # Process RDS instances
        for instance in instances:
            instance_info = {
                "identifier": instance["DBInstanceIdentifier"],
                "engine": instance["Engine"],
                "engine_version": instance["EngineVersion"],
                "instance_class": instance["DBInstanceClass"],
                "status": instance["DBInstanceStatus"],
                "vpc_id": instance.get("DBSubnetGroup", {}).get("VpcId", "N/A"),
                "subnet_group": instance.get("DBSubnetGroup", {}).get("DBSubnetGroupName", "N/A"),
                "subnets": [
                    subnet["SubnetIdentifier"]
                    for subnet in instance.get("DBSubnetGroup", {}).get("Subnets", [])
                ],
                "endpoint": instance.get("Endpoint", {}).get("Address", "N/A"),
                "port": instance.get("Endpoint", {}).get("Port", "N/A"),
                "publicly_accessible": instance.get("PubliclyAccessible", False),
                "multi_az": instance.get("MultiAZ", False),
                "storage_type": instance.get("StorageType", "N/A"),
                "allocated_storage": instance.get("AllocatedStorage", 0),
                "creation_time": instance.get("InstanceCreateTime", "N/A"),
            }
            region_data["instances"].append(instance_info)

        # Process RDS clusters (serverless)
        for cluster in clusters:
            cluster_info = {
                "identifier": cluster["DBClusterIdentifier"],
                "engine": cluster["Engine"],
                "engine_version": cluster["EngineVersion"],
                "engine_mode": cluster.get("EngineMode", "provisioned"),
                "status": cluster["Status"],
                "vpc_id": cluster.get("DBSubnetGroup", {}).get("VpcId", "N/A"),
                "subnet_group": cluster.get("DBSubnetGroup", {}).get("DBSubnetGroupName", "N/A"),
                "subnets": [
                    subnet["SubnetIdentifier"]
                    for subnet in cluster.get("DBSubnetGroup", {}).get("Subnets", [])
                ],
                "endpoint": cluster.get("Endpoint", "N/A"),
                "reader_endpoint": cluster.get("ReaderEndpoint", "N/A"),
                "port": cluster.get("Port", "N/A"),
                "creation_time": cluster.get("ClusterCreateTime", "N/A"),
                "serverless_v2_scaling": cluster.get("ServerlessV2ScalingConfiguration", {}),
                "capacity": cluster.get("Capacity", "N/A"),
            }
            region_data["clusters"].append(cluster_info)

        return region_data

    except Exception as e:
        print(f"❌ Error auditing RDS in {region_name}: {str(e)}")
        return None


def get_network_interfaces_in_region(region_name, aws_access_key_id, aws_secret_access_key):
    """Get RDS network interfaces in a specific region"""
    try:
        ec2 = boto3.client(
            "ec2",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        # Get network interfaces with RDS description
        response = ec2.describe_network_interfaces(
            Filters=[{"Name": "description", "Values": ["RDSNetworkInterface"]}]
        )

        return response["NetworkInterfaces"]

    except Exception as e:
        print(f"❌ Error getting network interfaces in {region_name}: {str(e)}")
        return []


def main():
    """Main execution function"""
    print("AWS RDS and Network Interface Correlation Audit")
    print("=" * 70)

    try:
        # Load credentials
        aws_access_key_id, aws_secret_access_key = load_aws_credentials()

        # Get all regions
        regions = get_all_regions()
        print(f"🌍 Scanning {len(regions)} AWS regions for RDS instances and network interfaces...")
        print()

        total_instances = 0
        total_clusters = 0
        total_rds_interfaces = 0
        regions_with_rds = []
        rds_network_interfaces = []

        for region in regions:
            print(f"🔍 Checking region: {region}")

            # Check RDS instances and clusters
            rds_data = audit_rds_instances_in_region(
                region, aws_access_key_id, aws_secret_access_key
            )

            # Check RDS network interfaces
            rds_interfaces = get_network_interfaces_in_region(
                region, aws_access_key_id, aws_secret_access_key
            )

            if rds_data or rds_interfaces:
                if rds_data:
                    regions_with_rds.append(rds_data)
                    total_instances += rds_data["total_instances"]
                    total_clusters += rds_data["total_clusters"]
                    print(f"   📊 RDS Instances: {rds_data['total_instances']}")
                    print(f"   📊 RDS Clusters: {rds_data['total_clusters']}")

                if rds_interfaces:
                    total_rds_interfaces += len(rds_interfaces)
                    print(f"   🔗 RDS Network Interfaces: {len(rds_interfaces)}")

                    for interface in rds_interfaces:
                        interface_info = {
                            "region": region,
                            "interface_id": interface["NetworkInterfaceId"],
                            "vpc_id": interface.get("VpcId", "N/A"),
                            "subnet_id": interface.get("SubnetId", "N/A"),
                            "private_ip": interface.get("PrivateIpAddress", "N/A"),
                            "public_ip": interface.get("Association", {}).get("PublicIp", "None"),
                            "status": interface["Status"],
                            "description": interface.get("Description", "No description"),
                        }
                        rds_network_interfaces.append(interface_info)
            else:
                print(f"   ✅ No RDS resources found")
            print()

        # Summary report
        print("=" * 70)
        print("📋 RDS AND NETWORK INTERFACE AUDIT SUMMARY")
        print("=" * 70)
        print(f"🌍 Regions scanned: {len(regions)}")
        print(f"📊 Total RDS instances: {total_instances}")
        print(f"📊 Total RDS clusters: {total_clusters}")
        print(f"🔗 Total RDS network interfaces: {total_rds_interfaces}")
        print()

        # Detailed RDS information
        if regions_with_rds:
            print("🗄️  RDS INSTANCES AND CLUSTERS DETAILS")
            print("=" * 50)

            for region_data in regions_with_rds:
                print(f"\n📍 Region: {region_data['region']}")
                print("-" * 30)

                # RDS Instances
                if region_data["instances"]:
                    print("   📊 RDS Instances:")
                    for instance in region_data["instances"]:
                        print(f"      🗄️  {instance['identifier']}")
                        print(f"         Engine: {instance['engine']} {instance['engine_version']}")
                        print(f"         Class: {instance['instance_class']}")
                        print(f"         Status: {instance['status']}")
                        print(f"         VPC: {instance['vpc_id']}")
                        print(f"         Endpoint: {instance['endpoint']}:{instance['port']}")
                        print(f"         Public: {instance['publicly_accessible']}")
                        print(
                            f"         Storage: {instance['storage_type']} ({instance['allocated_storage']} GB)"
                        )
                        print(f"         Created: {instance['creation_time']}")
                        print()

                # RDS Clusters
                if region_data["clusters"]:
                    print("   🌐 RDS Clusters:")
                    for cluster in region_data["clusters"]:
                        print(f"      🌐 {cluster['identifier']}")
                        print(f"         Engine: {cluster['engine']} {cluster['engine_version']}")
                        print(f"         Mode: {cluster['engine_mode']}")
                        print(f"         Status: {cluster['status']}")
                        print(f"         VPC: {cluster['vpc_id']}")
                        print(f"         Endpoint: {cluster['endpoint']}:{cluster['port']}")
                        if cluster["reader_endpoint"] != "N/A":
                            print(f"         Reader: {cluster['reader_endpoint']}")
                        if cluster["serverless_v2_scaling"]:
                            print(f"         Serverless V2: {cluster['serverless_v2_scaling']}")
                        print(f"         Created: {cluster['creation_time']}")
                        print()

        # RDS Network Interface details
        if rds_network_interfaces:
            print("\n🔗 RDS NETWORK INTERFACES DETAILS")
            print("=" * 50)

            for interface in rds_network_interfaces:
                print(f"\n🔗 Interface: {interface['interface_id']} ({interface['region']})")
                print(f"   VPC: {interface['vpc_id']}")
                print(f"   Subnet: {interface['subnet_id']}")
                print(f"   Private IP: {interface['private_ip']}")
                print(f"   Public IP: {interface['public_ip']}")
                print(f"   Status: {interface['status']}")

        # Analysis and recommendations
        print("\n" + "=" * 70)
        print("💡 CLEANUP ANALYSIS AND RECOMMENDATIONS")
        print("=" * 70)

        if total_rds_interfaces > 0 and (total_instances + total_clusters) == 0:
            print("⚠️  ORPHANED RDS NETWORK INTERFACES DETECTED!")
            print("   • Found RDS network interfaces but no active RDS instances/clusters")
            print("   • These interfaces are likely from deleted RDS instances")
            print("   • Safe to delete for cost savings and hygiene")

        elif total_rds_interfaces > (total_instances + total_clusters):
            print("⚠️  EXCESS RDS NETWORK INTERFACES DETECTED!")
            print(
                f"   • Found {total_rds_interfaces} RDS interfaces but only {total_instances + total_clusters} RDS resources"
            )
            print("   • Some interfaces may be orphaned")

        elif total_instances > 0 and total_clusters > 0:
            print("ℹ️  MIXED RDS DEPLOYMENT DETECTED")
            print("   • Both traditional instances and serverless clusters found")
            print("   • Review if all instances are needed")

        elif total_clusters > 0:
            print("✅ SERVERLESS RDS DEPLOYMENT")
            print("   • Only serverless clusters found - optimal for cost")

        else:
            print("✅ CLEAN RDS CONFIGURATION")
            print("   • RDS network interfaces match RDS resources")

    except Exception as e:
        print(f"❌ Critical error during RDS audit: {str(e)}")
        raise


if __name__ == "__main__":
    main()
