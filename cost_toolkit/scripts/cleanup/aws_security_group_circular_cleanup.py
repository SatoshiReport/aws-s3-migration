#!/usr/bin/env python3
"""
AWS Security Group Circular Dependencies Cleanup Script
Resolves circular dependencies between security groups and deletes them.
The audit revealed that security groups are referencing each other in rules,
preventing deletion. This script removes the cross-references first, then deletes the groups.
"""

import os

import boto3
from dotenv import load_dotenv


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def remove_security_group_rule(ec2_client, group_id, rule_type, rule_data):
    """Remove a specific security group rule"""
    try:
        if rule_type == "inbound":
            ec2_client.revoke_security_group_ingress(GroupId=group_id, IpPermissions=[rule_data])
        else:  # outbound
            ec2_client.revoke_security_group_egress(GroupId=group_id, IpPermissions=[rule_data])
        return True
    except Exception as e:
        print(f"   ❌ Error removing rule: {e}")
        return False


def get_security_group_rules_referencing_group(ec2_client, target_group_id):
    """Get all rules that reference a specific security group"""
    rules_to_remove = []

    try:
        response = ec2_client.describe_security_groups()
        for sg in response.get("SecurityGroups", []):
            sg_id = sg["GroupId"]

            # Check inbound rules
            for rule in sg.get("IpPermissions", []):
                for group_pair in rule.get("UserIdGroupPairs", []):
                    if group_pair.get("GroupId") == target_group_id:
                        rules_to_remove.append(
                            {
                                "source_sg_id": sg_id,
                                "source_sg_name": sg["GroupName"],
                                "rule_type": "inbound",
                                "rule_data": rule,
                                "target_group_id": target_group_id,
                            }
                        )

            # Check outbound rules
            for rule in sg.get("IpPermissionsEgress", []):
                for group_pair in rule.get("UserIdGroupPairs", []):
                    if group_pair.get("GroupId") == target_group_id:
                        rules_to_remove.append(
                            {
                                "source_sg_id": sg_id,
                                "source_sg_name": sg["GroupName"],
                                "rule_type": "outbound",
                                "rule_data": rule,
                                "target_group_id": target_group_id,
                            }
                        )

        return rules_to_remove
    except Exception as e:
        print(f"❌ Error getting security group rules: {e}")
        return []


def delete_security_group(ec2_client, group_id, group_name):
    """Delete a security group"""
    try:
        print(f"   🗑️  Deleting security group: {group_id} ({group_name})")
        ec2_client.delete_security_group(GroupId=group_id)
        print(f"   ✅ Successfully deleted {group_id}")
        return True
    except Exception as e:
        print(f"   ❌ Error deleting {group_id}: {e}")
        return False


def cleanup_circular_security_groups():
    """Clean up security groups with circular dependencies"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    # Security groups with circular dependencies identified in the audit
    circular_security_groups = [
        # us-east-1 region - NFS groups (circular)
        {
            "group_id": "sg-0423403672ae41d94",
            "name": "security-group-for-outbound-nfs-d-jbqwgqwiy4df",
            "region": "us-east-1",
        },
        {
            "group_id": "sg-0dfa7bedc21d91798",
            "name": "security-group-for-inbound-nfs-d-jbqwgqwiy4df",
            "region": "us-east-1",
        },
        {
            "group_id": "sg-049977ce080d9ab0f",
            "name": "security-group-for-inbound-nfs-d-ujcvqjdoyu70",
            "region": "us-east-1",
        },
        {
            "group_id": "sg-05ec40d14e0fb6fed",
            "name": "security-group-for-outbound-nfs-d-ujcvqjdoyu70",
            "region": "us-east-1",
        },
        # us-east-1 region - RDS groups (circular)
        {"group_id": "sg-0bf8a0d06a121f4a0", "name": "rds-ec2-1", "region": "us-east-1"},
        {"group_id": "sg-044777fbbcdee8f28", "name": "ec2-rds-1", "region": "us-east-1"},
        # us-east-2 region - NFS groups (circular)
        {
            "group_id": "sg-09e291dc61da97af1",
            "name": "security-group-for-outbound-nfs-d-ki8zr9k0yt95",
            "region": "us-east-2",
        },
        {
            "group_id": "sg-0dba11de0f5b92f40",
            "name": "security-group-for-inbound-nfs-d-ki8zr9k0yt95",
            "region": "us-east-2",
        },
    ]

    print("AWS Security Group Circular Dependencies Cleanup")
    print("=" * 60)
    print("Resolving circular dependencies and cleaning up security groups...")
    print()
    print(f"🎯 Target: {len(circular_security_groups)} security groups with circular dependencies")
    print()

    print("⚠️  PROCESS:")
    print("   1. Remove all cross-references between security groups")
    print("   2. Delete the now-unreferenced security groups")
    print("   3. Improve security hygiene and reduce clutter")
    print()

    confirmation = input("Type 'RESOLVE CIRCULAR DEPENDENCIES' to proceed: ")

    if confirmation != "RESOLVE CIRCULAR DEPENDENCIES":
        print("❌ Operation cancelled by user")
        return

    print()
    print("🚨 Proceeding with circular dependency resolution...")
    print("=" * 60)

    # Group by region for efficiency
    regions = {}
    for sg in circular_security_groups:
        region = sg["region"]
        if region not in regions:
            regions[region] = []
        regions[region].append(sg)

    total_rules_removed = 0
    total_groups_deleted = 0

    for region, sgs in regions.items():
        print(f"🔍 Processing region: {region}")
        print()

        # Create EC2 client for the specific region
        ec2_client = boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        # Step 1: Remove all cross-references
        print("🔗 Step 1: Removing cross-references...")
        for sg in sgs:
            group_id = sg["group_id"]
            group_name = sg["name"]

            print(f"   🔍 Checking references to {group_id} ({group_name})")

            rules_to_remove = get_security_group_rules_referencing_group(ec2_client, group_id)

            for rule_info in rules_to_remove:
                source_sg_id = rule_info["source_sg_id"]
                source_sg_name = rule_info["source_sg_name"]
                rule_type = rule_info["rule_type"]
                rule_data = rule_info["rule_data"]

                print(f"     🔧 Removing {rule_type} rule from {source_sg_id} ({source_sg_name})")

                if remove_security_group_rule(ec2_client, source_sg_id, rule_type, rule_data):
                    total_rules_removed += 1
                    print(f"     ✅ Removed rule successfully")
                else:
                    print(f"     ❌ Failed to remove rule")

        print()

        # Step 2: Delete the security groups
        print("🗑️  Step 2: Deleting security groups...")
        for sg in sgs:
            group_id = sg["group_id"]
            group_name = sg["name"]

            if delete_security_group(ec2_client, group_id, group_name):
                total_groups_deleted += 1

        print()

    print("=" * 60)
    print("🎯 CIRCULAR DEPENDENCY CLEANUP SUMMARY")
    print("=" * 60)
    print(f"🔗 Security group rules removed: {total_rules_removed}")
    print(f"🗑️  Security groups deleted: {total_groups_deleted}")
    print(f"📊 Success rate: {total_groups_deleted}/{len(circular_security_groups)} groups")
    print()

    if total_groups_deleted > 0:
        print("🎉 Circular dependency cleanup completed!")
        print("   Your AWS account now has cleaner security group configuration.")
        print()
        print("📝 Benefits achieved:")
        print("   • Resolved circular security group dependencies")
        print("   • Removed unused NFS and RDS security groups")
        print("   • Improved security posture and compliance")
        print("   • Cleaner AWS console experience")
    else:
        print("❌ No security groups were successfully deleted")
        print("   Some dependencies may still exist or require manual intervention")


if __name__ == "__main__":
    try:
        cleanup_circular_security_groups()
    except Exception as e:
        print(f"❌ Script failed: {e}")
        exit(1)
