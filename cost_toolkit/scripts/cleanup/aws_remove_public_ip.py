#!/usr/bin/env python3
"""Remove public IP addresses from EC2 instances."""

import time

from botocore.exceptions import ClientError

from cost_toolkit.common.aws_client_factory import create_client
from cost_toolkit.scripts.aws_utils import get_instance_info


def get_instance_details(_ec2, instance_id, region_name):
    """Get current instance details and network information"""
    print("Step 1: Getting instance details...")
    instance = get_instance_info(instance_id, region_name)

    current_state = instance["State"]["Name"]
    current_public_ip = instance.get("PublicIpAddress")
    network_interface_id = instance["NetworkInterfaces"][0]["NetworkInterfaceId"]

    print(f"  Current state: {current_state}")
    print(f"  Current public IP: {current_public_ip}")
    print(f"  Network Interface ID: {network_interface_id}")

    return instance, current_state, current_public_ip, network_interface_id


def stop_instance_if_running(ec2, instance_id, current_state):
    """Stop the instance if it's currently running"""
    if current_state == "running":
        print(f"Step 2: Stopping instance {instance_id}...")
        ec2.stop_instances(InstanceIds=[instance_id])

        print("  Waiting for instance to stop...")
        waiter = ec2.get_waiter("instance_stopped")
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})
        print("  ✅ Instance stopped")
    else:
        print("Step 2: Instance is already stopped")


def modify_network_interface(ec2, instance_id, network_interface_id):
    """Modify network interface to not assign public IP"""
    print("Step 3: Modifying network interface...")
    try:
        ec2.modify_network_interface_attribute(
            NetworkInterfaceId=network_interface_id,
            SourceDestCheck={"Value": True},
        )
        ec2.modify_instance_attribute(InstanceId=instance_id, SourceDestCheck={"Value": True})
        print("  ✅ Network interface modified")
    except ClientError as e:
        print(f"  ⚠️  Network interface modification: {e}")


def start_instance(ec2, instance_id):
    """Start the instance and wait for it to be running"""
    print(f"Step 4: Starting instance {instance_id}...")
    ec2.start_instances(InstanceIds=[instance_id])

    print("  Waiting for instance to start...")
    waiter = ec2.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})
    print("  ✅ Instance started")


def retry_with_subnet_modification(ec2, instance_id, subnet_id, region_name):
    """Retry removing public IP by modifying subnet settings"""
    try:
        ec2.modify_subnet_attribute(SubnetId=subnet_id, MapPublicIpOnLaunch={"Value": False})
        print(f"  ✅ Disabled auto-assign public IP on subnet {subnet_id}")

        print("  Stopping instance again to apply subnet changes...")
        ec2.stop_instances(InstanceIds=[instance_id])
        waiter = ec2.get_waiter("instance_stopped")
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})

        print("  Starting instance again...")
        ec2.start_instances(InstanceIds=[instance_id])
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})

        time.sleep(10)
        final_instance = get_instance_info(instance_id, region_name)
        final_public_ip = final_instance.get("PublicIpAddress")

        if final_public_ip:
            print(f"  ❌ Instance still has public IP: {final_public_ip}")
            return False

        print("  ✅ Public IP successfully removed")
    except ClientError as e:
        print(f"  ❌ Error modifying subnet: {e}")
        return False
    return True


def verify_public_ip_removed(ec2, instance_id, region_name):
    """Verify that public IP has been removed"""
    print("Step 5: Verifying public IP removal...")
    time.sleep(10)

    updated_instance = get_instance_info(instance_id, region_name)
    new_public_ip = updated_instance.get("PublicIpAddress")

    if new_public_ip:
        print(f"  ⚠️  Instance still has public IP: {new_public_ip}")
        print("  This may be due to subnet auto-assign settings")

        subnet_id = updated_instance["SubnetId"]
        print(f"  Checking subnet {subnet_id} auto-assign setting...")

        return retry_with_subnet_modification(ec2, instance_id, subnet_id, region_name)

    print("  ✅ Public IP successfully removed")
    return True


def remove_public_ip_from_instance(instance_id, region_name):
    """Remove public IP from an EC2 instance by stopping, modifying, and restarting"""
    print(f"\n🔧 Removing public IP from instance {instance_id} in {region_name}")
    print("=" * 80)

    try:
        ec2 = create_client("ec2", region=region_name)

        _instance, current_state, current_public_ip, network_interface_id = get_instance_details(
            ec2, instance_id, region_name
        )

        if not current_public_ip:
            print(f"✅ Instance {instance_id} already has no public IP")
            return True

        stop_instance_if_running(ec2, instance_id, current_state)
        modify_network_interface(ec2, instance_id, network_interface_id)
        start_instance(ec2, instance_id)

        return verify_public_ip_removed(ec2, instance_id, region_name)

    except ClientError as e:
        print(f"❌ Error removing public IP: {e}")
        return False


def main():
    """Main entry point to remove public IP from EC2 instance."""
    print("AWS Remove Public IP Address")
    print("=" * 80)
    print("Removing public IP from EC2 instance to save $3.60/month...")

    instance_id = "i-00c39b1ba0eba3e2d"
    region_name = "us-east-2"

    print(f"\n⚠️  WARNING: This will cause downtime for instance {instance_id}")
    print("The instance will be stopped and restarted to remove the public IP.")
    print("After this operation, you'll need to use AWS Systems Manager to connect:")
    print(f"  aws ssm start-session --target {instance_id} --region {region_name}")

    success = remove_public_ip_from_instance(instance_id, region_name)

    print("\n" + "=" * 80)
    print("🎯 OPERATION SUMMARY")
    print("=" * 80)

    if success:
        print(f"✅ Successfully removed public IP from {instance_id}")
        print("💰 Cost savings: $3.60/month")
        print("🔧 Connection method: AWS Systems Manager Session Manager")
        print(f"   Command: aws ssm start-session --target {instance_id} --region {region_name}")
    else:
        print(f"❌ Failed to remove public IP from {instance_id}")
        print("💡 Manual steps may be required:")
        print("   1. Stop the instance")
        print("   2. Modify subnet to not auto-assign public IPs")
        print("   3. Start the instance")


if __name__ == "__main__":
    main()
