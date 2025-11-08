#!/usr/bin/env python3

import json

import boto3
from botocore.exceptions import ClientError


def audit_rds_databases():  # noqa: C901, PLR0912, PLR0915
    """Audit RDS databases across all regions to understand what's running"""

    # Get all AWS regions
    ec2 = boto3.client("ec2", region_name="us-east-1")
    regions = [region["RegionName"] for region in ec2.describe_regions()["Regions"]]

    print("AWS RDS Database Audit")
    print("=" * 80)

    total_instances = 0
    total_clusters = 0
    total_monthly_cost = 0

    for region in regions:
        try:
            rds = boto3.client("rds", region_name=region)

            # Check RDS instances
            instances = rds.describe_db_instances()
            clusters = rds.describe_db_clusters()

            if not instances["DBInstances"] and not clusters["DBClusters"]:
                continue

            print(f"\nRegion: {region}")
            print("-" * 40)

            # Process RDS Instances
            if instances["DBInstances"]:
                print("RDS INSTANCES:")
                for instance in instances["DBInstances"]:
                    total_instances += 1

                    print(f"  Instance ID: {instance['DBInstanceIdentifier']}")
                    print(
                        f"  Engine: {instance['Engine']} {instance.get('EngineVersion', 'Unknown')}"
                    )
                    print(f"  Instance Class: {instance['DBInstanceClass']}")
                    print(f"  Status: {instance['DBInstanceStatus']}")
                    print(f"  Storage: {instance.get('AllocatedStorage', 'Unknown')} GB")
                    print(f"  Storage Type: {instance.get('StorageType', 'Unknown')}")
                    print(f"  Multi-AZ: {instance.get('MultiAZ', False)}")
                    print(f"  Publicly Accessible: {instance.get('PubliclyAccessible', False)}")
                    print(f"  Creation Time: {instance.get('InstanceCreateTime', 'Unknown')}")

                    # Estimate monthly cost based on instance class
                    instance_class = instance["DBInstanceClass"]
                    if "t3.micro" in instance_class:
                        estimated_cost = 20.0  # Rough estimate for t3.micro
                        total_monthly_cost += estimated_cost
                        print(f"  Estimated Cost: ~${estimated_cost:.2f}/month")

                    # Check if instance is in a cluster
                    if instance.get("DBClusterIdentifier"):
                        print(f"  Part of Cluster: {instance['DBClusterIdentifier']}")

                    print()

            # Process Aurora Clusters
            if clusters["DBClusters"]:
                print("AURORA CLUSTERS:")
                for cluster in clusters["DBClusters"]:
                    total_clusters += 1

                    print(f"  Cluster ID: {cluster['DBClusterIdentifier']}")
                    print(
                        f"  Engine: {cluster['Engine']} {cluster.get('EngineVersion', 'Unknown')}"
                    )
                    print(f"  Status: {cluster['Status']}")
                    print(f"  Database Name: {cluster.get('DatabaseName', 'None')}")
                    print(f"  Master Username: {cluster.get('MasterUsername', 'Unknown')}")
                    print(f"  Multi-AZ: {cluster.get('MultiAZ', False)}")
                    print(f"  Storage Encrypted: {cluster.get('StorageEncrypted', False)}")
                    print(f"  Creation Time: {cluster.get('ClusterCreateTime', 'Unknown')}")

                    # Check cluster members
                    if cluster.get("DBClusterMembers"):
                        print(f"  Cluster Members: {len(cluster['DBClusterMembers'])}")
                        for member in cluster["DBClusterMembers"]:
                            print(
                                f"    - {member['DBInstanceIdentifier']} ({'Writer' if member['IsClusterWriter'] else 'Reader'})"
                            )

                    # Check if it's serverless
                    if cluster.get("EngineMode") == "serverless":
                        print(f"  Engine Mode: Serverless")
                        if cluster.get("ScalingConfigurationInfo"):
                            scaling = cluster["ScalingConfigurationInfo"]
                            print(
                                f"  Scaling: {scaling.get('MinCapacity', 'Unknown')}-{scaling.get('MaxCapacity', 'Unknown')} ACU"
                            )
                    elif cluster.get("ServerlessV2ScalingConfiguration"):
                        print(f"  Engine Mode: Serverless V2")
                        scaling = cluster["ServerlessV2ScalingConfiguration"]
                        print(
                            f"  Scaling: {scaling.get('MinCapacity', 'Unknown')}-{scaling.get('MaxCapacity', 'Unknown')} ACU"
                        )

                    print()

        except ClientError as e:
            if "not available" not in str(e).lower():
                print(f"Error accessing region {region}: {e}")

    print("=" * 80)
    print(f"DATABASE SUMMARY:")
    print(f"Total RDS Instances: {total_instances}")
    print(f"Total Aurora Clusters: {total_clusters}")
    print(f"Estimated Monthly Cost: ${total_monthly_cost:.2f}")

    # Analyze billing data context
    print("\n" + "=" * 80)
    print("BILLING DATA ANALYSIS:")
    print("-" * 40)
    print("Based on your billing data:")
    print("• us-east-1: $1.29 (96% of RDS cost)")
    print("  - db.t3.micro instance: 64 hours")
    print("  - GP3 storage: 1.78 GB")
    print("• eu-west-2: $0.05 (4% of RDS cost)")
    print("  - Aurora Serverless V2: 0.36 ACU-Hr")
    print("  - Aurora storage: 0.01 GB")
    print("  - Aurora I/O: 11,735 operations")

    print("\nCOST OPTIMIZATION OPPORTUNITIES:")
    print("-" * 40)
    print("1. Aurora Serverless V2 (eu-west-2): Very low usage (0.36 ACU-Hr)")
    print("   - Consider if this database is still needed")
    print("   - Minimal storage (0.01 GB) suggests it's mostly empty")
    print("2. RDS Instance (us-east-1): t3.micro running 64/720 hours (~9%)")
    print("   - Consider stopping when not in use")
    print("   - Or migrate to Aurora Serverless for auto-scaling")


if __name__ == "__main__":
    audit_rds_databases()
