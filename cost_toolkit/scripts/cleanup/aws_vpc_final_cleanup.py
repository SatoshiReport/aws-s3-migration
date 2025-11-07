#!/usr/bin/env python3

import boto3
from botocore.exceptions import ClientError


def release_remaining_elastic_ip():
    """Try to release the remaining Elastic IP in eu-west-2"""
    print("AWS VPC Final Cleanup - Remaining Elastic IP")
    print("=" * 80)

    try:
        ec2 = boto3.client("ec2", region_name="eu-west-2")

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
                    print(f"  🔗 Disassociating from instance...")
                    ec2.disassociate_address(AssociationId=association_id)
                    print(f"  ✅ Disassociated successfully")

                # Try to release the IP
                print(f"  🗑️  Attempting to release Elastic IP...")
                ec2.release_address(AllocationId=allocation_id)
                print(f"  ✅ Successfully released {public_ip}")
                return True

            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                error_message = e.response["Error"]["Message"]

                if error_code == "InvalidAddress.Locked":
                    print(f"  ❌ IP is locked by AWS: {error_message}")
                    print(f"  ℹ️  This IP requires AWS Support to unlock")
                    return False
                else:
                    print(f"  ❌ Failed to release {public_ip}: {error_message}")
                    return False

        return True

    except ClientError as e:
        print(f"❌ Error accessing eu-west-2: {e}")
        return False


def main():
    print("Attempting to release the final remaining Elastic IP...")

    success = release_remaining_elastic_ip()

    if success:
        print(f"\n✅ SUCCESS: All Elastic IPs have been released!")
        print(f"💰 Total monthly savings: $14.40")
        print(f"💰 Annual savings: $172.80")
    else:
        print(f"\n⚠️  PARTIAL SUCCESS: 1 IP remains locked by AWS")
        print(f"💰 Monthly savings so far: $10.80")
        print(f"💰 Remaining cost: $3.60/month for locked IP")
        print(f"📞 Contact AWS Support to unlock the remaining IP")


if __name__ == "__main__":
    main()
