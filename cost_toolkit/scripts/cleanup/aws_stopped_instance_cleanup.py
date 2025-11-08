#!/usr/bin/env python3
"""
AWS Stopped Instance Cleanup Script
Terminates stopped EC2 instances and cleans up associated resources.
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
        raise ValueError("AWS credentials not found in ~/.env file")  # noqa: TRY003

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def get_instance_details(region_name, instance_id, aws_access_key_id, aws_secret_access_key):
    """Get detailed information about an EC2 instance"""
    try:
        ec2 = boto3.client(
            "ec2",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]

        # Get tags for better identification
        tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
        name = tags.get("Name", "No Name")

        # Get volume information
        volumes = []
        for bdm in instance.get("BlockDeviceMappings", []):
            if "Ebs" in bdm:
                volumes.append(
                    {
                        "volume_id": bdm["Ebs"]["VolumeId"],
                        "device_name": bdm["DeviceName"],
                        "delete_on_termination": bdm["Ebs"]["DeleteOnTermination"],
                    }
                )

        instance_info = {
            "instance_id": instance_id,
            "name": name,
            "instance_type": instance["InstanceType"],
            "state": instance["State"]["Name"],
            "vpc_id": instance.get("VpcId", "N/A"),
            "subnet_id": instance.get("SubnetId", "N/A"),
            "private_ip": instance.get("PrivateIpAddress", "N/A"),
            "public_ip": instance.get("PublicIpAddress", "None"),
            "launch_time": instance.get("LaunchTime", "Unknown"),
            "volumes": volumes,
            "tags": tags,
            "security_groups": [sg["GroupId"] for sg in instance.get("SecurityGroups", [])],
            "network_interfaces": [
                eni["NetworkInterfaceId"] for eni in instance.get("NetworkInterfaces", [])
            ],
        }

    except Exception as e:
        print(f"❌ Error getting instance details for {instance_id}: {str(e)}")
        return None

    else:
        return instance_info


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

    except Exception as e:
        print(f"   ❌ Failed to terminate {instance_id}: {str(e)}")
        return False

    else:
        return True


def main():  # noqa: C901, PLR0912, PLR0915
    """Main execution function"""
    print("AWS Stopped Instance Cleanup")
    print("=" * 50)
    print("Terminating stopped EC2 instances and cleaning up resources...")
    print()

    try:
        # Load credentials
        aws_access_key_id, aws_secret_access_key = load_aws_credentials()

        # Target stopped instances identified in audit - EU-WEST-2 ONLY
        stopped_instances = [
            {"region": "eu-west-2", "instance_id": "i-09ff569745467b037", "type": "r7i.2xlarge"},
            {"region": "eu-west-2", "instance_id": "i-0635f4a0de21cbc37", "type": "r7i.2xlarge"},
        ]

        print(f"🎯 Target: {len(stopped_instances)} stopped instances")
        print()

        # Get detailed information for each instance
        instance_details = []
        for instance in stopped_instances:
            region = instance["region"]
            instance_id = instance["instance_id"]

            print(f"🔍 Analyzing instance: {instance_id} ({region})")
            details = get_instance_details(
                region, instance_id, aws_access_key_id, aws_secret_access_key
            )

            if details:
                instance_details.append({"region": region, "details": details})

                print(f"   Name: {details['name']}")
                print(f"   Type: {details['instance_type']}")
                print(f"   State: {details['state']}")
                print(f"   VPC: {details['vpc_id']}")
                print(f"   Launch Time: {details['launch_time']}")
                print(f"   Volumes: {len(details['volumes'])} attached")
                print(f"   Network Interfaces: {len(details['network_interfaces'])} attached")

                # Show volume deletion behavior
                for volume in details["volumes"]:
                    delete_behavior = (
                        "will be deleted"
                        if volume["delete_on_termination"]
                        else "will be preserved"
                    )
                    print(
                        f"      📀 {volume['volume_id']} ({volume['device_name']}) - {delete_behavior}"
                    )
            print()

        if not instance_details:
            print("❌ No valid instances found to terminate")
            return

        # Show termination impact
        print("⚠️  TERMINATION IMPACT:")
        print("   • Instances will be permanently deleted")
        print("   • Some EBS volumes may be deleted (check delete_on_termination)")
        print("   • Network interfaces will be detached")
        print("   • This action cannot be undone")
        print("   • Significant cost savings from stopping r7i.2xlarge instances")
        print()

        confirmation = input("Type 'TERMINATE STOPPED INSTANCES' to proceed: ")

        if confirmation != "TERMINATE STOPPED INSTANCES":
            print("❌ Operation cancelled - confirmation text did not match")
            return

        print("\n🚨 Proceeding with instance termination...")
        print("=" * 50)

        # Terminate instances
        terminated_instances = []
        failed_terminations = []

        for instance_data in instance_details:
            region = instance_data["region"]
            details = instance_data["details"]
            instance_id = details["instance_id"]

            success = terminate_instance(
                region, instance_id, aws_access_key_id, aws_secret_access_key
            )

            if success:
                terminated_instances.append(instance_data)
            else:
                failed_terminations.append(instance_data)

        # Summary
        print("\n" + "=" * 50)
        print("🎯 INSTANCE TERMINATION SUMMARY")
        print("=" * 50)
        print(f"✅ Successfully terminated: {len(terminated_instances)} instances")
        print(f"❌ Failed terminations: {len(failed_terminations)} instances")
        print()

        if terminated_instances:
            print("✅ Successfully terminated instances:")
            for instance_data in terminated_instances:
                details = instance_data["details"]
                region = instance_data["region"]
                print(
                    f"   🗑️  {details['instance_id']} ({region}) - {details['name']} ({details['instance_type']})"
                )

        if failed_terminations:
            print("\n❌ Failed terminations:")
            for instance_data in failed_terminations:
                details = instance_data["details"]
                region = instance_data["region"]
                print(f"   ❌ {details['instance_id']} ({region}) - {details['name']}")

        if len(terminated_instances) > 0:
            print("\n🎉 Instance termination completed!")
            print("   • Stopped instances have been terminated")
            print("   • Network interfaces will be automatically detached")
            print("   • EBS volumes handled according to delete_on_termination setting")
            print("   • Significant cost savings achieved")
            print("\n💡 Next steps:")
            print("   • Wait for termination to complete (5-10 minutes)")
            print("   • Run VPC cleanup to remove empty VPCs if desired")
            print("   • Verify no orphaned resources remain")

    except Exception as e:
        print(f"❌ Critical error during instance cleanup: {str(e)}")
        raise


if __name__ == "__main__":
    main()
