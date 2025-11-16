#!/usr/bin/env python3
"""
AWS Fix Termination Protection and Terminate Script
Disables termination protection on protected instances and then terminates them.
"""

from botocore.exceptions import ClientError

from cost_toolkit.common.credential_utils import setup_aws_credentials
from cost_toolkit.scripts.aws_ec2_operations import (
    disable_termination_protection,
    terminate_instance,
)


def display_instance_info(protected_instance):
    """Display target instance information"""
    print(f"🎯 Target: {protected_instance['name']} ({protected_instance['instance_id']})")
    print(f"   Region: {protected_instance['region']}")
    print(f"   Type: {protected_instance['type']}")
    print()


def display_warning_and_confirm():
    """Display termination warning and get user confirmation"""
    print("⚠️  TERMINATION PROTECTION REMOVAL:")
    print("   • This will disable termination protection")
    print("   • Then permanently terminate the instance")
    print("   • This action cannot be undone")
    print("   • Significant cost savings from r7i.2xlarge termination")
    print()

    confirmation = input("Type 'DISABLE PROTECTION AND TERMINATE' to proceed: ")

    if confirmation != "DISABLE PROTECTION AND TERMINATE":
        print("❌ Operation cancelled - confirmation text did not match")
        return False
    return True


def print_success_summary(instance_id):
    """Print success summary and next steps"""
    print("✅ Successfully completed all operations:")
    print(f"   🔓 Disabled termination protection: {instance_id}")
    print(f"   🗑️  Terminated instance: {instance_id}")
    print()
    print("🎉 Protected instance termination completed!")
    print("   • Termination protection has been disabled")
    print("   • Instance is now terminating")
    print("   • Network interface will be automatically detached")
    print("   • Significant cost savings achieved")
    print()
    print("💡 Next steps:")
    print("   • Wait for termination to complete (5-10 minutes)")
    print("   • Run VPC cleanup to remove empty VPCs if desired")
    print("   • Verify no orphaned resources remain")


def print_operation_summary(protection_disabled, termination_success, instance_id):
    """Print operation summary based on results"""
    print("\n" + "=" * 60)
    print("🎯 TERMINATION PROTECTION FIX SUMMARY")
    print("=" * 60)

    if protection_disabled and termination_success:
        print_success_summary(instance_id)
    else:
        print("❌ Operation partially failed:")
        print(f"   Protection disabled: {'✅' if protection_disabled else '❌'}")
        print(f"   Instance terminated: {'✅' if termination_success else '❌'}")


def main():
    """Main execution function"""
    print("AWS Fix Termination Protection and Terminate")
    print("=" * 60)
    print("Disabling termination protection and terminating protected instances...")
    print()

    try:
        # Load credentials
        aws_access_key_id, aws_secret_access_key = setup_aws_credentials()

        # Target instance with termination protection
        protected_instance = {
            "region": "eu-west-2",
            "instance_id": "i-0635f4a0de21cbc37",
            "name": "Tars",
            "type": "r7i.2xlarge",
        }

        display_instance_info(protected_instance)

        if not display_warning_and_confirm():
            return

        print("\n🚨 Proceeding with termination protection removal and termination...")
        print("=" * 60)

        region = protected_instance["region"]
        instance_id = protected_instance["instance_id"]

        # Step 1: Disable termination protection
        protection_disabled = disable_termination_protection(
            region, instance_id, aws_access_key_id, aws_secret_access_key
        )

        if not protection_disabled:
            print("❌ Failed to disable termination protection - cannot proceed with termination")
            return

        print()

        # Step 2: Terminate the instance
        termination_success = terminate_instance(
            region, instance_id, aws_access_key_id, aws_secret_access_key
        )

        # Summary
        print_operation_summary(protection_disabled, termination_success, instance_id)

    except ClientError as e:
        print(f"❌ Critical error during termination protection fix: {str(e)}")
        raise


if __name__ == "__main__":
    main()
