#!/usr/bin/env python3

import base64
import os

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def check_instance_status():  # noqa: C901, PLR0912, PLR0915
    """Check EC2 instance status and User Data execution"""
    setup_aws_credentials()

    print("AWS Instance Status Check")
    print("=" * 80)

    ec2 = boto3.client("ec2", region_name="eu-west-2")
    instance_id = "i-05ad29f28fc8a8fdc"

    try:
        # Get instance details
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]

        print(f"🖥️  INSTANCE STATUS:")
        print(f"  Instance ID: {instance_id}")
        print(f"  State: {instance['State']['Name']}")
        print(f"  Launch Time: {instance.get('LaunchTime', 'N/A')}")
        print(f"  Instance Type: {instance['InstanceType']}")
        print()

        # Get User Data
        try:
            user_data_response = ec2.describe_instance_attribute(
                InstanceId=instance_id, Attribute="userData"
            )

            if "UserData" in user_data_response and "Value" in user_data_response["UserData"]:
                user_data_b64 = user_data_response["UserData"]["Value"]
                user_data = base64.b64decode(user_data_b64).decode("utf-8")

                print("📝 USER DATA STATUS:")
                print("✅ User Data is configured")
                print(f"  Script size: {len(user_data)} characters")

                # Check if it contains our migration script
                if "EBS to S3 Migration Script" in user_data:
                    print("✅ Migration script detected in User Data")
                else:
                    print("⚠️ Migration script not found in User Data")

            else:
                print("❌ No User Data configured")

        except Exception as e:
            print(f"⚠️ Could not retrieve User Data: {str(e)}")

        print()

        # Check system logs (if available)
        try:
            print("📋 CHECKING SYSTEM LOGS:")
            print("=" * 40)

            # Get console output
            console_response = ec2.get_console_output(InstanceId=instance_id)

            if "Output" in console_response:
                console_output = console_response["Output"]

                # Look for migration-related log entries
                lines = console_output.split("\n")
                migration_lines = []

                for line in lines:
                    if any(
                        keyword in line.lower()
                        for keyword in ["migration", "mount", "s3", "sync", "aws"]
                    ):
                        migration_lines.append(line.strip())

                if migration_lines:
                    print("🔍 Migration-related console output:")
                    for line in migration_lines[-10:]:  # Last 10 relevant lines
                        if line:
                            print(f"  {line}")
                else:
                    print("📝 No migration-specific output found in console logs")
                    print("📄 Last few console lines:")
                    for line in lines[-5:]:
                        if line.strip():
                            print(f"  {line.strip()}")
            else:
                print("📭 No console output available yet")

        except Exception as e:
            print(f"⚠️ Could not retrieve console output: {str(e)}")

        print()
        print("💡 TROUBLESHOOTING:")
        print("=" * 40)
        print("If migration hasn't started after 10+ minutes:")
        print("1. User Data may have failed to execute")
        print("2. Instance may need manual intervention")
        print("3. Check console output for errors")
        print("4. Consider alternative approach (SSM with proper permissions)")

    except Exception as e:
        print(f"❌ Error checking instance status: {str(e)}")


if __name__ == "__main__":
    check_instance_status()
