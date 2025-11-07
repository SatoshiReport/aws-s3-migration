#!/usr/bin/env python3
"""
AWS Fix Termination Protection and Terminate Script
Disables termination protection on protected instances and then terminates them.
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


def disable_termination_protection(
    region_name, instance_id, aws_access_key_id, aws_secret_access_key
):
    """Disable termination protection on an EC2 instance"""
    try:
        ec2 = boto3.client(
            "ec2",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        print(f"🔓 Disabling termination protection: {instance_id}")
        ec2.modify_instance_attribute(
            InstanceId=instance_id, DisableApiTermination={"Value": False}
        )

        print(f"   ✅ Termination protection disabled for {instance_id}")
        return True

    except Exception as e:
        print(f"   ❌ Failed to disable termination protection for {instance_id}: {str(e)}")
        return False


def terminate_instance(region_name, instance_id, aws_access_key_id, aws_secret_access_key):
    """Terminate an EC2 instance"""
    try:
        ec2 = boto3.client(
            "ec2",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        print(f"🗑️  Terminating instance: {instance_id}")
        response = ec2.terminate_instances(InstanceIds=[instance_id])

        current_state = response["TerminatingInstances"][0]["CurrentState"]["Name"]
        previous_state = response["TerminatingInstances"][0]["PreviousState"]["Name"]

        print(f"   State change: {previous_state} → {current_state}")
        return True

    except Exception as e:
        print(f"   ❌ Failed to terminate {instance_id}: {str(e)}")
        return False


def main():
    """Main execution function"""
    print("AWS Fix Termination Protection and Terminate")
    print("=" * 60)
    print("Disabling termination protection and terminating protected instances...")
    print()

    try:
        # Load credentials
        aws_access_key_id, aws_secret_access_key = load_aws_credentials()

        # Target instance with termination protection
        protected_instance = {
            "region": "eu-west-2",
            "instance_id": "i-0635f4a0de21cbc37",
            "name": "Tars",
            "type": "r7i.2xlarge",
        }

        print(f"🎯 Target: {protected_instance['name']} ({protected_instance['instance_id']})")
        print(f"   Region: {protected_instance['region']}")
        print(f"   Type: {protected_instance['type']}")
        print()

        print("⚠️  TERMINATION PROTECTION REMOVAL:")
        print("   • This will disable termination protection")
        print("   • Then permanently terminate the instance")
        print("   • This action cannot be undone")
        print("   • Significant cost savings from r7i.2xlarge termination")
        print()

        confirmation = input("Type 'DISABLE PROTECTION AND TERMINATE' to proceed: ")

        if confirmation != "DISABLE PROTECTION AND TERMINATE":
            print("❌ Operation cancelled - confirmation text did not match")
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
        print("\n" + "=" * 60)
        print("🎯 TERMINATION PROTECTION FIX SUMMARY")
        print("=" * 60)

        if protection_disabled and termination_success:
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
        else:
            print("❌ Operation partially failed:")
            print(f"   Protection disabled: {'✅' if protection_disabled else '❌'}")
            print(f"   Instance terminated: {'✅' if termination_success else '❌'}")

    except Exception as e:
        print(f"❌ Critical error during termination protection fix: {str(e)}")
        raise


if __name__ == "__main__":
    main()
