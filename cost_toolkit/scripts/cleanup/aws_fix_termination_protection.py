#!/usr/bin/env python3
"""Fix EC2 instance termination protection settings."""

from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_client_factory import create_client


def disable_termination_protection_and_terminate(instance_id, region_name):
    """Disable termination protection and terminate an instance"""
    print(f"\n🔓 Disabling termination protection for {instance_id} in {region_name}")
    print("=" * 80)

    try:
        ec2 = create_client("ec2", region=region_name)

        # First, disable termination protection
        print("  Disabling termination protection...")
        ec2.modify_instance_attribute(
            InstanceId=instance_id, DisableApiTermination={"Value": False}
        )
        print("  ✅ Termination protection disabled")

        # Now terminate the instance
        print("  Terminating instance...")
        ec2.terminate_instances(InstanceIds=[instance_id])
        print(f"  ✅ Instance {instance_id} termination initiated")
        print("  💰 This will stop EBS storage charges for attached volumes")

    except ClientError as e:
        print(f"  ❌ Error: {e}")
        return False

    return True


def main():
    """Disable termination protection and remove EC2 instance."""
    print("AWS Fix Termination Protection")
    print("=" * 80)

    # The instance that failed to terminate
    instance_id = "i-0cfce47f50e3c34f"
    region_name = "us-east-1"

    print("Fixing termination protection for mufasa instance...")

    success = disable_termination_protection_and_terminate(instance_id, region_name)

    print("\n🎯 RESULT:")
    if success:
        print(f"  ✅ Successfully disabled protection and terminated {instance_id}")
        print("  💰 Additional monthly savings: $0.64 (8GB EBS volume)")
    else:
        print(f"  ❌ Failed to terminate {instance_id}")


if __name__ == "__main__":
    main()
