#!/usr/bin/env python3

import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def remove_public_ip_by_network_interface_replacement(  # noqa: C901, PLR0911, PLR0912, PLR0915
    instance_id, region_name
):  # noqa: C901, PLR0911, PLR0912, PLR0915
    """Remove public IP by creating a new network interface without public IP"""
    print(f"\n🔧 Advanced method: Replacing network interface for {instance_id}")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        # Step 1: Get current instance details
        print(f"Step 1: Getting instance details...")
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]

        current_state = instance["State"]["Name"]
        current_public_ip = instance.get("PublicIpAddress")
        vpc_id = instance["VpcId"]
        subnet_id = instance["SubnetId"]
        security_groups = [sg["GroupId"] for sg in instance["SecurityGroups"]]
        current_eni = instance["NetworkInterfaces"][0]
        current_eni_id = current_eni["NetworkInterfaceId"]

        print(f"  Current state: {current_state}")
        print(f"  Current public IP: {current_public_ip}")
        print(f"  VPC: {vpc_id}")
        print(f"  Subnet: {subnet_id}")
        print(f"  Security Groups: {security_groups}")
        print(f"  Current ENI: {current_eni_id}")

        if not current_public_ip:
            print(f"✅ Instance {instance_id} already has no public IP")
            return True

        # Step 2: Stop the instance if running
        if current_state == "running":
            print(f"Step 2: Stopping instance {instance_id}...")
            ec2.stop_instances(InstanceIds=[instance_id])

            waiter = ec2.get_waiter("instance_stopped")
            waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})
            print(f"  ✅ Instance stopped")

        # Step 3: Create a new network interface without public IP
        print(f"Step 3: Creating new network interface without public IP...")

        try:
            new_eni_response = ec2.create_network_interface(
                SubnetId=subnet_id,
                Groups=security_groups,
                Description=f"Replacement ENI for {instance_id} - no public IP",
            )
            new_eni_id = new_eni_response["NetworkInterface"]["NetworkInterfaceId"]
            print(f"  ✅ Created new ENI: {new_eni_id}")

            # Wait for the new ENI to be available
            time.sleep(5)

        except ClientError as e:
            print(f"  ❌ Error creating new ENI: {e}")
            return False

        # Step 4: Detach the current network interface
        print(f"Step 4: Detaching current network interface...")
        try:
            attachment_id = current_eni["Attachment"]["AttachmentId"]
            ec2.detach_network_interface(AttachmentId=attachment_id, Force=True)
            print(f"  ✅ Detached ENI {current_eni_id}")

            # Wait for detachment
            time.sleep(10)

        except ClientError as e:
            print(f"  ❌ Error detaching ENI: {e}")
            # Clean up the new ENI
            try:
                ec2.delete_network_interface(NetworkInterfaceId=new_eni_id)
            except:
                pass
            return False

        # Step 5: Attach the new network interface
        print(f"Step 5: Attaching new network interface...")
        try:
            attach_response = ec2.attach_network_interface(
                NetworkInterfaceId=new_eni_id, InstanceId=instance_id, DeviceIndex=0
            )
            print(f"  ✅ Attached new ENI {new_eni_id}")

            # Wait for attachment
            time.sleep(10)

        except ClientError as e:
            print(f"  ❌ Error attaching new ENI: {e}")
            # Clean up
            try:
                ec2.delete_network_interface(NetworkInterfaceId=new_eni_id)
            except:
                pass
            return False

        # Step 6: Start the instance
        print(f"Step 6: Starting instance...")
        try:
            ec2.start_instances(InstanceIds=[instance_id])

            waiter = ec2.get_waiter("instance_running")
            waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})
            print(f"  ✅ Instance started")

        except ClientError as e:
            print(f"  ❌ Error starting instance: {e}")
            return False

        # Step 7: Verify no public IP
        print(f"Step 7: Verifying public IP removal...")
        time.sleep(10)

        response = ec2.describe_instances(InstanceIds=[instance_id])
        updated_instance = response["Reservations"][0]["Instances"][0]
        new_public_ip = updated_instance.get("PublicIpAddress")

        if new_public_ip:
            print(f"  ❌ Instance still has public IP: {new_public_ip}")
            return False
        else:
            print(f"  ✅ Public IP successfully removed")

            # Step 8: Clean up the old network interface
            print(f"Step 8: Cleaning up old network interface...")
            try:
                ec2.delete_network_interface(NetworkInterfaceId=current_eni_id)
                print(f"  ✅ Deleted old ENI {current_eni_id}")
            except ClientError as e:
                print(f"  ⚠️  Could not delete old ENI {current_eni_id}: {e}")

            return True

    except ClientError as e:
        print(f"❌ Error in advanced public IP removal: {e}")
        return False


def simple_stop_start_without_public_ip(instance_id, region_name):
    """Simple approach: just stop instance and start in private subnet mode"""
    print(f"\n🔧 Simple method: Stop/start with private-only configuration")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name=region_name)

        # Get instance details
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]
        subnet_id = instance["SubnetId"]

        print(f"Step 1: Ensuring subnet doesn't auto-assign public IPs...")

        # Make sure subnet doesn't auto-assign public IPs
        ec2.modify_subnet_attribute(SubnetId=subnet_id, MapPublicIpOnLaunch={"Value": False})
        print(f"  ✅ Subnet {subnet_id} set to not auto-assign public IPs")

        print(f"Step 2: Stopping instance...")
        ec2.stop_instances(InstanceIds=[instance_id])

        waiter = ec2.get_waiter("instance_stopped")
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})
        print(f"  ✅ Instance stopped")

        print(f"Step 3: Starting instance (should get no public IP)...")
        ec2.start_instances(InstanceIds=[instance_id])

        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})
        print(f"  ✅ Instance started")

        # Verify
        time.sleep(10)
        response = ec2.describe_instances(InstanceIds=[instance_id])
        updated_instance = response["Reservations"][0]["Instances"][0]
        new_public_ip = updated_instance.get("PublicIpAddress")

        if new_public_ip:
            print(f"  ❌ Instance still has public IP: {new_public_ip}")
            return False
        else:
            print(f"  ✅ Public IP successfully removed")
            return True

    except ClientError as e:
        print(f"❌ Error in simple public IP removal: {e}")
        return False


def main():
    print("AWS Advanced Public IP Removal")
    print("=" * 80)

    instance_id = "i-00c39b1ba0eba3e2d"
    region_name = "us-east-2"

    print(f"Attempting to remove public IP from {instance_id}")
    print(f"Current public IP: 18.191.206.247 (from previous attempt)")

    # Try the simple method first
    print(f"\n" + "=" * 80)
    print("ATTEMPTING SIMPLE METHOD")
    print("=" * 80)

    success = simple_stop_start_without_public_ip(instance_id, region_name)

    if not success:
        print(f"\n" + "=" * 80)
        print("ATTEMPTING ADVANCED METHOD")
        print("=" * 80)
        success = remove_public_ip_by_network_interface_replacement(instance_id, region_name)

    # Final summary
    print(f"\n" + "=" * 80)
    print("🎯 FINAL RESULT")
    print("=" * 80)

    if success:
        print(f"✅ Successfully removed public IP from {instance_id}")
        print(f"💰 Monthly savings: $3.60")
        print(f"🔧 Connection method: AWS Systems Manager")
        print(f"   Command: aws ssm start-session --target {instance_id} --region {region_name}")
        print(f"📍 Instance now has private IP only")
    else:
        print(f"❌ Failed to remove public IP from {instance_id}")
        print(f"💡 The instance may need manual intervention via AWS Console")
        print(f"   1. Stop the instance")
        print(f"   2. Actions -> Networking -> Change subnet (to a private subnet)")
        print(f"   3. Start the instance")


if __name__ == "__main__":
    main()
