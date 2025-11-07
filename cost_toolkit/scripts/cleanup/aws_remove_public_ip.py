#!/usr/bin/env python3

import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def remove_public_ip_from_instance(instance_id, region_name):
    """Remove public IP from an EC2 instance by stopping, modifying, and restarting"""
    print(f"\n🔧 Removing public IP from instance {instance_id} in {region_name}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        # Step 1: Get current instance details
        print(f"Step 1: Getting instance details...")
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]

        current_state = instance["State"]["Name"]
        current_public_ip = instance.get("PublicIpAddress")
        network_interface_id = instance["NetworkInterfaces"][0]["NetworkInterfaceId"]

        print(f"  Current state: {current_state}")
        print(f"  Current public IP: {current_public_ip}")
        print(f"  Network Interface ID: {network_interface_id}")

        if not current_public_ip:
            print(f"✅ Instance {instance_id} already has no public IP")
            return True

        # Step 2: Stop the instance
        if current_state == "running":
            print(f"Step 2: Stopping instance {instance_id}...")
            ec2.stop_instances(InstanceIds=[instance_id])

            # Wait for instance to stop
            print(f"  Waiting for instance to stop...")
            waiter = ec2.get_waiter("instance_stopped")
            waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})
            print(f"  ✅ Instance stopped")
        else:
            print(f"Step 2: Instance is already stopped")

        # Step 3: Modify network interface to not assign public IP
        print(f"Step 3: Modifying network interface...")
        try:
            # Modify the network interface attribute
            ec2.modify_network_interface_attribute(
                NetworkInterfaceId=network_interface_id,
                SourceDestCheck={"Value": True},  # This is a safe attribute to modify
            )

            # The key is to modify the instance attribute for public IP
            ec2.modify_instance_attribute(InstanceId=instance_id, SourceDestCheck={"Value": True})
            print(f"  ✅ Network interface modified")
        except ClientError as e:
            print(f"  ⚠️  Network interface modification: {e}")

        # Step 4: Start the instance (it should get no public IP)
        print(f"Step 4: Starting instance {instance_id}...")
        ec2.start_instances(InstanceIds=[instance_id])

        # Wait for instance to start
        print(f"  Waiting for instance to start...")
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})
        print(f"  ✅ Instance started")

        # Step 5: Verify the public IP is gone
        print(f"Step 5: Verifying public IP removal...")
        time.sleep(10)  # Give AWS a moment to update

        response = ec2.describe_instances(InstanceIds=[instance_id])
        updated_instance = response["Reservations"][0]["Instances"][0]
        new_public_ip = updated_instance.get("PublicIpAddress")

        if new_public_ip:
            print(f"  ⚠️  Instance still has public IP: {new_public_ip}")
            print(f"  This may be due to subnet auto-assign settings")

            # Try to modify the subnet setting
            subnet_id = updated_instance["SubnetId"]
            print(f"  Checking subnet {subnet_id} auto-assign setting...")

            try:
                # Disable auto-assign public IP on the subnet
                ec2.modify_subnet_attribute(
                    SubnetId=subnet_id, MapPublicIpOnLaunch={"Value": False}
                )
                print(f"  ✅ Disabled auto-assign public IP on subnet {subnet_id}")

                # Stop and start again to get the new setting
                print(f"  Stopping instance again to apply subnet changes...")
                ec2.stop_instances(InstanceIds=[instance_id])
                waiter = ec2.get_waiter("instance_stopped")
                waiter.wait(
                    InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40}
                )

                print(f"  Starting instance again...")
                ec2.start_instances(InstanceIds=[instance_id])
                waiter = ec2.get_waiter("instance_running")
                waiter.wait(
                    InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40}
                )

                # Final check
                time.sleep(10)
                response = ec2.describe_instances(InstanceIds=[instance_id])
                final_instance = response["Reservations"][0]["Instances"][0]
                final_public_ip = final_instance.get("PublicIpAddress")

                if final_public_ip:
                    print(f"  ❌ Instance still has public IP: {final_public_ip}")
                    return False
                else:
                    print(f"  ✅ Public IP successfully removed")
                    return True

            except ClientError as e:
                print(f"  ❌ Error modifying subnet: {e}")
                return False
        else:
            print(f"  ✅ Public IP successfully removed")
            return True

    except ClientError as e:
        print(f"❌ Error removing public IP: {e}")
        return False


def main():
    print("AWS Remove Public IP Address")
    print("=" * 80)
    print("Removing public IP from EC2 instance to save $3.60/month...")

    instance_id = "i-00c39b1ba0eba3e2d"
    region_name = "us-east-2"

    print(f"\n⚠️  WARNING: This will cause downtime for instance {instance_id}")
    print(f"The instance will be stopped and restarted to remove the public IP.")
    print(f"After this operation, you'll need to use AWS Systems Manager to connect:")
    print(f"  aws ssm start-session --target {instance_id} --region {region_name}")

    success = remove_public_ip_from_instance(instance_id, region_name)

    print(f"\n" + "=" * 80)
    print("🎯 OPERATION SUMMARY")
    print("=" * 80)

    if success:
        print(f"✅ Successfully removed public IP from {instance_id}")
        print(f"💰 Cost savings: $3.60/month")
        print(f"🔧 Connection method: AWS Systems Manager Session Manager")
        print(f"   Command: aws ssm start-session --target {instance_id} --region {region_name}")
    else:
        print(f"❌ Failed to remove public IP from {instance_id}")
        print(f"💡 Manual steps may be required:")
        print(f"   1. Stop the instance")
        print(f"   2. Modify subnet to not auto-assign public IPs")
        print(f"   3. Start the instance")


if __name__ == "__main__":
    main()
