#!/usr/bin/env python3
"""
AWS Security Group Circular Dependencies Cleanup Script
Resolves circular dependencies between security groups and deletes them.
The audit revealed that security groups are referencing each other in rules,
preventing deletion. This script removes the cross-references first, then deletes the groups.
"""

import sys

from botocore.exceptions import ClientError

from cost_toolkit.common.aws_client_factory import create_client
from cost_toolkit.common.credential_utils import setup_aws_credentials
from cost_toolkit.common.security_group_constants import ALL_CIRCULAR_SECURITY_GROUPS
from cost_toolkit.scripts.aws_ec2_operations import delete_security_group as delete_security_group_canonical


def remove_security_group_rule(ec2_client, group_id, rule_type, rule_data):
    """Remove a specific security group rule"""
    try:
        if rule_type == "inbound":
            ec2_client.revoke_security_group_ingress(GroupId=group_id, IpPermissions=[rule_data])
        else:  # outbound
            ec2_client.revoke_security_group_egress(GroupId=group_id, IpPermissions=[rule_data])
    except ClientError as e:
        print(f"   ❌ Error removing rule: {e}")
        return False

    return True


def _check_inbound_rules(sg, target_group_id):
    """Check inbound rules for references to target group."""
    rules = []
    for rule in sg.get("IpPermissions", []):
        for group_pair in rule.get("UserIdGroupPairs", []):
            if group_pair.get("GroupId") == target_group_id:
                rules.append(
                    {
                        "source_sg_id": sg["GroupId"],
                        "source_sg_name": sg["GroupName"],
                        "rule_type": "inbound",
                        "rule_data": rule,
                        "target_group_id": target_group_id,
                    }
                )
    return rules


def _check_outbound_rules(sg, target_group_id):
    """Check outbound rules for references to target group."""
    rules = []
    for rule in sg.get("IpPermissionsEgress", []):
        for group_pair in rule.get("UserIdGroupPairs", []):
            if group_pair.get("GroupId") == target_group_id:
                rules.append(
                    {
                        "source_sg_id": sg["GroupId"],
                        "source_sg_name": sg["GroupName"],
                        "rule_type": "outbound",
                        "rule_data": rule,
                        "target_group_id": target_group_id,
                    }
                )
    return rules


def get_security_group_rules_referencing_group(ec2_client, target_group_id):
    """Get all rules that reference a specific security group"""
    rules_to_remove = []

    try:
        response = ec2_client.describe_security_groups()
        for sg in response.get("SecurityGroups", []):
            rules_to_remove.extend(_check_inbound_rules(sg, target_group_id))
            rules_to_remove.extend(_check_outbound_rules(sg, target_group_id))

    except ClientError as e:
        print(f"❌ Error getting security group rules: {e}")
        return []

    return rules_to_remove


def delete_security_group(ec2_client, group_id, group_name):
    """
    Delete a security group.
    """
    return delete_security_group_canonical(
        region=ec2_client.meta.region_name,
        group_id=group_id,
        group_name=group_name,
        ec2_client=ec2_client,
    )


def _get_circular_security_groups():
    """Return list of security groups with circular dependencies from shared constants."""
    return ALL_CIRCULAR_SECURITY_GROUPS


def _remove_cross_references(ec2_client, sgs):
    """Remove cross-references between security groups."""
    total_rules_removed = 0
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
                print("     ✅ Removed rule successfully")
            else:
                print("     ❌ Failed to remove rule")

    return total_rules_removed


def _delete_security_groups(ec2_client, sgs):
    """Delete security groups."""
    total_groups_deleted = 0
    print("🗑️  Step 2: Deleting security groups...")
    for sg in sgs:
        group_id = sg["group_id"]
        group_name = sg["name"]
        if delete_security_group(ec2_client, group_id, group_name):
            total_groups_deleted += 1
    return total_groups_deleted


def _process_regions(regions, aws_access_key_id, aws_secret_access_key):
    """Process security groups by region."""
    total_rules_removed = 0
    total_groups_deleted = 0

    for region, sgs in regions.items():
        print(f"🔍 Processing region: {region}")
        print()

        ec2_client = create_client(
            "ec2",
            region=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        total_rules_removed += _remove_cross_references(ec2_client, sgs)
        print()
        total_groups_deleted += _delete_security_groups(ec2_client, sgs)
        print()

    return total_rules_removed, total_groups_deleted


def _print_final_summary(total_rules_removed, total_groups_deleted, total_groups):
    """Print final cleanup summary."""
    print("=" * 60)
    print("🎯 CIRCULAR DEPENDENCY CLEANUP SUMMARY")
    print("=" * 60)
    print(f"🔗 Security group rules removed: {total_rules_removed}")
    print(f"🗑️  Security groups deleted: {total_groups_deleted}")
    print(f"📊 Success rate: {total_groups_deleted}/{total_groups} groups")
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


def cleanup_circular_security_groups():
    """Clean up security groups with circular dependencies"""
    aws_access_key_id, aws_secret_access_key = setup_aws_credentials()
    circular_security_groups = _get_circular_security_groups()

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

    regions = {}
    for sg in circular_security_groups:
        region = sg["region"]
        if region not in regions:
            regions[region] = []
        regions[region].append(sg)

    total_rules_removed, total_groups_deleted = _process_regions(
        regions, aws_access_key_id, aws_secret_access_key
    )

    _print_final_summary(total_rules_removed, total_groups_deleted, len(circular_security_groups))


def main():
    """Main function."""
    try:
        cleanup_circular_security_groups()
    except ClientError as e:
        print(f"❌ Script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
