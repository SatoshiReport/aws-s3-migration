"""
AWS Cost Optimization Opportunity Analysis
Scans for unattached EBS volumes, unused Elastic IPs, and old snapshots.
"""

from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

from cost_toolkit.common.aws_common import get_default_regions
from cost_toolkit.common.cost_utils import calculate_ebs_volume_cost, calculate_snapshot_cost


def _scan_region_for_unattached_volumes(region):
    """Scan a single region for unattached EBS volumes."""
    try:
        ec2 = boto3.client("ec2", region_name=region)
        volumes = ec2.describe_volumes()["Volumes"]

        count = 0
        total_cost = 0.0

        for volume in volumes:
            if not volume.get("Attachments"):
                count += 1
                size_gb = volume["Size"]
                volume_type = volume["VolumeType"]
                total_cost += calculate_ebs_volume_cost(size_gb, volume_type)
    except ClientError as exc:
        print(f"⚠️  Failed to inspect EBS volumes in {region}: {exc}")
        return 0, 0.0
    return count, total_cost


def _check_unattached_ebs_volumes():
    """Check for unattached EBS volumes across regions."""
    try:
        regions = get_default_regions()
        unattached_volumes = 0
        unattached_cost = 0.0

        for region in regions:
            count, cost = _scan_region_for_unattached_volumes(region)
            unattached_volumes += count
            unattached_cost += cost

        if unattached_volumes > 0:
            return {
                "category": "EBS Optimization",
                "description": f"{unattached_volumes} unattached EBS volumes",
                "potential_savings": unattached_cost,
                "risk": "Low",
                "action": "Delete unused volumes after verification",
            }
    except ClientError:
        pass
    return None


def _check_unused_elastic_ips():
    """Check for unused Elastic IPs across regions."""
    try:
        elastic_ips = 0
        for region in [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
        ]:
            try:
                ec2 = boto3.client("ec2", region_name=region)
                addresses = ec2.describe_addresses()["Addresses"]

                for address in addresses:
                    if not address.get("InstanceId"):
                        elastic_ips += 1
            except ClientError as exc:
                print(f"⚠️  Failed to inspect Elastic IPs in {region}: {exc}")

        if elastic_ips > 0:
            return {
                "category": "VPC Optimization",
                "description": f"{elastic_ips} unattached Elastic IPs",
                "potential_savings": elastic_ips * 3.60,
                "risk": "Low",
                "action": "Release unused Elastic IPs",
            }
    except ClientError:
        pass
    return None


def _check_old_snapshots():
    """Check for old snapshots across regions."""
    try:
        old_snapshots = 0
        snapshot_cost = 0.0
        cutoff_date = datetime.now() - timedelta(days=90)

        for region in get_default_regions():
            try:
                ec2 = boto3.client("ec2", region_name=region)
                snapshots = ec2.describe_snapshots(OwnerIds=["self"])["Snapshots"]

                for snapshot in snapshots:
                    if snapshot["StartTime"].replace(tzinfo=None) < cutoff_date:
                        old_snapshots += 1
                        size_gb = snapshot.get("VolumeSize", 0)
                        snapshot_cost += calculate_snapshot_cost(size_gb)
            except ClientError as exc:
                print(f"⚠️  Failed to inspect snapshots in {region}: {exc}")

        if old_snapshots > 0:
            return {
                "category": "Snapshot Optimization",
                "description": f"{old_snapshots} snapshots older than 90 days",
                "potential_savings": snapshot_cost,
                "risk": "Medium",
                "action": "Review and delete unnecessary old snapshots",
            }
    except ClientError:
        pass
    return None


def analyze_optimization_opportunities():
    """Analyze potential cost optimization opportunities"""
    opportunities = []

    checkers = [
        _check_unattached_ebs_volumes,
        _check_unused_elastic_ips,
        _check_old_snapshots,
    ]

    for checker in checkers:
        opportunity = checker()
        if opportunity:
            opportunities.append(opportunity)

    return opportunities
