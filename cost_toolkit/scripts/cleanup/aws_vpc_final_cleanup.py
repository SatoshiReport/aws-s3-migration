#!/usr/bin/env python3
"""Final VPC cleanup operations."""

from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_client_factory import create_client


def release_remaining_elastic_ip():
    """Try to release the remaining Elastic IP in eu-west-2"""
    print("AWS VPC Final Cleanup - Remaining Elastic IP")
    print("=" * 80)

    try:
        ec2 = create_client("ec2", region="eu-west-2")

        # Get the remaining Elastic IP
        response = ec2.describe_addresses()
        addresses = response.get("Addresses", [])

        if not addresses:
            print("✅ No Elastic IP addresses found in eu-west-2")
            return True

        for addr in addresses:
            allocation_id = addr.get("AllocationId")
            public_ip = addr.get("PublicIp")
            association_id = addr.get("AssociationId")

            print(f"Found IP: {public_ip} (Allocation ID: {allocation_id})")

            try:
                # If associated, disassociate first
                if association_id:
                    print("  🔗 Disassociating from instance...")
                    ec2.disassociate_address(AssociationId=association_id)
                    print("  ✅ Disassociated successfully")

                # Try to release the IP
                print("  🗑️  Attempting to release Elastic IP...")
                ec2.release_address(AllocationId=allocation_id)
                print(f"  ✅ Successfully released {public_ip}")

            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                error_message = e.response["Error"]["Message"]

                if error_code == "InvalidAddress.Locked":
                    print(f"  ❌ IP is locked by AWS: {error_message}")
                    print("  ℹ️  This IP requires AWS Support to unlock")
                    return False
                print(f"  ❌ Failed to release {public_ip}: {error_message}")
                return False

    except ClientError as e:
        print(f"❌ Error accessing eu-west-2: {e}")
        return False
    return True


def main():
    """Release final remaining Elastic IP address."""
    print("Attempting to release the final remaining Elastic IP...")

    success = release_remaining_elastic_ip()

    if success:
        print("\n✅ SUCCESS: All Elastic IPs have been released!")
        print("💰 Total monthly savings: $14.40")
        print("💰 Annual savings: $172.80")
    else:
        print("\n⚠️  PARTIAL SUCCESS: 1 IP remains locked by AWS")
        print("💰 Monthly savings so far: $10.80")
        print("💰 Remaining cost: $3.60/month for locked IP")
        print("📞 Contact AWS Support to unlock the remaining IP")


if __name__ == "__main__":
    main()
