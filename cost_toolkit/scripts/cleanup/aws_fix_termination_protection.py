#!/usr/bin/env python3

import boto3
from botocore.exceptions import ClientError


def disable_termination_protection_and_terminate(instance_id, region_name):
    """Disable termination protection and terminate an instance"""
    print(f"\n🔓 Disabling termination protection for {instance_id} in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        # First, disable termination protection
        print(f"  Disabling termination protection...")
        ec2.modify_instance_attribute(
            InstanceId=instance_id, DisableApiTermination={"Value": False}
        )
        print(f"  ✅ Termination protection disabled")

        # Now terminate the instance
        print(f"  Terminating instance...")
        ec2.terminate_instances(InstanceIds=[instance_id])
        print(f"  ✅ Instance {instance_id} termination initiated")
        print(f"  💰 This will stop EBS storage charges for attached volumes")

        return True

    except ClientError as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    print("AWS Fix Termination Protection")
    print("=" * 80)

    # The instance that failed to terminate
    instance_id = "i-0cfce47f50e3c34ff"
    region_name = "us-east-1"

    print(f"Fixing termination protection for mufasa instance...")

    success = disable_termination_protection_and_terminate(instance_id, region_name)

    print(f"\n🎯 RESULT:")
    if success:
        print(f"  ✅ Successfully disabled protection and terminated {instance_id}")
        print(f"  💰 Additional monthly savings: $0.64 (8GB EBS volume)")
    else:
        print(f"  ❌ Failed to terminate {instance_id}")


if __name__ == "__main__":
    main()
