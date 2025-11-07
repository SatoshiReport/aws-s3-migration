#!/usr/bin/env python3

import json
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError


def get_all_regions():
    """Get list of all AWS regions"""
    ec2 = boto3.client("ec2", region_name="us-east-1")
    try:
        response = ec2.describe_regions()
        return [region["RegionName"] for region in response["Regions"]]
    except ClientError as e:
        print(f"Error getting regions: {e}")
        return ["us-east-1", "us-east-2", "us-west-2", "eu-west-1", "eu-west-2"]


def analyze_ec2_instances_in_region(region_name):
    """Analyze EC2 instances and their compute costs in a specific region"""
    print(f"\n🖥️  Analyzing EC2 Compute in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        # Get all instances (including terminated ones from recent past)
        response = ec2.describe_instances()

        instances_found = []
        total_monthly_cost = 0

        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                instance_id = instance["InstanceId"]
                instance_type = instance["InstanceType"]
                state = instance["State"]["Name"]
                launch_time = instance.get("LaunchTime")

                # Get instance pricing (approximate)
                hourly_cost = get_instance_hourly_cost(instance_type, region_name)
                monthly_cost = hourly_cost * 24 * 30  # Approximate monthly cost

                instance_info = {
                    "instance_id": instance_id,
                    "instance_type": instance_type,
                    "state": state,
                    "launch_time": launch_time,
                    "region": region_name,
                    "hourly_cost": hourly_cost,
                    "monthly_cost": monthly_cost,
                    "platform": instance.get("Platform", "Linux/UNIX"),
                    "vpc_id": instance.get("VpcId"),
                    "subnet_id": instance.get("SubnetId"),
                    "public_ip": instance.get("PublicIpAddress"),
                    "private_ip": instance.get("PrivateIpAddress"),
                    "tags": instance.get("Tags", []),
                }

                print(f"Instance: {instance_id}")
                print(f"  Type: {instance_type}")
                print(f"  State: {state}")
                print(f"  Platform: {instance_info['platform']}")
                print(f"  Launch Time: {launch_time}")
                print(f"  Hourly Cost: ${hourly_cost:.4f}")

                if state == "running":
                    print(f"  Monthly Cost (if running 24/7): ${monthly_cost:.2f}")
                    total_monthly_cost += monthly_cost
                elif state == "stopped":
                    print(f"  Monthly Cost: $0.00 (stopped - only EBS storage charges)")
                else:
                    print(f"  Monthly Cost: $0.00 ({state})")

                # Show network info
                if instance_info["public_ip"]:
                    print(f"  Public IP: {instance_info['public_ip']}")
                if instance_info["private_ip"]:
                    print(f"  Private IP: {instance_info['private_ip']}")

                # Show tags
                if instance_info["tags"]:
                    print(f"  Tags:")
                    for tag in instance_info["tags"]:
                        print(f"    {tag['Key']}: {tag['Value']}")

                print()
                instances_found.append(instance_info)

        if not instances_found:
            print(f"✅ No EC2 instances found in {region_name}")
        else:
            print(f"📊 Region Summary for {region_name}:")
            running_instances = [i for i in instances_found if i["state"] == "running"]
            stopped_instances = [i for i in instances_found if i["state"] == "stopped"]
            terminated_instances = [i for i in instances_found if i["state"] == "terminated"]

            print(f"  Running instances: {len(running_instances)}")
            print(f"  Stopped instances: {len(stopped_instances)}")
            print(f"  Terminated instances: {len(terminated_instances)}")
            print(f"  Total monthly compute cost: ${total_monthly_cost:.2f}")

        return instances_found

    except ClientError as e:
        print(f"❌ Error analyzing EC2 in {region_name}: {e}")
        return []


def get_instance_hourly_cost(instance_type, region_name):
    """Get approximate hourly cost for an instance type"""
    # This is a simplified pricing model - actual costs may vary
    # Based on On-Demand pricing for Linux instances

    pricing_map = {
        # General Purpose
        "t2.nano": 0.0058,
        "t2.micro": 0.0116,
        "t2.small": 0.023,
        "t2.medium": 0.0464,
        "t2.large": 0.0928,
        "t3.nano": 0.0052,
        "t3.micro": 0.0104,
        "t3.small": 0.0208,
        "t3.medium": 0.0416,
        "t3.large": 0.0832,
        "t4g.nano": 0.0042,
        "t4g.micro": 0.0084,
        "t4g.small": 0.0168,
        "t4g.medium": 0.0336,
        "t4g.large": 0.0672,
        # Compute Optimized
        "c5.large": 0.085,
        "c5.xlarge": 0.17,
        "c5.2xlarge": 0.34,
        "c5.4xlarge": 0.68,
        "c6i.large": 0.0765,
        "c6i.xlarge": 0.153,
        "c6i.2xlarge": 0.306,
        "c7g.medium": 0.0363,
        "c7g.large": 0.0725,
        "c7g.xlarge": 0.145,
        "c7gn.medium": 0.0435,  # Network optimized
        "c7gn.large": 0.087,
        "c7gn.xlarge": 0.174,
        # Memory Optimized
        "r5.large": 0.126,
        "r5.xlarge": 0.252,
        "r5.2xlarge": 0.504,
        "r6i.large": 0.1008,
        "r6i.xlarge": 0.2016,
        # Storage Optimized
        "i3.large": 0.156,
        "i3.xlarge": 0.312,
        "i4i.large": 0.1562,
        "i4i.xlarge": 0.3125,
    }

    # Regional pricing adjustments (us-east-1 is baseline)
    regional_multipliers = {
        "us-east-1": 1.0,
        "us-east-2": 1.0,
        "us-west-1": 1.1,
        "us-west-2": 1.0,
        "eu-west-1": 1.1,
        "eu-west-2": 1.1,
        "eu-central-1": 1.1,
        "ap-southeast-1": 1.15,
        "ap-northeast-1": 1.15,
    }

    base_cost = pricing_map.get(instance_type, 0.05)  # Default fallback
    regional_multiplier = regional_multipliers.get(region_name, 1.1)

    return base_cost * regional_multiplier


def analyze_ebs_volumes_in_region(region_name):
    """Analyze EBS volumes and their costs"""
    print(f"\n💾 Analyzing EBS Storage in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        response = ec2.describe_volumes()
        volumes = response.get("Volumes", [])

        if not volumes:
            print(f"✅ No EBS volumes found in {region_name}")
            return []

        total_storage_cost = 0
        volume_details = []

        for volume in volumes:
            volume_id = volume["VolumeId"]
            volume_type = volume["VolumeType"]
            size_gb = volume["Size"]
            state = volume["State"]
            iops = volume.get("Iops", 0)
            throughput = volume.get("Throughput", 0)

            # Calculate monthly storage cost
            monthly_cost = calculate_ebs_monthly_cost(volume_type, size_gb, iops, throughput)
            total_storage_cost += monthly_cost

            # Check if attached to instance
            attachments = volume.get("Attachments", [])
            attached_to = None
            if attachments:
                attached_to = attachments[0].get("InstanceId")

            print(f"Volume: {volume_id}")
            print(f"  Type: {volume_type}")
            print(f"  Size: {size_gb} GB")
            print(f"  State: {state}")
            print(f"  IOPS: {iops}")
            if throughput:
                print(f"  Throughput: {throughput} MB/s")
            print(f"  Attached to: {attached_to or 'None'}")
            print(f"  Monthly cost: ${monthly_cost:.2f}")

            volume_details.append(
                {
                    "volume_id": volume_id,
                    "volume_type": volume_type,
                    "size_gb": size_gb,
                    "state": state,
                    "attached_to": attached_to,
                    "monthly_cost": monthly_cost,
                }
            )
            print()

        print(f"📊 EBS Summary for {region_name}:")
        print(f"  Total volumes: {len(volumes)}")
        print(f"  Total monthly storage cost: ${total_storage_cost:.2f}")

        return volume_details

    except ClientError as e:
        print(f"❌ Error analyzing EBS in {region_name}: {e}")
        return []


def calculate_ebs_monthly_cost(volume_type, size_gb, iops, throughput):
    """Calculate monthly EBS cost based on volume type and specifications"""
    # EBS pricing per GB per month (approximate)
    pricing = {
        "gp2": 0.10,  # General Purpose SSD
        "gp3": 0.08,  # General Purpose SSD (newer)
        "io1": 0.125,  # Provisioned IOPS SSD
        "io2": 0.125,  # Provisioned IOPS SSD (newer)
        "st1": 0.045,  # Throughput Optimized HDD
        "sc1": 0.025,  # Cold HDD
        "standard": 0.05,  # Magnetic
    }

    base_cost = pricing.get(volume_type, 0.10) * size_gb

    # Add IOPS costs for io1/io2
    if volume_type in ["io1", "io2"] and iops > size_gb * 3:
        extra_iops = iops - (size_gb * 3)
        iops_cost = extra_iops * 0.065  # $0.065 per IOPS per month
        base_cost += iops_cost

    # Add throughput costs for gp3
    if volume_type == "gp3" and throughput > 125:
        extra_throughput = throughput - 125
        throughput_cost = extra_throughput * 0.04  # $0.04 per MB/s per month
        base_cost += throughput_cost

    return base_cost


def main():
    print("AWS EC2 Compute Detailed Cost Analysis")
    print("=" * 80)
    print("Analyzing 'Amazon Elastic Compute Cloud - Compute' costs...")

    # Get all regions
    regions = get_all_regions()

    all_instances = []
    all_volumes = []
    total_compute_cost = 0
    total_storage_cost = 0

    # Focus on regions where we typically see activity
    target_regions = ["us-east-1", "us-east-2", "us-west-2", "eu-west-1", "eu-west-2"]

    for region in target_regions:
        instances = analyze_ec2_instances_in_region(region)
        volumes = analyze_ebs_volumes_in_region(region)

        all_instances.extend(instances)
        all_volumes.extend(volumes)

        # Calculate costs for this region
        region_compute_cost = sum(i["monthly_cost"] for i in instances if i["state"] == "running")
        region_storage_cost = sum(v["monthly_cost"] for v in volumes)

        total_compute_cost += region_compute_cost
        total_storage_cost += region_storage_cost

    # Overall summary
    print("\n" + "=" * 80)
    print("🎯 OVERALL EC2 COST BREAKDOWN")
    print("=" * 80)

    # Instance summary
    running_instances = [i for i in all_instances if i["state"] == "running"]
    stopped_instances = [i for i in all_instances if i["state"] == "stopped"]

    print(f"💻 EC2 INSTANCES:")
    print(f"  Running instances: {len(running_instances)}")
    print(f"  Stopped instances: {len(stopped_instances)}")
    print(f"  Monthly compute cost: ${total_compute_cost:.2f}")

    if running_instances:
        print(f"\n  Running instance details:")
        for instance in running_instances:
            print(
                f"    {instance['instance_id']} ({instance['instance_type']}) - ${instance['monthly_cost']:.2f}/month"
            )

    # Storage summary
    print(f"\n💾 EBS STORAGE:")
    print(f"  Total volumes: {len(all_volumes)}")
    print(f"  Monthly storage cost: ${total_storage_cost:.2f}")

    # Total EC2 costs
    total_ec2_cost = total_compute_cost + total_storage_cost
    print(f"\n💰 TOTAL EC2 COSTS:")
    print(f"  Compute (instances): ${total_compute_cost:.2f}/month")
    print(f"  Storage (EBS): ${total_storage_cost:.2f}/month")
    print(f"  Total EC2: ${total_ec2_cost:.2f}/month")

    # Explain what "Amazon Elastic Compute Cloud - Compute" means
    print(f"\n📋 WHAT IS 'AMAZON ELASTIC COMPUTE CLOUD - COMPUTE'?")
    print(f"  This billing line item includes:")
    print(f"    1. EC2 Instance hours (compute time)")
    print(f"    2. EBS storage costs (disk space)")
    print(f"    3. EBS IOPS and throughput charges")
    print(f"    4. Data transfer within EC2")
    print(f"    5. Elastic IP addresses (if any)")
    print(f"    6. Load balancer costs (if any)")

    # Optimization recommendations
    print(f"\n💡 COST OPTIMIZATION OPPORTUNITIES:")

    if stopped_instances:
        print(f"  🔄 Stopped instances still incur EBS storage costs")
        print(f"     Consider terminating unused instances")

    if len(running_instances) > 1:
        print(f"  📊 Multiple running instances detected")
        print(f"     Review if all instances are necessary")

    if total_storage_cost > total_compute_cost:
        print(f"  💾 Storage costs exceed compute costs")
        print(f"     Review EBS volumes for optimization opportunities")

    print(f"\n🔍 NEXT STEPS:")
    print(f"  1. Review each running instance's necessity")
    print(f"  2. Consider rightsizing instance types")
    print(f"  3. Evaluate EBS volume types and sizes")
    print(f"  4. Look into Reserved Instances for long-term workloads")


if __name__ == "__main__":
    main()
